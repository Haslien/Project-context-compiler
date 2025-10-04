# map_structure_selected.py
import os
import json
import argparse
import fnmatch
import glob
from typing import Callable, Iterable, List, Tuple

try:
    import pathspec  # valgfri .gitignore-matching
except Exception:
    pathspec = None


# ---------- helpers delt med main.py ----------

def compile_gitignore_matcher(repo_root: str, extra_patterns: Iterable[str]) -> Callable[[str], bool]:
    gitignore_file = os.path.join(repo_root, ".gitignore")
    patterns: List[str] = []

    if os.path.isfile(gitignore_file):
        try:
            with open(gitignore_file, "r", encoding="utf-8") as f:
                patterns.extend([line.rstrip("\n") for line in f])
        except Exception:
            pass

    for p in extra_patterns or []:
        patterns.append(str(p))

    if pathspec is not None:
        try:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
            def is_ignored(relpath: str) -> bool:
                return spec.match_file(relpath.replace(os.sep, "/"))
            return is_ignored
        except Exception:
            pass

    norm_patterns = []
    for pat in patterns:
        pat = pat.strip()
        if not pat or pat.startswith("#"):
            continue
        if pat.endswith("/"):
            pat = pat + "**"
        norm_patterns.append(pat.replace("\\", "/"))

    def is_ignored(relpath: str) -> bool:
        rel_posix = relpath.replace(os.sep, "/")
        for pat in norm_patterns:
            if fnmatch.fnmatch(rel_posix, pat):
                return True
        return False

    return is_ignored


def expand_files(abs_path: str, requested: List[str], is_ignored: Callable[[str], bool]) -> Tuple[List[str], List[str]]:
    included: List[str] = []
    missing: List[str] = []

    def has_wc(p: str) -> bool:
        return any(w in p for w in ["**", "*", "?"])

    for entry in requested:
        if not entry:
            continue
        entry = entry.strip()
        pattern = entry + "**" if entry.endswith("/") else entry

        if has_wc(pattern):
            glob_pattern = os.path.join(abs_path, pattern)
            matches = glob.glob(glob_pattern, recursive=True)
            file_matches = [m for m in matches if os.path.isfile(m)]
            file_matches.sort()
            if not file_matches:
                missing.append(entry)
                continue
            for full in file_matches:
                rel = os.path.relpath(full, abs_path).replace("\\", "/")
                if not is_ignored(rel):
                    included.append(rel)
        else:
            full = os.path.join(abs_path, entry)
            if os.path.isfile(full):
                rel = entry.replace("\\", "/")
                if not is_ignored(rel):
                    included.append(rel)
            else:
                missing.append(entry)

    seen = set()
    uniq = []
    for r in included:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq, missing


# ---------- bygg minimalt tre kun for valgte ----------

def build_selected_tree(root_abs: str, selected_files: List[str]) -> dict:
    # Normaliser til posix relpaths
    sel = [p.replace("\\", "/") for p in selected_files]

    # Samle nødvendige mapper
    dirs = set()
    for rel in sel:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))

    def make_dir(name): return {"name": name, "type": "dir", "children": {}}
    root_name = os.path.basename(root_abs) or root_abs
    tree = make_dir(root_name)

    for rel in sel:
        parts = rel.split("/")
        node = tree
        for i in range(len(parts) - 1):
            dn = parts[i]
            if dn not in node["children"]:
                node["children"][dn] = make_dir(dn)
            node = node["children"][dn]
        fn = parts[-1]
        node["children"][fn] = {"name": fn, "type": "file"}

    return tree


def render_tree_ascii(tree: dict) -> str:
    """
    Renders som:
    root/
    ├── 📁 dir1/
    │   └── 📄 file.ts
    └── 📄 other.txt
    """
    lines: List[str] = [f'{tree["name"]}/']

    def walk(node: dict, prefix: str):
        items = sorted(node["children"].items(), key=lambda kv: (kv[1]["type"] != "dir", kv[0].lower()))
        total = len(items)
        for idx, (name, child) in enumerate(items):
            is_last = idx == total - 1
            connector = "└── " if is_last else "├── "
            next_prefix = "    " if is_last else "│   "
            if child["type"] == "dir":
                lines.append(f"{prefix}{connector}📁 {name}/")
                walk(child, prefix + next_prefix)
            else:
                lines.append(f"{prefix}{connector}📄 {name}")

    walk(tree, "")
    return "\n".join(lines)


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="Skriv kompakt tre med KUN valgte filer fra JSON.files")
    ap.add_argument("project_json", help="Navn i projects/ eller direkte sti til JSON")
    args = ap.parse_args()

    base_dir = os.path.dirname(__file__)
    cfg_path = args.project_json
    if not os.path.isabs(cfg_path):
        if os.path.sep not in cfg_path and "/" not in cfg_path:
            cfg_path = os.path.join(base_dir, "projects", cfg_path)
        else:
            cfg_path = os.path.join(base_dir, cfg_path)
    if not os.path.isfile(cfg_path):
        raise SystemExit(f"Fant ikke konfigurasjon: {cfg_path}")

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    abs_path = cfg.get("absolute_path", "").strip()
    use_gitignore = cfg.get("use_gitignore", True)
    extra_ignore = cfg.get("ignore", []) or []
    files_list = cfg.get("files", []) or []
    title = cfg.get("title", "").strip()

    if not abs_path or not os.path.isdir(abs_path):
        raise SystemExit(f"absolute_path ugyldig: {abs_path!r}")

    # matcher
    if use_gitignore:
        is_ignored = compile_gitignore_matcher(abs_path, extra_ignore)
    else:
        def _json_only(relpath: str) -> bool:
            rel_posix = relpath.replace("\\", "/")
            for pat in extra_ignore:
                pat = str(pat).replace("\\", "/")
                if pat.endswith("/"):
                    pat = pat + "**"
                if fnmatch.fnmatch(rel_posix, pat):
                    return True
            return False
        is_ignored = _json_only

    # utvid JSON.files til faktiske filer og filtrer mot ignore
    selected_files, missing = expand_files(abs_path, files_list, is_ignored)

    # bygg og render kompakt tre
    tree = build_selected_tree(abs_path, selected_files)
    ascii_tree = render_tree_ascii(tree)

    out_dir = os.path.join(base_dir, "structures")
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(cfg_path))[0]
    out_path = os.path.join(out_dir, f"{base_name}.tree.txt")

    header = []
    header.append(f"# {title or base_name}")
    header.append(f"root: {abs_path}")
    header.append("only selected files are shown, there may be files not listed here, but present in the directory")
    if missing:
        header.append(f"missing_patterns: {missing}")
    header.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write(ascii_tree)
        f.write("\n")

    print(f"Skrev tre til: {out_path}")

if __name__ == "__main__":
    main()
