"""
Simulation Configurator - Flask Backend
Run from the simulator/ directory: python ui/server.py
"""

import csv
import io
import json
import re
import ast
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from io import StringIO

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent   # simulator/
AGT_DIR   = BASE_DIR / "agt"
ARCH_DIR  = BASE_DIR / "arch"
BB_DIR    = BASE_DIR / "bb"
INIT_DIR  = BASE_DIR / "initializer"
ENV_CLASS = "env.Env"

DEFAULT_OUTPUT_FOLDER = "simulation_output"
DEFAULT_MAS_NAME      = "simulation_example"

# Fixed column schemas for each initializer CSV
INITIALIZER_SCHEMAS = {
    "messages.csv":        ["id", "author", "content", "reactions", "original", "topics", "variables"],
    "network.csv":         ["from", "to", "weight"],
    "public_profiles.csv": ["agent", "attribute", "value"],
}

# ── Discovery ────────────────────────────────────────────────────────────────

def discover_java_classes(directory: Path, package: str) -> list[str]:
    if not directory.exists():
        return []
    results = []
    for f in sorted(directory.glob("*.java")):
        source = f.read_text(errors="ignore")
        if re.search(rf'\binterface\s+{re.escape(f.stem)}\b', source):
            continue
        results.append(f"{package}.{f.stem}")
    return results

def discover_asl_files() -> list[str]:
    if not AGT_DIR.exists():
        return []
    return sorted(f.name for f in AGT_DIR.glob("*.asl"))

def _safe_folder_name(name: str) -> str:
    clean = name.replace("\\", "/").strip("/")
    if not clean or ".." in clean.split("/"):
        return DEFAULT_OUTPUT_FOLDER
    if not re.match(r'^[\w\-./]+$', clean):
        return DEFAULT_OUTPUT_FOLDER
    return clean


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/options")
def options():
    return jsonify({
        "asl_files":           discover_asl_files(),
        "arch_classes":        discover_java_classes(ARCH_DIR, "arch"),
        "bb_classes":          discover_java_classes(BB_DIR,   "bb"),
        "initializer_schemas": INITIALIZER_SCHEMAS,
    })

@app.route("/api/asl_preview")
def asl_preview():
    name = request.args.get("name", "")
    path = AGT_DIR / name
    if not path.exists() or path.suffix != ".asl":
        return jsonify({"error": "File not found"}), 404
    return jsonify({"content": path.read_text()})

@app.route("/api/parse_csv", methods=["POST"])
def parse_csv():
    """Parse an uploaded wide-format CSV (for agent instances)."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    text   = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows    = [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    columns = [c.strip() for c in (reader.fieldnames or [])]
    return jsonify({"rows": rows, "columns": columns})

@app.route("/api/parse_initializer_csv", methods=["POST"])
def parse_initializer_csv():
    """Parse an uploaded initializer CSV (fixed schema, returned as row dicts)."""
    name   = request.form.get("name", "")
    f      = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    schema = INITIALIZER_SCHEMAS.get(name, [])
    text   = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row_idx, row in enumerate(reader):
        clean = {k.strip(): (v or "").strip() for k, v in row.items()}
        parsed_row = {}
        for col in schema:
            value = clean.get(col, "")
            if col == "variables":
                try:
                    parsed_row[col] = value
                except ValueError as e:
                    return jsonify({"error": f"Row {row_idx}: {str(e)}"}), 400
            else:
                parsed_row[col] = value
        rows.append(parsed_row)
    return jsonify({"rows": rows})

@app.route("/api/generate", methods=["POST"])
def generate():
    data        = request.get_json(force=True)
    errors      = []
    gen_files   = []
    agent_lines = []

    mas_name       = (data.get("mas_name")      or DEFAULT_MAS_NAME).strip()
    raw_folder     = (data.get("output_folder") or DEFAULT_OUTPUT_FOLDER).strip()
    mind_inspector = bool(data.get("mind_inspector", False))
    silent_logging = bool(data.get("silent_logging", False))
    output_folder  = _safe_folder_name(raw_folder)

    agent_types  = data.get("agent_types",  [])
    initializers = data.get("initializers", {})

    # ── Output directories ────────────────────────────────────────────────────
    out_dir      = BASE_DIR / output_folder
    out_agt_dir  = out_dir / "agt"
    out_init_dir = out_dir / "initializer"
    out_agt_dir.mkdir(parents=True, exist_ok=True)
    out_init_dir.mkdir(parents=True, exist_ok=True)

    # ── Copy / generate logging.properties ───────────────────────────────────────
    logging_dst = BASE_DIR / "logging.properties"
    logging_dst.write_text(
        _build_logging_properties(silent=silent_logging), encoding="utf-8"
    )
    gen_files.append(str(logging_dst.relative_to(BASE_DIR)))

    # ── Pre-count total instances per stem ────────────────────────────────────
    stem_totals: dict[str, int] = {}
    for atype in agent_types:
        asl_src = atype.get("asl", "")
        if not asl_src:
            continue
        stem = Path(asl_src).stem
        for inst in atype.get("instances", []):
            count = max(1, int(inst.get("_count", 1) or 1))
            stem_totals[stem] = stem_totals.get(stem, 0) + count

    # ── Agent .asl files + mas2j lines ────────────────────────────────────────
    stem_counter: dict[str, int] = {}
    written_stems: set[str] = set()

    for tidx, atype in enumerate(agent_types):
        asl_src   = atype.get("asl", "")
        arch_cls  = (atype.get("arch_class") or "").strip()
        bb_cls    = (atype.get("bb_class")   or "").strip()
        instances = atype.get("instances", [])

        if not asl_src:
            errors.append(f"Agent type {tidx}: missing .asl file.")
            continue

        src_path = AGT_DIR / asl_src
        if not src_path.exists():
            errors.append(f"Agent type {tidx}: '{asl_src}' not found in agt/.")
            continue

        stem           = src_path.stem
        multiple_total = stem_totals.get(stem, 1) > 1

        # Write the shared .asl once per stem — no beliefs baked in
        if stem not in written_stems:
            out_path = out_agt_dir / f"{stem}.asl"
            out_path.write_text(src_path.read_text(), encoding="utf-8")
            gen_files.append(str(out_path.relative_to(BASE_DIR)))
            written_stems.add(stem)

        for inst in instances:
            count     = max(1, int(inst.get("_count", 1) or 1))
            inst_data = {k: v for k, v in inst.items() if k != "_count"}

            belief_str = _build_belief_string(inst_data)
            beliefs_clause = f' [ beliefs="{belief_str}" ]' if belief_str else ""

            for _ in range(count):
                stem_counter[stem] = stem_counter.get(stem, 0) + 1
                idx = stem_counter[stem]

                agent_name = stem if not multiple_total else f"{stem}_{idx}"

                clauses = []
                if arch_cls: clauses.append(f"agentArchClass {arch_cls}")
                if bb_cls:   clauses.append(f"beliefBaseClass {bb_cls}")
                arch_suffix = (
                    "\n            " + "\n            ".join(clauses)
                ) if clauses else ""

                agent_lines.append(
                    f"        {agent_name}  {stem}{beliefs_clause}{arch_suffix};"
                )

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # ── Initializer CSVs ──────────────────────────────────────────────────────
    for csv_name, rows in initializers.items():
        schema = INITIALIZER_SCHEMAS.get(csv_name)
        if not schema or not rows:
            continue

        out_path = out_init_dir / csv_name
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=schema, extrasaction="ignore")
            writer.writeheader()
            for row_idx, row in enumerate(rows):
                if "variables" in row:
                    raw = (row.get("variables") or "").strip()
                    try:
                        parsed = parse_variables(raw, row_idx)
                        row["variables"] = json.dumps(parsed)
                    except ValueError as e:
                        return jsonify({
                            "ok": False,
                            "error": f"{csv_name} row {row_idx}: {str(e)}"
                        }), 400
                writer.writerow(row)
        gen_files.append(str(out_path.relative_to(BASE_DIR)))

    # ── .mas2j ────────────────────────────────────────────────────────────────
    mas2j     = _build_mas2j(mas_name, ENV_CLASS, agent_lines,
                              asl_source_path="./agt",
                              mind_inspector=mind_inspector)
    mas2j_out = out_dir / f"{mas_name}.mas2j"
    mas2j_out.write_text(mas2j, encoding="utf-8")
    gen_files.append(str(mas2j_out.relative_to(BASE_DIR)))

    return jsonify({
        "ok": True,
        "generated_files": gen_files,
        "output_folder":   output_folder,
        "mas_name":        mas_name,
        "mas2j":           mas2j,
    })

# ── Visualisations ────────────────────────────────────────────────────────────

@app.route("/<path:folder>/epidemic")
def visualize_epidemic(folder: str):
    safe_folder = _safe_folder_name(folder)
    logs_dir    = BASE_DIR / safe_folder / "logs"

    agents_data: dict[str, list] = {}
    error = None

    if not logs_dir.exists():
        error = f"Logs directory not found: {logs_dir.relative_to(BASE_DIR)}"
    else:
        for jsonl_file in sorted(logs_dir.glob("*.jsonl")):
            if jsonl_file.stem == "messages":
                continue
            agent_name = jsonl_file.stem
            rows: list[dict] = []
            try:
                for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            except Exception as exc:
                error = f"Failed to parse {jsonl_file.name}: {exc}"
                break
            if rows:
                agents_data[agent_name] = rows

    # ── Load network.csv ──────────────────────────────────────────────────────
    network_data: dict = {"edges": [], "loaded": False}
    network_csv = BASE_DIR / safe_folder / "initializer" / "network.csv"
    if network_csv.exists():
        try:
            edges = []
            with network_csv.open(encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    src = (row.get("from") or row.get("source") or "").strip()
                    tgt = (row.get("to")   or row.get("target") or "").strip()
                    if src and tgt:
                        edges.append({"source": src, "target": tgt})
            network_data = {"edges": edges, "loaded": True}
        except Exception as exc:
            network_data = {"edges": [], "loaded": False, "error": str(exc)}

    return render_template(
        "epidemic.html",
        folder       = safe_folder,
        folder_json  = json.dumps(safe_folder),
        agents_json  = json.dumps(agents_data),
        network_json = json.dumps(network_data),
        error        = error,
    )

@app.route("/<path:folder>/agts")
def visualize_agts(folder: str):
    safe_folder = _safe_folder_name(folder)
    logs_dir    = BASE_DIR / safe_folder / "logs"

    agents_data: dict[str, list] = {}
    error = None

    if not logs_dir.exists():
        error = f"Logs directory not found: {logs_dir.relative_to(BASE_DIR)}"
    else:
        for jsonl_file in sorted(logs_dir.glob("*.jsonl")):
            if jsonl_file.stem == "messages":
                continue
            agent_name = jsonl_file.stem
            rows: list[dict] = []
            try:
                for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            except Exception as exc:
                error = f"Failed to parse {jsonl_file.name}: {exc}"
                break
            if rows:
                agents_data[agent_name] = rows

    return render_template(
        "agts.html",
        folder      = safe_folder,
        folder_json = json.dumps(safe_folder),
        agents_json = json.dumps(agents_data),
        error       = error,
    )


@app.route("/<path:folder>/arg_tree")
def visualize(folder: str):
    safe_folder = _safe_folder_name(folder)
    log_path    = BASE_DIR / safe_folder / "logs" / "messages.jsonl"

    messages = []
    error    = None

    if not log_path.exists():
        error = f"Log file not found: {log_path.relative_to(BASE_DIR)}"
    else:
        try:
            for line in log_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        except Exception as exc:
            error = f"Failed to parse log file: {exc}"

    return render_template(
        "arg_tree.html",
        folder       = safe_folder,
        folder_json  = json.dumps(safe_folder),
        messages_json= json.dumps(messages),
        error        = error,
    )

@app.route("/<path:folder>/polarization")
def visualize_polarization(folder: str):
    safe_folder = _safe_folder_name(folder)
    log_path    = BASE_DIR / safe_folder / "logs" / "messages.jsonl"

    messages = []
    error    = None

    if not log_path.exists():
        error = f"Log file not found: {log_path.relative_to(BASE_DIR)}"
    else:
        try:
            for line in log_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        except Exception as exc:
            error = f"Failed to parse log file: {exc}"

    return render_template(
        "polarization.html",
        folder        = safe_folder,
        folder_json   = json.dumps(safe_folder),
        messages_json = json.dumps(messages),
        error         = error,
    )

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_logging_properties(silent: bool = False) -> str:
    if silent:
        return """\
# Only log to file
handlers = java.util.logging.FileHandler

.level = ALL

############################################################
# FileHandler configuration
############################################################
java.util.logging.FileHandler.pattern = ./mas.log
java.util.logging.FileHandler.limit = 500000
java.util.logging.FileHandler.count = 1
java.util.logging.FileHandler.formatter = java.util.logging.SimpleFormatter
java.util.logging.FileHandler.level = INFO

############################################################
# Disable console/GUI logging
############################################################
java.util.logging.ConsoleHandler.level = OFF
jason.runtime.MASConsoleLogHandler.level = OFF

############################################################
# Silence other verbose loggers
############################################################
java.level = OFF
javax.level = OFF
sun.level = OFF
jade.level = OFF
"""
    return """\
# Use both FileHandler and ConsoleHandler
handlers = java.util.logging.FileHandler, jason.runtime.MASConsoleLogHandler

.level = ALL

############################################################
# FileHandler configuration
############################################################
java.util.logging.FileHandler.pattern = ./mas.log
java.util.logging.FileHandler.limit = 500000
java.util.logging.FileHandler.count = 1
java.util.logging.FileHandler.formatter = java.util.logging.SimpleFormatter
java.util.logging.FileHandler.level = INFO

############################################################
# ConsoleHandler configuration
############################################################
java.util.logging.ConsoleHandler.level = INFO
java.util.logging.ConsoleHandler.formatter = jason.runtime.MASConsoleLogFormatter

############################################################
# Jason MAS specific handler
############################################################
jason.runtime.MASConsoleLogHandler.level = INFO
jason.runtime.MASConsoleLogHandler.formatter = jason.runtime.MASConsoleLogFormatter
jason.runtime.MASConsoleLogHandler.tabbed = false
jason.runtime.MASConsoleLogHandler.colors = true

############################################################
# Silence other verbose loggers
############################################################
java.level = OFF
javax.level = OFF
sun.level = OFF
jade.level = OFF
"""

def parse_variables(value: str, row_idx: int):
    """
    Parses the variables field into a nested dict.

    Accepts two formats (auto-detected):

    1. JSON object  — e.g.  {"public": {"conversation_id": 1, "state": "infected"}}
    2. Dot-path pairs — e.g.  public.likes=10;private.score=0.8

    Both formats can appear in the same CSV; detection is per-cell.
    """
    if not value:
        return {}

    stripped = value.strip()

    # ── JSON format ───────────────────────────────────────────────────────────
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                raise ValueError(f"Row {row_idx}: JSON variables must be an object, got {type(parsed).__name__}")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValueError(f"Row {row_idx}: invalid JSON in variables field: {exc}") from exc

    # ── Dot-path format (original behaviour) ─────────────────────────────────
    result = {}
    for pair in stripped.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"Invalid variable '{pair}' (missing '=')")
        key_path, raw_value = pair.split("=", 1)
        keys = [k.strip() for k in key_path.split(".") if k.strip()]
        if not keys:
            raise ValueError(f"Invalid key in '{pair}'")
        val = raw_value.strip()
        if val.lower() in ("true", "false"):
            val = val.lower() == "true"
        else:
            try:
                val = float(val) if "." in val else int(val)
            except ValueError:
                pass
        current = result
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = val
    return result


def _build_belief_string(instance: dict) -> str:
    """
    Build a comma-separated belief string for the mas2j [ beliefs="..." ] clause.
    e.g. {"pepe": "num1", "prob": "0.3"} → 'pepe(num1), prob(0.3)'
    """
    parts = []
    for attr, value in instance.items():
        attr  = (attr  or "").strip()
        value = (value or "").strip()
        if not attr or not value:
            continue
        functor = attr.split(":")[0].strip()
        if not functor:
            continue
        args     = _parse_fact_args(value)
        rendered = ", ".join(_render_arg(a) for a in args)
        parts.append(f"{functor}({rendered})")
    return ", ".join(parts)


def _parse_fact_args(value: str) -> list[str]:
    """Robust CSV-style parser that respects quoted strings."""
    reader = csv.reader(StringIO(value), skipinitialspace=True)
    return next(reader)


def _render_arg(arg: str) -> str:
    arg = arg.strip()
    if not arg:
        return '""'
    if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
        inner = arg[1:-1].replace('"', '\\"')
        return f'"{inner}"'
    if _is_number(arg):
        return arg
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', arg):
        return arg
    if arg.startswith("[") and arg.endswith("]"):
        try:
            parsed = ast.literal_eval(arg)
            if isinstance(parsed, list):
                return "[" + ",".join(_render_arg(str(x)) for x in parsed) + "]"
        except Exception:
            pass
        return f'"{arg}"'
    if arg.startswith("{") and arg.endswith("}"):
        return f'"{arg}"'
    return f'"{arg.replace(chr(34), chr(92)+chr(34))}"'


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _build_mas2j(
    mas_name: str,
    env_class: str,
    agent_lines: list[str],
    asl_source_path: str = "./agt",
    mind_inspector: bool = False,
) -> str:
    block = "\n".join(agent_lines)
    exec_ctrl = (
        "\n    executionControl: jason.control.ExecutionControlGUI\n"
        if mind_inspector else ""
    )
    return (
        f"/*\n    {mas_name}\n    ---------------------------\n"
        f"    Jason Application File\n"
        f"    Auto-generated by Simulation Configurator\n*/\n\n"
        f"MAS {mas_name} {{\n"
        f"    environment: {env_class}\n"
        f"{exec_ctrl}\n"
        f"    agents:\n{block}\n\n"
        f"    aslSourcePath: \"{asl_source_path}\";\n}}\n"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Simulation Configurator  →  http://localhost:5050")
    print(f"  Base : {BASE_DIR}")
    print(f"  Agt  : {AGT_DIR}")
    app.run(debug=True, port=5050)