"""
Simulation Configurator - Flask Backend
Run from the simulator/ directory: python ui/server.py
"""

import csv as csv_mod
import io
from pathlib import Path
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent   # simulator/
AGT_DIR   = BASE_DIR / "agt"
ARCH_DIR  = BASE_DIR / "arch"
BB_DIR    = BASE_DIR / "bb"
INIT_DIR  = BASE_DIR / "initializer"
MAS2J_OUT = BASE_DIR / "simulation_configured.mas2j"

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
        # Skip interfaces — look for the pattern "interface ClassName"
        # Uses a simple heuristic: the word "interface" followed by the filename stem
        import re
        if re.search(rf'\binterface\s+{re.escape(f.stem)}\b', source):
            continue
        results.append(f"{package}.{f.stem}")
    return results

def discover_asl_files() -> list[str]:
    if not AGT_DIR.exists():
        return []
    return sorted(f.name for f in AGT_DIR.glob("*.asl"))

def discover_initializer_csvs() -> list[str]:
    """Return CSV filenames present in initializer/."""
    if not INIT_DIR.exists():
        return []
    return sorted(f.name for f in INIT_DIR.glob("*.csv"))


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/options")
def options():
    return jsonify({
        "asl_files":         discover_asl_files(),
        "arch_classes":      discover_java_classes(ARCH_DIR, "arch"),
        "bb_classes":        discover_java_classes(BB_DIR,   "bb"),
        "initializer_csvs":  discover_initializer_csvs(),
        "initializer_schemas": INITIALIZER_SCHEMAS,
    })

@app.route("/api/asl_preview")
def asl_preview():
    name = request.args.get("name", "")
    path = AGT_DIR / name
    if not path.exists() or path.suffix != ".asl":
        return jsonify({"error": "File not found"}), 404
    return jsonify({"content": path.read_text()})

@app.route("/api/load_initializer_csv")
def load_initializer_csv():
    """Load an existing initializer CSV and return its rows."""
    name = request.args.get("name", "")
    path = INIT_DIR / name
    if not path.exists() or path.suffix != ".csv":
        return jsonify({"error": "File not found"}), 404
    text = path.read_text(encoding="utf-8-sig")
    reader = csv_mod.DictReader(io.StringIO(text))
    rows = [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return jsonify({"rows": rows})

@app.route("/api/parse_csv", methods=["POST"])
def parse_csv():
    """Parse an uploaded wide-format CSV (for agent instances)."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    text = f.read().decode("utf-8-sig")
    reader = csv_mod.DictReader(io.StringIO(text))
    rows = [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    columns = [c.strip() for c in (reader.fieldnames or [])]
    return jsonify({"rows": rows, "columns": columns})

@app.route("/api/parse_initializer_csv", methods=["POST"])
def parse_initializer_csv():
    """Parse an uploaded initializer CSV (fixed schema, returned as row dicts)."""
    name = request.form.get("name", "")          # which initializer (e.g. "messages.csv")
    f    = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    schema = INITIALIZER_SCHEMAS.get(name, [])
    text   = f.read().decode("utf-8-sig")
    reader = csv_mod.DictReader(io.StringIO(text))
    rows   = []
    for row in reader:
        clean = {k.strip(): (v or "").strip() for k, v in row.items()}
        # Ensure all schema columns are present (fill missing with "")
        rows.append({col: clean.get(col, "") for col in schema})
    return jsonify({"rows": rows})

@app.route("/api/generate", methods=["POST"])
def generate():
    """
    Body (JSON):
    {
      "mas_name":  "my_simulation",
      "env_class": "env.Env",
      "agent_types": [ { "asl", "arch_class", "bb_class", "instances": [{col:val}] } ],
      "initializers": {
        "messages.csv":        [ {id, author, content, reactions, original, topics}, ... ],
        "network.csv":         [ {from, to, weight}, ... ],
        "public_profiles.csv": [ {agent, attribute, value}, ... ]
      }
    }
    """
    data        = request.get_json(force=True)
    errors      = []
    gen_files   = []
    agent_lines = []
    stem_counter: dict[str, int] = {}

    mas_name     = (data.get("mas_name")  or "simulation_configured").strip()
    env_class    = (data.get("env_class") or "env.Env").strip()
    agent_types  = data.get("agent_types",  [])
    initializers = data.get("initializers", {})

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
            out_stem = f"{stem}_{stem_counter[stem]}"
            out_path = AGT_DIR / f"{out_stem}.asl"

            fact_block  = _build_fact_block(inst)
            new_content = (
                "/* === Auto-generated initial facts === */\n"
                + fact_block
                + "/* === End auto-generated facts === */\n\n"
                + original_content
            ) if fact_block else original_content

            out_path.write_text(new_content)
            gen_files.append(str(out_path.relative_to(BASE_DIR)))

            clauses = []
            if arch_cls: clauses.append(f"agentArchClass {arch_cls}")
            if bb_cls:   clauses.append(f"beliefBaseClass {bb_cls}")
            suffix = ("\n            " + "\n            ".join(clauses)) if clauses else ""
            agent_lines.append(f"        {out_stem}{suffix};")

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # ── Initializer CSVs ──────────────────────────────────────────────────────
    INIT_DIR.mkdir(exist_ok=True)
    for csv_name, rows in initializers.items():
        schema = INITIALIZER_SCHEMAS.get(csv_name)
        if not schema:
            continue   # unknown file, skip silently
        if not rows:
            continue   # nothing to write
        out_path = INIT_DIR / csv_name
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv_mod.DictWriter(fh, fieldnames=schema, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        gen_files.append(str(out_path.relative_to(BASE_DIR)))

    # ── .mas2j ────────────────────────────────────────────────────────────────
    mas2j = _build_mas2j(mas_name, env_class, agent_lines)
    MAS2J_OUT.write_text(mas2j)
    gen_files.append(str(MAS2J_OUT.relative_to(BASE_DIR)))

    return jsonify({"ok": True, "generated_files": gen_files, "mas2j": mas2j})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_fact_block(instance: dict) -> str:
    lines = []
    for attr, value in instance.items():
        attr  = (attr  or "").strip()
        value = (value or "").strip()
        if not attr or not value:
            continue
        if _is_number(value):
            lines.append(f"{attr}({value}).")
        else:
            escaped = value.replace('"', '\\"')
            lines.append(f'{attr}("{escaped}").')
    return "\n".join(lines) + ("\n" if lines else "")

def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False

def _build_mas2j(mas_name: str, env_class: str, agent_lines: list[str]) -> str:
    block = "\n".join(agent_lines)
    return (
        f"/*\n    {mas_name}\n    ---------------------------\n"
        f"    Jason Application File\n"
        f"    Auto-generated by Simulation Configurator\n*/\n\n"
        f"MAS {mas_name} {{\n"
        f"    environment: {env_class}\n\n"
        f"    agents:\n{block}\n\n"
        f"    aslSourcePath: \"./agt\";\n}}\n"
    )


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Simulation Configurator  →  http://localhost:5050")
    print(f"  Base : {BASE_DIR}")
    print(f"  Agt  : {AGT_DIR}")
    app.run(debug=True, port=5050)
