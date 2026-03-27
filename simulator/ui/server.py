"""
Simulation Configurator - Flask Backend
Run from the simulator/ directory: python ui/server.py
"""

import csv
import io
import re
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

# Fixed column schemas for each initializer CSV
INITIALIZER_SCHEMAS = {
    "messages.csv":        ["id", "author", "content", "reactions", "original", "topics"],
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
    rows   = []
    for row in reader:
        clean = {k.strip(): (v or "").strip() for k, v in row.items()}
        rows.append({col: clean.get(col, "") for col in schema})
    return jsonify({"rows": rows})

@app.route("/api/generate", methods=["POST"])
def generate():
    data        = request.get_json(force=True)
    errors      = []
    gen_files   = []
    agent_lines = []
    stem_counter: dict[str, int] = {}

    mas_name      = (data.get("mas_name")      or "simulation_configured").strip()
    raw_folder    = (data.get("output_folder") or DEFAULT_OUTPUT_FOLDER).strip()
    output_folder = _safe_folder_name(raw_folder)

    agent_types  = data.get("agent_types",  [])
    initializers = data.get("initializers", {})

    # ── Output directories ────────────────────────────────────────────────────
    out_dir      = BASE_DIR / output_folder
    out_agt_dir  = out_dir / "agt"
    out_init_dir = out_dir / "initializer"
    out_agt_dir.mkdir(parents=True, exist_ok=True)
    out_init_dir.mkdir(parents=True, exist_ok=True)

    # ── Copy logging.properties into the output folder ────────────────────────
    logging_src = BASE_DIR / "logging.properties"
    if logging_src.exists():
        logging_dst = out_dir / "logging.properties"
        logging_dst.write_text(logging_src.read_text(encoding="utf-8"), encoding="utf-8")
        gen_files.append(str(logging_dst.relative_to(BASE_DIR)))


    # ── Build network relationship maps from network.csv edges ────────────────
    network_edges   = initializers.get("network.csv", [])
    follows_map:    dict[str, set] = {}
    followed_by_map: dict[str, set] = {}

    for edge in network_edges:
        frm = (edge.get("from") or "").strip()
        to  = (edge.get("to")   or "").strip()
        if frm and to:
            follows_map.setdefault(frm, set()).add(to)
            followed_by_map.setdefault(to, set()).add(frm)

    # ── Pre-count instances per stem (to decide whether to suffix with _N) ────
    stem_totals: dict[str, int] = {}
    for atype in agent_types:
        asl_src = atype.get("asl", "")
        if not asl_src:
            continue
        stem = Path(asl_src).stem
        stem_totals[stem] = stem_totals.get(stem, 0) + len(atype.get("instances", []))

    # ── Agent .asl files ──────────────────────────────────────────────────────
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

        original_content = src_path.read_text()
        stem = src_path.stem

        for inst in instances:
            stem_counter[stem] = stem_counter.get(stem, 0) + 1
            # Only append _N if there are multiple instances of this type
            if stem_totals.get(stem, 1) == 1:
                out_stem = stem
            else:
                out_stem = f"{stem}_{stem_counter[stem]}"

            out_path = out_agt_dir / f"{out_stem}.asl"

            fact_block    = _build_fact_block(inst)
            network_block = _build_network_fact_block(out_stem, follows_map, followed_by_map)
            combined_block = fact_block + network_block

            new_content = (
                "/* === Auto-generated initial facts === */\n"
                + combined_block
                + "/* === End auto-generated facts === */\n\n"
                + original_content
            ) if combined_block else original_content

            out_path.write_text(new_content, encoding="utf-8")
            gen_files.append(str(out_path.relative_to(BASE_DIR)))

            clauses = []
            if arch_cls: clauses.append(f"agentArchClass {arch_cls}")
            if bb_cls:   clauses.append(f"beliefBaseClass {bb_cls}")
            suffix = ("\n            " + "\n            ".join(clauses)) if clauses else ""
            agent_lines.append(f"        {out_stem}{suffix};")

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
            writer.writerows(rows)
        gen_files.append(str(out_path.relative_to(BASE_DIR)))

    # ── .mas2j ────────────────────────────────────────────────────────────────
    mas2j     = _build_mas2j(mas_name, ENV_CLASS, agent_lines, asl_source_path="./agt")
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_fact_block(instance: dict) -> str:
    lines = []
    for attr, value in instance.items():
        attr  = (attr  or "").strip()
        value = (value or "").strip()
        if not attr or not value:
            continue
        # Strip the ":label" suffix — allows multiple columns with the same functor
        # e.g. "debate:1" and "debate:2" both emit debate(...).
        functor = attr.split(":")[0].strip()
        if not functor:
            continue
        args = _parse_fact_args(value)
        rendered = ", ".join(_render_arg(a) for a in args)
        lines.append(f"{functor}({rendered}).")
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_fact_args(value: str) -> list[str]:
    """
    Robust CSV-style parser that respects quoted strings.
    """
    reader = csv.reader(StringIO(value), skipinitialspace=True)
    return next(reader)


def _render_arg(arg: str) -> str:
    """
    Render one parsed argument for a Jason belief literal.
    Rules:
    - Numbers                 → as-is
    - Valid atoms/vars        → as-is
    - Strings (including CSV-quoted) → double-quoted, internal quotes escaped
    - Lists / dict-like text  → double-quoted
    """
    arg = arg.strip()
    if not arg:
        return '""'
    # Already quoted strings from CSV
    if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
        inner = arg[1:-1]
        inner = inner.replace('"', '\\"')  # escape double quotes
        return f'"{inner}"'
    # Numbers
    if _is_number(arg):
        return arg
    # Atoms / variable names (letters, digits, underscore)
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', arg):
        return arg
    # Structured literals (arrays / dict-like strings)
    if arg.startswith("[") and arg.endswith("]"):
        return f'"{arg}"'
    if arg.startswith("{") and arg.endswith("}"):
        return f'"{arg}"'
    # Fallback: quote anything else and escape internal quotes
    inner_escaped = arg.replace('"', r'\"')
    return f'"{inner_escaped}"'

def _build_network_fact_block(
    agent_name: str,
    follows_map: dict[str, set],
    followed_by_map: dict[str, set],
) -> str:
    lines = []
    for target in sorted(follows_map.get(agent_name, [])):
        lines.append(f'follows("{target.replace(chr(34), chr(92)+chr(34))}").')
    for source in sorted(followed_by_map.get(agent_name, [])):
        lines.append(f'followedBy("{source.replace(chr(34), chr(92)+chr(34))}").')
    return "\n".join(lines) + ("\n" if lines else "")


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
) -> str:
    block = "\n".join(agent_lines)
    return (
        f"/*\n    {mas_name}\n    ---------------------------\n"
        f"    Jason Application File\n"
        f"    Auto-generated by Simulation Configurator\n*/\n\n"
        f"MAS {mas_name} {{\n"
        f"    environment: {env_class}\n\n"
        f"    agents:\n{block}\n\n"
        f"    aslSourcePath: \"{asl_source_path}\";\n}}\n"
    )


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Simulation Configurator  →  http://localhost:5050")
    print(f"  Base : {BASE_DIR}")
    print(f"  Agt  : {AGT_DIR}")
    app.run(debug=True, port=5050)
