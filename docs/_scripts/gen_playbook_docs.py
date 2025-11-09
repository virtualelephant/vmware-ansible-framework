# docs/_scripts/gen_playbook_docs.py
from pathlib import Path
import os, re, yaml
from typing import Dict, Any, List

# Try mkdocs_gen_files (during mkdocs build); fall back to writing into docs/
try:
    import mkdocs_gen_files as gen  # type: ignore
except Exception:
    gen = None

ROOT = Path.cwd()                       # MkDocs runs from project root
DOCS_DIR = ROOT / "docs"
PLAYBOOKS_DIR = ROOT / "ansible" / "playbooks"

DEST_DIR = "generated/ansible/playbooks"     # where individual md pages go
SECTION_MD = "generated/ansible/playbooks.md"  # list/section page

WRITE_TO_DISK = os.getenv("WRITE_TO_DISK", "0") == "1"

DOCBLOCK_RE = re.compile(r"^#\s*---\s*\n(?P<body>(?:#.*\n)+?)#\s*---", re.MULTILINE)
SAFE_ID_RE_BAD = re.compile(r"[^a-z0-9._-]+")
SAFE_ID_RE_DASH = re.compile(r"-{2,}")

def safe_id(s: str) -> str:
    s = s.strip().lower()
    s = SAFE_ID_RE_BAD.sub("-", s)
    s = SAFE_ID_RE_DASH.sub("-", s).strip("-")
    return s or "playbook"

def write(rel_path: str, content: str) -> None:
    if gen is not None:
        with gen.open(rel_path, "w") as f:
            f.write(content)
    if gen is None or WRITE_TO_DISK:
        out = DOCS_DIR / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

def parse_docblock(text: str) -> Dict[str, Any]:
    m = DOCBLOCK_RE.search(text)
    if not m:
        return {}
    body = m.group("body")
    cleaned = "\n".join(
        line[2:] if line.startswith("# ")
        else line[1:] if line.startswith("#")
        else line
        for line in body.splitlines()
    )
    try:
        data = yaml.safe_load(cleaned)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def extract_task_names(play: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for t in (play.get("tasks") or []):
        if isinstance(t, dict):
            names.append(t.get("name") or "(unnamed task)")
    return names

def build_playbook_page(yml: Path, meta: Dict[str, Any], plays: List[Dict[str, Any]]) -> str:
    title = meta.get("title") or yml.stem.replace("_", " ").title()
    overview = (meta.get("overview") or meta.get("description") or "").strip()
    lines = [f"# {title}", ""]
    if overview:
        lines += [overview, ""]
    lines += [f"**Source:** `{yml.relative_to(ROOT)}`", ""]

    all_task_names: List[str] = []
    for p in plays:
        all_task_names.extend(extract_task_names(p))
    if all_task_names:
        lines += ["## Tasks", *[f"- {n}" for n in all_task_names], ""]

    return "\n".join(lines).rstrip() + "\n"

def main() -> None:
    # Gather playbooks
    ymls = sorted(PLAYBOOKS_DIR.rglob("*.yml")) + sorted(PLAYBOOKS_DIR.rglob("*.yaml"))

    # Build individual pages and collect section entries
    section_lines = ["# Playbooks\n\n"]
    for yml in ymls:
        raw = yml.read_text(encoding="utf-8", errors="replace")
        meta = parse_docblock(raw)
        data = load_yaml(yml) or []
        plays = data if isinstance(data, list) else [data]

        doc_id = safe_id(meta.get("id", yml.stem))
        title = meta.get("title") or yml.stem.replace("_", " ").title()

        # Write individual page
        page_md_path = f"{DEST_DIR}/{doc_id}.md"
        write(page_md_path, build_playbook_page(yml, meta, plays))

        # Link from section page using SAME-FOLDER relative URL
        # (playbooks.md is in generated/ansible/, individual pages in generated/ansible/playbooks/)
        section_lines.append(f"- [{title}](playbooks/{doc_id}.md)\n")

    # Prefer directory-URLs? Flip to: section_lines.append(f"- [{title}](playbooks/{doc_id}/)\n")
    # If you do that, also set use_directory_urls: true (default) and MkDocs will route to /.../<doc_id>/

    # Write section page once
    write(SECTION_MD, "".join(section_lines))

    # Optional sidebar helper
    summary = ["# Summary\n\n", "* [Home](index.md)\n", "* [Playbooks](generated/ansible/playbooks.md)\n"]
    write("SUMMARY.md", "".join(summary))

if __name__ == "__main__":
    main()
