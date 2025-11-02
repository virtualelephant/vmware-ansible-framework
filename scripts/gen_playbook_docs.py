from pathlib import Path
import re, yaml
import mkdocs_gen_files as gen

ROOT = Path(__file__).resolve().parents[2]  # repo root
PLAYBOOKS_DIR = ROOT / "ansible" / "playbooks"
DEST_DIR = "generated/ansible/playbooks"

DOCBLOCK_RE = re.compile(r"^#\s*---\s*\n(?P<body>(?:#.*\n)+?)#\s*---", re.MULTILINE)

def parse_docblock(text: str):
    m = DOCBLOCK_RE.search(text)
    if not m:
        return {}
    raw = "\n".join([line[2:] for line in m.group("body").splitlines() if line.startswith("# ")])
    try:
        data = yaml.safe_load(raw) or {}
        return data.get("docmeta", {})
    except Exception:
        return {}

def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text())
    except Exception:
        return None

def extract_tasks(play):
    tasks = play.get("tasks", [])
    out = []
    for t in tasks:
        if isinstance(t, dict):
            name = t.get("name") or "(unnamed task)"
            # first key that looks like a module name (exclude 'name','register','loop','vars', etc.)
            module = next((k for k in t.keys() if k not in ("name","register","when","loop","vars","tags","delegate_to","with_items")), None)
            out.append({
                "name": name,
                "module": module or "meta/other",
                "tags": t.get("tags", []),
                "when": t.get("when"),
                "register": t.get("register"),
            })
    return out

def render_markdown(meta, path, play):
    title = meta.get("title") or (play.get("name") or path.stem)
    vars_files = play.get("vars_files", [])
    hosts = play.get("hosts")
    become = play.get("become")
    gather = play.get("gather_facts")
    tasks = extract_tasks(play)

    lines = []
    lines.append(f"# {title}\n")
    if meta.get("summary"):
        lines.append(meta["summary"] + "\n")

    lines.append("## How it works\n")
    lines.append(f"- **Hosts:** `{hosts}`  \n- **gather_facts:** `{gather}`  \n- **become:** `{bool(become)}`\n")
    if vars_files:
        lines.append(f"- **vars_files:** `{', '.join(vars_files)}`\n")

    if meta.get("prerequisites"):
        lines.append("## Prerequisites\n")
        for p in meta["prerequisites"]:
            lines.append(f"- {p}")
        lines.append("")

    if meta.get("inputs_required") or meta.get("inputs_optional"):
        lines.append("## Inputs\n")
        if meta.get("inputs_required"):
            lines.append("**Required**")
            for i in meta["inputs_required"]:
                lines.append(f"- {i}")
        if meta.get("inputs_optional"):
            lines.append("\n**Optional**")
            for i in meta["inputs_optional"]:
                lines.append(f"- {i}")
        lines.append("")

    if meta.get("outputs"):
        lines.append("## Outputs\n")
        for o in meta["outputs"]:
            lines.append(f"- {o}")
        lines.append("")

    lines.append("## Tasks\n")
    lines.append("| # | Task | Module | Tags | When |")
    lines.append("|---:|---|---|---|---|")
    for idx, t in enumerate(tasks, 1):
        tags = ", ".join(t["tags"]) if t["tags"] else "—"
        when = (t["when"] if isinstance(t["when"], str) else "—") if t["when"] else "—"
        lines.append(f"| {idx} | {t['name']} | `{t['module']}` | `{tags}` | `{when}` |")
    lines.append("")

    if meta.get("examples"):
        lines.append("## Examples\n")
        for ex in meta["examples"]:
            lines.append(f"**{ex.get('name','Example')}**")
            lines.append("\n```bash")
            lines.append(ex["cmd"])
            lines.append("```\n")

    if meta.get("notes"):
        lines.append("## Notes\n")
        for n in meta["notes"]:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)

def main():
    for yml in sorted(PLAYBOOKS_DIR.rglob("*.yml")):
        text = yml.read_text()
        docmeta = parse_docblock(text)
        data = load_yaml(yml) or []
        plays = data if isinstance(data, list) else [data]
        for play in plays:
            md = render_markdown(docmeta, yml, play)
            # choose target path
            doc_id = docmeta.get("id", yml.stem)
            dest = f"{DEST_DIR}/{doc_id}.md"
            with gen.open(dest, "w") as f:
                f.write(md)

if __name__ == "__main__":
    main()
