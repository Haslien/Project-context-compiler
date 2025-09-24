import os
import json
import argparse
import glob
import mimetypes
import subprocess
from typing import Callable, Iterable, List, Tuple, Optional

# Prøv valgfrie avhengigheter, men ikke krev dem
try:
    import pathspec  # for .gitignore-aktig matching
except Exception:  # noqa: PIE786
    pathspec = None

try:
    from PIL import Image  # for bilde-dimensjoner
except Exception:  # noqa: PIE786
    Image = None


GREEN = "✅"
YELLOW = "⚠️"
RED = "❌"

TEXT_EXTENSIONS_HINT = {
    ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".html",
    ".css", ".scss", ".sass", ".yml", ".yaml", ".toml", ".py",
    ".cjs", ".mjs", ".tsconfig", ".graphql", ".gql"
}


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0


def run_ffprobe_duration(path: str) -> Optional[float]:
    """Return duration in seconds using ffprobe if available, else None."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True,
            text=True,
            check=True,
        )
        dur_str = result.stdout.strip()
        if dur_str:
            return float(dur_str)
    except Exception:
        return None
    return None


def human_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def guess_is_text_file(path: str) -> bool:
    """
    Grovt anslag: vurder filendelse og et lett forsøk på å lese som UTF-8.
    Vi vil ikke kaste, bare indikere sannsynlig tekst vs binær.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS_HINT:
        return True
    mime, _ = mimetypes.guess_type(path)
    if mime:
        if mime.startswith("text/"):
            return True
        if mime in ("application/json", "application/xml"):
            return True
    # Siste sjanse: les litt og se om det dekoder
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)
        chunk.decode("utf-8")  # kan kaste UnicodeDecodeError
        return True
    except Exception:
        return False


def get_media_info(path: str) -> Optional[str]:
    """
    Returner en kort streng med medie-info for bilder og video.
    Eksempler:
      - "this is an image 1920x1080 px, 1.2 MB"
      - "this is a video 5.0 GB, 5m 30s"
    Returnerer None dersom ikke bilde/video eller info ikke kan hentes.
    """
    size_bytes = os.path.getsize(path)
    size_str = human_size(size_bytes)

    mime, _ = mimetypes.guess_type(path)
    if not mime:
        return None

    if mime.startswith("image/"):
        dims = None
        if Image is not None:
            try:
                with Image.open(path) as im:
                    dims = f"{im.width}x{im.height} px"
            except Exception:
                dims = None
        if dims:
            return f"this is an image {dims}, {size_str}"
        return f"this is an image, {size_str}"

    if mime.startswith("video/"):
        dur = run_ffprobe_duration(path)
        if dur is not None:
            return f"this is a video {size_str}, {human_duration(dur)}"
        return f"this is a video, {size_str}"

    return None


def compile_gitignore_matcher(repo_root: str, extra_patterns: Iterable[str]) -> Callable[[str], bool]:
    """
    Bygger en funksjon is_ignored(relpath) -> bool.
    Bruker pathspec for ekte .gitignore hvis tilgjengelig. Ellers en enkel glob-basert fallback.
    """
    gitignore_file = os.path.join(repo_root, ".gitignore")
    patterns: List[str] = []

    # Les .gitignore om den finnes
    if os.path.isfile(gitignore_file):
        try:
            with open(gitignore_file, "r", encoding="utf-8") as f:
                patterns.extend([line.rstrip("\n") for line in f])
            print(f"{GREEN} Fant .gitignore i {gitignore_file}")
        except Exception as e:
            print(f"{YELLOW} Klarte ikke lese .gitignore: {e}")

    # Legg til ekstra mønstre fra JSON
    for p in extra_patterns:
        patterns.append(str(p))

    # Pathspec-variant
    if pathspec is not None:
        try:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
            def is_ignored(relpath: str) -> bool:
                # PathSpec forventer posix-paths
                rel_posix = relpath.replace(os.sep, "/")
                return spec.match_file(rel_posix)
            return is_ignored
        except Exception as e:
            print(f"{YELLOW} Pathspec feilet, faller tilbake til enkel glob-matching: {e}")

    # Enkel fallback: sjekk mot fnmatch for hvert mønster
    import fnmatch
    norm_patterns = []
    for pat in patterns:
        pat = pat.strip()
        if not pat or pat.startswith("#"):
            continue
        # .gitignore katalogsyntaks: sørg for at suffikset /** for katalognavn
        if pat.endswith("/"):
            pat = pat + "**"
        # standardiser til posix
        pat = pat.replace("\\", "/")
        norm_patterns.append(pat)

    def is_ignored(relpath: str) -> bool:
        rel_posix = relpath.replace(os.sep, "/")
        for pat in norm_patterns:
            if fnmatch.fnmatch(rel_posix, pat):
                return True
        return False

    return is_ignored


def expand_files(abs_path: str, requested: List[str], is_ignored: Callable[[str], bool]) -> Tuple[List[str], List[str]]:
    """
    Tar ønskede paths/patterns og returnerer:
      included_files: liste over faktiske filer som skal behandles
      missing_items:  liste over paths som ikke ga treff
    Bevarer bakoverkompatibilitet: rene filbaner uten wildcards prøves direkte.
    """
    included: List[str] = []
    missing: List[str] = []

    def want_recursive(p: str) -> bool:
        return any(w in p for w in ["**", "*", "?"])

    for entry in requested:
        entry = entry.strip()
        if not entry:
            continue

        # Tolke "dir/*" og "dir/" litt vennlig: "dir/" -> "dir/**"
        pattern = entry
        if entry.endswith("/"):
            pattern = entry + "**"
        elif entry.endswith("/*"):
            # "dir/*" inkluderer bare direkte underfiler
            pattern = entry

        has_wildcards = want_recursive(pattern)

        if has_wildcards:
            # Glob relativt til root
            glob_pattern = os.path.join(abs_path, pattern)
            # Tillat rekursjon når ** brukes
            recursive = "**" in pattern
            matches = glob.glob(glob_pattern, recursive=True)
            # Filtrer vekk kataloger, behold filer
            file_matches = [m for m in matches if os.path.isfile(m)]

            # Sortert for deterministisk output
            file_matches.sort()
            if not file_matches:
                print(f"{YELLOW} Ingen treff for mønster: {entry}")
                missing.append(entry)
                continue

            found_any = False
            for full in file_matches:
                rel = os.path.relpath(full, abs_path)
                if is_ignored(rel):
                    print(f"{YELLOW} Ignorerer pga. ignore-regler: {rel}")
                    continue
                included.append(rel)
                found_any = True
            if found_any:
                print(f"{GREEN} Utvidet mønster: {entry} -> {len([p for p in file_matches if not is_ignored(os.path.relpath(p, abs_path))])} filer")
            else:
                print(f"{YELLOW} Alle treff ble ignorert for mønster: {entry}")

        else:
            # Bakoverkompatibel enkeltfil
            full = os.path.join(abs_path, entry)
            if os.path.isfile(full):
                rel = entry
                if is_ignored(rel):
                    print(f"{YELLOW} Ignorerer pga. ignore-regler: {rel}")
                else:
                    included.append(rel)
                    print(f"{GREEN} Fant fil: {rel}")
            else:
                print(f"{RED} Fant ikke fil: {entry}")
                missing.append(entry)

    # Fjern duplikater, men bevar rekkefølgen
    seen = set()
    unique_included = []
    for rel in included:
        if rel not in seen:
            seen.add(rel)
            unique_included.append(rel)

    return unique_included, missing


def compile_project(config_filename: str):
    """
    Forbedret kompilator:
      - Støtter *.glob og rekursive mønstre
      - Leser .gitignore og JSON.ignore
      - Rik logging i konsoll
      - Skriver medie-info for binærfiler
    Bakoverkompatibel med eksisterende JSON-skjema.
    """

    # ------------------------
    # 1) Locate and load the JSON
    # ------------------------
    base_dir = os.path.dirname(__file__)
    config_path = os.path.join(base_dir, "projects", config_filename)
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Could not find configuration file: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ------------------------
    # 2) Extract fields (optional felt beholdes som før)
    # ------------------------
    title = data.get("title", "").strip()
    abs_path = data.get("absolute_path", "").strip()
    start_prompt = data.get("start_prompt", "").strip()
    start_text_template = data.get("start_text", "").strip()
    stop_text_template = data.get("stop_text", "").strip()
    files_list = data.get("files", [])

    # Nye valgfrie felt
    use_gitignore = data.get("use_gitignore", True)
    extra_ignore_patterns = data.get("ignore", []) or []

    if not abs_path:
        raise ValueError("The 'absolute_path' field must not be empty.")
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(f"Absolute path does not exist: {abs_path}")
    if not isinstance(files_list, list) or len(files_list) == 0:
        raise ValueError("The 'files' array must contain at least one relative path.")

    # ------------------------
    # 3) Prepare output
    # ------------------------
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(config_filename))[0]
    output_filename = f"{base_name}.txt"
    output_path = os.path.join(output_dir, output_filename)

    # ------------------------
    # 3.5) Build ignore matcher
    # ------------------------
    ignore_patterns = extra_ignore_patterns if isinstance(extra_ignore_patterns, list) else []
    is_ignored: Callable[[str], bool]
    if use_gitignore:
        is_ignored = compile_gitignore_matcher(abs_path, ignore_patterns)
    else:
        # Minimal matcher som kun tar hensyn til JSON.ignore
        def _json_only(relpath: str) -> bool:
            import fnmatch
            rel_posix = relpath.replace(os.sep, "/")
            for pat in ignore_patterns:
                pat = str(pat).replace("\\", "/")
                if pat.endswith("/"):
                    pat = pat + "**"
                if fnmatch.fnmatch(rel_posix, pat):
                    return True
            return False
        is_ignored = _json_only

    # ------------------------
    # 4) Expand files
    # ------------------------
    print(f"\nStarter kompilering for prosjekt-root: {abs_path}")
    included_files, missing_items = expand_files(abs_path, files_list, is_ignored)
    print(f"\nOppsummering av utvalg: {len(included_files)} filer inkludert, {len(missing_items)} oppføringer uten treff.")

    # ------------------------
    # 5) Write output file
    # ------------------------
    files_written = 0
    with open(output_path, "w", encoding="utf-8") as out_file:
        if start_prompt:
            out_file.write(start_prompt + "\n\n")

        if title:
            out_file.write(f"Project: {title}\n\n")

        for rel_path in included_files:
            full_path = os.path.join(abs_path, rel_path)

            # 5.a) start_text
            if start_text_template:
                intro = start_text_template.replace("{file}", rel_path) if "{file}" in start_text_template else f'{start_text_template} "{rel_path}"'
                out_file.write(intro + "\n")

            # 5.b) innhold eller medie-info
            try:
                if guess_is_text_file(full_path):
                    with open(full_path, "r", encoding="utf-8") as code_file:
                        content = code_file.read()
                    out_file.write(content)
                    print(f"{GREEN} Skrev tekstinnhold: {rel_path}")
                else:
                    media_info = get_media_info(full_path)
                    if media_info:
                        out_file.write(f"*** {media_info} ***\n")
                        print(f"{GREEN} Skrev medie-info: {rel_path} -> {media_info}")
                    else:
                        size_str = human_size(os.path.getsize(full_path))
                        out_file.write(f"*** binary file, {size_str} ***\n")
                        print(f"{GREEN} Skrev binær-info: {rel_path} -> {size_str}")
            except Exception as e:
                out_file.write(f"*** ERROR: Could not read file: {full_path}\nReason: {e} ***\n")
                print(f"{RED} Feil ved lesing: {rel_path} -> {e}")

            # 5.c) stop_text
            if stop_text_template:
                footer = stop_text_template.replace("{file}", rel_path) if "{file}" in stop_text_template else stop_text_template
                out_file.write(footer)

            out_file.write("\n\n")
            files_written += 1

    print(f"\n{GREEN} Compilation complete! Output written to: {output_path}")
    print(f"{GREEN} Filer skrevet: {files_written}")
    if missing_items:
        print(f"{YELLOW} Oppføringer uten treff: {len(missing_items)}")
        for m in missing_items:
            print(f"   {YELLOW} {m}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect file contents based on a JSON configuration, with optional start_prompt, start_text, stop_text, glob support and ignore rules."
    )
    parser.add_argument(
        "project_json",
        type=str,
        help='Name of the JSON file in projects/ (for eksempel my-project.json)'
    )
    args = parser.parse_args()

    try:
        compile_project(args.project_json)
    except Exception as e:
        print(f"{RED} An error occurred: {e}")
