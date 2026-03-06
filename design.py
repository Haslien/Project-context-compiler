# design.py
from __future__ import annotations
import os
import json
import argparse
import fnmatch
import glob
import mimetypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Valgfri støtte for .gitignore
try:
    import pathspec
except Exception:
    pathspec = None

# ---------------- Utils ----------------

TEXT_EXTENSIONS_HINT = {
    ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".html",
    ".css", ".scss", ".sass", ".yml", ".yaml", ".toml", ".py",
    ".cjs", ".mjs", ".graphql", ".gql"
}

def guess_is_text_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS_HINT:
        return True
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("text/"):
        return True
    if mime in ("application/json", "application/xml"):
        return True
    try:
        with open(path, "rb") as f:
            f.read(2048).decode("utf-8")
        return True
    except Exception:
        return False

def compile_gitignore_matcher(repo_root: str, extra_patterns):
    patterns = []
    gi = os.path.join(repo_root, ".gitignore")
    if os.path.isfile(gi):
        try:
            with open(gi, "r", encoding="utf-8") as f:
                patterns.extend([line.rstrip("\n") for line in f])
        except Exception:
            pass
    if extra_patterns:
        patterns.extend([str(p) for p in extra_patterns])

    if pathspec is not None:
        try:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
            def is_ignored(relpath: str) -> bool:
                return spec.match_file(relpath.replace(os.sep, "/"))
            return is_ignored
        except Exception:
            pass

    norm = []
    for p in patterns:
        p = p.strip()
        if not p or p.startswith("#"):
            continue
        if p.endswith("/"):
            p = p + "**"
        norm.append(p.replace("\\", "/"))

    def is_ignored(relpath: str) -> bool:
        rp = relpath.replace(os.sep, "/")
        for pat in norm:
            if fnmatch.fnmatch(rp, pat):
                return True
        return False

    return is_ignored

def rel_from(root: str, abspath: str) -> str:
    return os.path.relpath(abspath, root).replace("\\", "/")

def is_within(child_rel: str, parent_rel: str) -> bool:
    parent_rel = parent_rel.rstrip("/")
    if child_rel == parent_rel:
        return True
    return child_rel.startswith(parent_rel + "/")

# ---------------- App ----------------

class DesignerApp(tk.Tk):
    """
    Lazy file browser som ikke låser UI:
      - Shift-klikk syklus: None -> include -> exclude -> None
      - Ignorerte elementer gråes ut og kan ikke velges
      - Mapper utvides på forespørsel
    """
    def __init__(self, initial_config_path: str | None):
        super().__init__()
        self.title("JSON Compile Designer")
        self.geometry("1300x780")
        self.minsize(960, 600)

        self.config_path = initial_config_path
        self.config_data = self._empty_config()
        self.repo_root = ""
        self.use_gitignore_var = tk.BooleanVar(value=True)
        self.title_var = tk.StringVar(value="")
        self.abs_path_var = tk.StringVar(value="")
        self.start_prompt_var = tk.StringVar(value="")
        self.start_text_var = tk.StringVar(value='-- Begin file "{file}" --')
        self.stop_text_var = tk.StringVar(value='\n-- End file "{file}" --')

        # relpath -> "include" | "exclude" | None
        self.states: dict[str, str | None] = {}
        self.is_ignored = lambda _p: False  # settes ved refresh

        self._build_ui()

        if self.config_path and os.path.isfile(self.config_path):
            self._load_config(self.config_path)
        elif self.config_path and not os.path.isabs(self.config_path):
            alt = os.path.join(os.path.dirname(__file__), "projects", self.config_path)
            if os.path.isfile(alt):
                self._load_config(alt)

    # ---------- UI ----------

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew")

        # Venstre
        left = ttk.Frame(paned)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        toolbar = ttk.Frame(left)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        toolbar.grid_columnconfigure(8, weight=1)

        ttk.Button(toolbar, text="Åpne JSON", command=self._open_json).grid(row=0, column=0, padx=3)
        ttk.Button(toolbar, text="Lagre JSON", command=self._save_json).grid(row=0, column=1, padx=3)
        ttk.Button(toolbar, text="Lagre som", command=self._save_json_as).grid(row=0, column=2, padx=3)
        ttk.Separator(toolbar, orient="vertical").grid(row=0, column=3, sticky="ns", padx=8)
        ttk.Button(toolbar, text="Velg prosjektmappe", command=self._choose_root).grid(row=0, column=4, padx=3)
        ttk.Button(toolbar, text="Oppdater tre", command=self._refresh_tree).grid(row=0, column=5, padx=3)
        ttk.Label(toolbar, text="Shift-klikk: inkluder -> ekskluder -> nullstill").grid(row=0, column=7, padx=8)

        tree_wrap = ttk.Frame(left)
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_wrap, columns=("rel",), show="tree")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        # Farger
        self.tree.tag_configure("include", background="#e7f8ec")
        self.tree.tag_configure("exclude", background="#fde7e7")
        self.tree.tag_configure("ignored", foreground="#8a8a8a")

        # Hendelser
        self.tree.bind("<<TreeviewOpen>>", self._on_open_node)
        self.tree.bind("<Button-1>", self._on_click_tree)

        paned.add(left, weight=3)

        # Høyre
        right = ttk.Notebook(paned)
        paned.add(right, weight=4)

        cfg = ttk.Frame(right)
        right.add(cfg, text="Konfig")
        cfg.grid_columnconfigure(1, weight=1)

        ttk.Label(cfg, text="Tittel").grid(row=0, column=0, sticky="w", padx=8, pady=(12,4))
        ttk.Entry(cfg, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", padx=(0,8), pady=(12,4))

        ttk.Label(cfg, text="Absolute path").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(cfg, textvariable=self.abs_path_var).grid(row=1, column=1, sticky="ew", padx=(0,8), pady=4)
        ttk.Button(cfg, text="Bla gjennom", command=self._browse_abs_path).grid(row=1, column=2, padx=3)
        ttk.Button(cfg, text="Bruk aktiv mappe", command=self._set_abs_to_repo).grid(row=1, column=3, padx=3)

        ttk.Label(cfg, text="Start prompt").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(cfg, textvariable=self.start_prompt_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=(0,8), pady=4)

        ttk.Label(cfg, text="Start text").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(cfg, textvariable=self.start_text_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=(0,8), pady=4)

        ttk.Label(cfg, text="Stop text").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(cfg, textvariable=self.stop_text_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=(0,8), pady=4)

        ttk.Checkbutton(cfg, text="Bruk .gitignore", variable=self.use_gitignore_var, command=self._refresh_tree).grid(row=5, column=1, sticky="w", padx=(0,8), pady=(8,4))

        ttk.Label(cfg, text="Ekstra ignore-mønstre").grid(row=6, column=0, sticky="nw", padx=8, pady=(8,4))
        self.ignore_box = tk.Text(cfg, height=8)
        self.ignore_box.grid(row=6, column=1, columnspan=3, sticky="nsew", padx=(0,8), pady=(8,8))
        cfg.grid_rowconfigure(6, weight=1)

        prev = ttk.Frame(right)
        right.add(prev, text="Utvalg og preview")
        prev.grid_columnconfigure(0, weight=1)
        prev.grid_rowconfigure(1, weight=1)

        topbar = ttk.Frame(prev)
        topbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(topbar, text="Generer mønstre", command=self._preview_patterns).pack(side=tk.LEFT, padx=3)
        ttk.Button(topbar, text="Skriv til JSON.files", command=self._apply_patterns_to_json).pack(side=tk.LEFT, padx=3)

        self.pattern_list = tk.Listbox(prev)
        self.pattern_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))

        self.status = tk.StringVar(value="Klar")
        ttk.Label(self, textvariable=self.status, anchor="w").grid(row=1, column=0, sticky="ew", padx=8, pady=(0,8))

    # ---------- Tree lazy loading ----------

    def _choose_root(self):
        d = filedialog.askdirectory(title="Velg prosjektmappe")
        if not d:
            return
        self.repo_root = d
        self.status.set(f"Root: {self.repo_root}")
        if not self.abs_path_var.get():
            self.abs_path_var.set(self.repo_root)
        self._refresh_tree()

    def _browse_abs_path(self):
        d = filedialog.askdirectory(title="Velg absolute_path for prosjektet")
        if not d:
            return
        self.abs_path_var.set(d)
        self.repo_root = d
        self.status.set(f"Absolute path satt til: {d}")
        self._refresh_tree()

    def _set_abs_to_repo(self):
        if self.repo_root:
            self.abs_path_var.set(self.repo_root)

    def _refresh_tree(self, *_):
        self.tree.delete(*self.tree.get_children())
        if not self.repo_root or not os.path.isdir(self.repo_root):
            return

        ignores_raw = [ln.strip() for ln in self.ignore_box.get("1.0", tk.END).splitlines() if ln.strip()]
        self.is_ignored = compile_gitignore_matcher(self.repo_root, ignores_raw) if self.use_gitignore_var.get() else (lambda _p: False)

        root_rel = "."
        root_id = self.tree.insert("", "end", text=os.path.basename(self.repo_root) or self.repo_root, values=(root_rel,))
        self.tree.item(root_id, open=False)
        self.tree.insert(root_id, "end", text="loading", values=("__DUMMY__",), tags=("dummy",))
        self.status.set("Treet er klart. Åpne mapper for å laste innhold.")

    def _on_open_node(self, _event):
        iid = self.tree.focus()
        vals = self.tree.item(iid, "values")
        if not vals:
            return
        rel = vals[0]
        # Har vi dummy-barn
        children = self.tree.get_children(iid)
        if not children:
            return
        if "dummy" not in self.tree.item(children[0], "tags"):
            return
        # Fjern dummy og last ekte barn
        self.tree.delete(children[0])
        if rel == ".":
            parent_abs = self.repo_root
        else:
            parent_abs = os.path.join(self.repo_root, rel.replace("/", os.sep))
        self._load_children(iid, parent_abs)

    def _load_children(self, parent_id: str, parent_abs: str):
        try:
            with os.scandir(parent_abs) as it:
                entries = sorted(it, key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        except Exception:
            entries = []

        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except Exception:
                is_dir = False
            if is_dir and os.path.islink(entry.path):
                continue  # ikke følg symlenker
            rel = rel_from(self.repo_root, entry.path)
            txt = entry.name
            tags = []
            if self.is_ignored(rel):
                tags.append("ignored")
            st = self.states.get(rel)
            if st == "include":
                tags.append("include")
            elif st == "exclude":
                tags.append("exclude")
            iid = self.tree.insert(parent_id, "end", text=txt, values=(rel,), tags=tuple(tags))
            if is_dir and not self.is_ignored(rel):
                # lazy child
                self.tree.insert(iid, "end", text="loading", values=("__DUMMY__",), tags=("dummy",))

    # ---------- Interaksjon ----------

    def _on_click_tree(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "tree":
            return
        element = self.tree.identify("element", event.x, event.y)
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if element in ("tree.expander", "Treeitem.button"):
            return
        # Shift for status
        if event.state & 0x0001:
            rel = self.tree.set(iid, "rel")
            if not rel or rel == "__DUMMY__":
                return
            if self.is_ignored(rel):
                self.status.set("Elementet er ignorert og kan ikke velges")
                return
            cur = self.states.get(rel)
            new = "include" if cur is None else ("exclude" if cur == "include" else None)
            self.states[rel] = new
            # Propager til allerede lastede barn
            self._set_state_recursive_loaded(iid, new)
            # Propager til filsystem for ikke-lastede barn
            abs_path = os.path.join(self.repo_root, rel.replace("/", os.sep))
            if os.path.isdir(abs_path):
                self._set_state_recursive_fs(abs_path, new)
            # Oppdater tag for valgt node
            self._apply_state_tag(iid, rel)
            self.status.set(f"{rel}: {new or 'ingen'}")
            return "break"

    def _apply_state_tag(self, iid: str, rel: str):
        tags = [t for t in self.tree.item(iid, "tags") if t not in ("include", "exclude")]
        st = self.states.get(rel)
        if st == "include":
            tags.append("include")
        elif st == "exclude":
            tags.append("exclude")
        self.tree.item(iid, tags=tuple(tags))

    def _set_state_recursive_loaded(self, iid: str, new: str | None):
        for c in self.tree.get_children(iid):
            rel = self.tree.set(c, "rel")
            if rel and rel != "__DUMMY__" and not self.is_ignored(rel):
                self.states[rel] = new
                self._apply_state_tag(c, rel)
                self._set_state_recursive_loaded(c, new)

    def _set_state_recursive_fs(self, abs_dir: str, new: str | None):
        try:
            with os.scandir(abs_dir) as it:
                for e in it:
                    r = rel_from(self.repo_root, e.path)
                    if self.is_ignored(r):
                        continue
                    self.states[r] = new
                    if e.is_dir(follow_symlinks=False) and not os.path.islink(e.path):
                        self._set_state_recursive_fs(e.path, new)
        except Exception:
            pass

    # ---------- Mønstergenerering ----------

    def _collect_patterns(self) -> list[str]:
        if not self.repo_root:
            return []
        includes = {rel for rel, st in self.states.items() if st == "include"}
        excludes = {rel for rel, st in self.states.items() if st == "exclude"}

        patterns: list[str] = []
        for rel in sorted(includes):
            abs_path = os.path.join(self.repo_root, rel.replace("/", os.sep))
            if self.is_ignored(rel):
                continue
            if os.path.isdir(abs_path):
                patterns.append(rel.rstrip("/") + "/**")
            else:
                patterns.append(rel)

        expanded_files: set[str] = set()
        for pat in patterns:
            glob_pat = os.path.join(self.repo_root, pat)
            for m in glob.glob(glob_pat, recursive=True):
                if os.path.isfile(m):
                    r = rel_from(self.repo_root, m)
                    if not self.is_ignored(r):
                        expanded_files.add(r)

        to_remove: set[str] = set()
        for r in expanded_files:
            if any(is_within(r, ex) for ex in excludes):
                to_remove.add(r)
        expanded_files.difference_update(to_remove)

        return sorted(expanded_files)

    def _preview_patterns(self):
        pats = self._collect_patterns()
        self.pattern_list.delete(0, tk.END)
        for p in pats:
            self.pattern_list.insert(tk.END, p)
        self.status.set(f"{len(pats)} elementer i preview")

    def _apply_patterns_to_json(self):
        pats = self._collect_patterns()
        if not pats:
            messagebox.showinfo("Info", "Ingen mønstre å skrive. Sett noen inkluder og prøv igjen.")
            return
        self._sync_form_to_config()
        self.config_data["files"] = pats
        messagebox.showinfo("OK", f"Skrev {len(pats)} elementer til JSON.files. Husk å lagre.")

    # ---------- JSON I/O ----------

    def _empty_config(self):
        return {
            "title": "",
            "absolute_path": "",
            "start_prompt": "",
            "start_text": '-- Begin file "{file}" --',
            "stop_text": '\n-- End file "{file}" --\n',
            "files": [],
            "use_gitignore": True,
            "ignore": []
        }

    def _open_json(self):
        p = filedialog.askopenfilename(
            title="Åpne JSON",
            filetypes=[("JSON files", "*.json")],
            initialdir=os.path.join(os.path.dirname(__file__), "projects")
        )
        if p:
            self._load_config(p)

    def _load_config(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = {**self._empty_config(), **data}
            if "start_prompt" not in cfg and "start_prompt_" in cfg:
                cfg["start_prompt"] = cfg.get("start_prompt_", "")
            self.config_path = path
            self.config_data = cfg

            self.title_var.set(cfg.get("title", ""))
            self.abs_path_var.set(cfg.get("absolute_path", ""))
            self.start_prompt_var.set(cfg.get("start_prompt", ""))
            self.start_text_var.set(cfg.get("start_text", ""))
            self.stop_text_var.set(cfg.get("stop_text", ""))
            self.use_gitignore_var.set(bool(cfg.get("use_gitignore", True)))

            self.ignore_box.delete("1.0", tk.END)
            for ptn in cfg.get("ignore", []):
                self.ignore_box.insert(tk.END, f"{ptn}\n")

            # Forhåndsmerk include-states basert på files
            self.states.clear()
            abs_path = cfg.get("absolute_path", "")
            if abs_path and os.path.isdir(abs_path):
                self.repo_root = abs_path
                self._refresh_tree()
                for entry in cfg.get("files", []):
                    entry = entry.rstrip("/")
                    self.states[entry] = "include"
                # Merk root som åpen og last første nivå
                root_id = self.tree.get_children("")[0]
                self.tree.item(root_id, open=True)
                self._on_open_node(None)
            else:
                self.repo_root = ""
                self.status.set("Hint: velg prosjektmappe eller bla til absolute_path")

            self.status.set(f"Lastet {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Feil", f"Klarte ikke lese JSON\n{e}")

    def _save_json(self):
        if not self.config_path:
            return self._save_json_as()
        self._sync_form_to_config()
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            self.status.set(f"Lagret {self.config_path}")
        except Exception as e:
            messagebox.showerror("Feil", f"Klarte ikke lagre\n{e}")

    def _save_json_as(self):
        p = filedialog.asksaveasfilename(
            title="Lagre JSON som",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialdir=os.path.join(os.path.dirname(__file__), "projects")
        )
        if not p:
            return
        self.config_path = p
        self._save_json()

    def _sync_form_to_config(self):
        cfg = self.config_data
        cfg["title"] = self.title_var.get().strip()
        cfg["absolute_path"] = self.abs_path_var.get().strip()
        cfg["start_prompt"] = self.start_prompt_var.get()
        cfg["start_text"] = self.start_text_var.get()
        cfg["stop_text"] = self.stop_text_var.get()
        cfg["use_gitignore"] = bool(self.use_gitignore_var.get())
        cfg["ignore"] = [ln.strip() for ln in self.ignore_box.get("1.0", tk.END).splitlines() if ln.strip()]

# ---------- Entry ----------

def main():
    parser = argparse.ArgumentParser(description="Visual designer for JSON-basert filkompilering")
    parser.add_argument("json_path", nargs="?", help="projects/my-project.json eller annen sti")
    args = parser.parse_args()

    app = DesignerApp(args.json_path)
    app.mainloop()

if __name__ == "__main__":
    main()
