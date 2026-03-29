---
name: new-project-config
description: Creates a new Project Context Compiler JSON config file for a given directory path. Use when the user says "lag prosjektfil for [sti]", "opprett prosjektfil", "make a project config for X", "create context config for X", or wants to compile context for a new project. Handles language-specific exclusions (TypeScript, JavaScript, Python, Go, Rust, Java), reads .gitignore, and supports optional layer scoping (api, frontend, backend, db, etc.).
---

# New Project Config

Creates a `.json` config file in `projects/` for the Project Context Compiler, by intelligently mapping a target project directory.

## Steps

### 1. Parse the request

Extract from the user's message:
- **`target_dir`**: Absolute path to the target project directory. Ask if not provided.
- **`scope`** (optional): A layer like `api`, `frontend`, `backend`, `web`, `client`, `server`, `db`. Use if user mentions one.
- **`config_name`** (optional): Desired output filename. Default: derive from the target directory base name.

### 2. Explore the target directory

Use the tools to list the top-level contents of `target_dir` and check for language/framework markers:

| File/Dir present | Detected stack |
|---|---|
| `package.json` + `tsconfig.json` | TypeScript / Node |
| `package.json` (no tsconfig) | JavaScript / Node |
| `requirements.txt` / `pyproject.toml` / `setup.py` | Python |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `pom.xml` / `build.gradle` | Java / Kotlin |
| `composer.json` | PHP |
| `Gemfile` | Ruby |

Also note whether `.gitignore` exists at root (the compiler reads it automatically via `use_gitignore: true`).

### 3. Determine exclusions

Always add to the `ignore` array:
```
.git/
.DS_Store
*.log
.env
.env.*
```

Add language-specific exclusions based on detected stack:

**TypeScript / JavaScript:**
```
node_modules/
dist/
build/
.next/
.nuxt/
out/
coverage/
.turbo/
.cache/
*.tsbuildinfo
```

**Python:**
```
__pycache__/
*.pyc
*.pyo
.venv/
venv/
env/
dist/
build/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

**Go:**
```
vendor/
```

**Rust:**
```
target/
```

**Java / Kotlin:**
```
target/
build/
.gradle/
out/
```

**Ruby:**
```
vendor/
.bundle/
```

### 4. Root files — always include

Regardless of scope, always check and include these if they exist at the root:

- `README.md`
- Dependency manifest: `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `composer.json`, `Gemfile`
- Root config files: `tsconfig.json`, `vite.config.*`, `next.config.*`, `eslint.config.*`, `.eslintrc*`, `jest.config.*`, `vitest.config.*`, `tailwind.config.*`, `docker-compose.yml`, `Dockerfile`
- `.env.example` (if exists — never `.env` itself)

Use the Glob tool to check which ones actually exist before adding them.

### 5. Scope filtering (if scope provided)

If the user specified a scope, include only matching source directories plus root files from step 4.

**Directory scope mapping:**

| User says | Directories to look for |
|---|---|
| api, backend, server | `api/`, `backend/`, `server/`, `app/api/`, `src/api/`, `src/server/` |
| frontend, web, client, ui | `frontend/`, `web/`, `client/`, `ui/`, `app/`, `src/app/`, `src/pages/`, `src/components/`, `src/views/` |
| shared, common, lib, utils | `shared/`, `common/`, `lib/`, `utils/`, `src/lib/`, `src/utils/` |
| db, database, models | `db/`, `database/`, `models/`, `src/models/`, `src/db/` |
| core, domain | `core/`, `domain/`, `src/core/`, `src/domain/` |

Check which directories actually exist using the Glob tool. If none match, look one level deeper and ask the user to confirm.

Add matching directories as glob patterns: `api/**`, `src/api/**`, etc.

### 6. No scope — full project mapping

If no scope is given, include all source code:

- Explicitly list root config files (from step 4)
- Use glob patterns for source directories: `src/**`, `app/**`, `lib/**`, `packages/**`, etc.
- For smaller projects, you may list specific important files/dirs rather than `src/**`

Rely on the `ignore` patterns from step 3 to exclude build artifacts — do not manually list every file.

### 7. Generate the JSON config

Use this structure:

```json
{
  "title": "<ProjectName> – <Scope or omit if full>",
  "absolute_path": "<target_dir with forward slashes>",
  "start_prompt": "Please get acquainted with this project's structure and source files. I will send you multiple files in sequence—review and understand their contents. Once you have absorbed the overall context, wait for my instructions before performing any specific tasks.\n\n",
  "start_text": "-- Begin file \"{file}\" --\n\n",
  "stop_text": "\n-- End file \"{file}\" --\n\n",
  "use_gitignore": true,
  "ignore": [],
  "files": []
}
```

**Rules:**
- `absolute_path`: Use forward slashes, no trailing slash
- `title`: Title-case the project folder name. Append ` – API`, ` – Frontend`, etc. for scoped configs
- `files` ordering: root files first (README.md, package.json, ...), then source dirs/globs alphabetically
- All paths in `files` use forward slashes and are relative to `absolute_path`
- For directories, use recursive glob: `src/**` (the compiler expands these)
- `ignore` patterns follow .gitignore glob syntax

### 8. Save the file

Determine the output filename:
- Full project: `<project-folder-name-lowercase-hyphenated>.json`
- Scoped: `<project-folder-name>-<scope>.json`

Examples: `ai-pipeline-v2.json`, `my-app-api.json`, `myapp-frontend.json`

Save using the **Write** tool to:
```
projects/<config-name>.json
```
(relative to the current working directory, which is the Project Context Compiler root)

### 9. Confirm to the user

After saving, tell the user:
- The config file path: `projects/<config-name>.json`
- What's included (scope summary)
- How to compile: `python main.py <config-name>.json`
- How to open the visual designer: `python design.py <config-name>.json`

## Examples

**"lag prosjektfil for C:/Users/mathi/code/ai-pipeline-v2"**
→ Detected: Python project
→ Saves: `projects/ai-pipeline-v2.json`
→ Files: `README.md`, `requirements.txt`, `src/**` (or top-level .py files if flat structure)
→ Ignore: Python artifacts

**"lag prosjektfil for C:/Users/mathi/code/ai-pipeline-v2, bare api laget"**
→ Saves: `projects/ai-pipeline-v2-api.json`
→ Files: `README.md`, `requirements.txt`, `api/**` (or `src/api/**`)

**"kan du lage context for frontend delen av /home/user/myapp"**
→ Saves: `projects/myapp-frontend.json`
→ Files: root configs + `frontend/**` (or `src/components/**`, `src/pages/**`, etc.)
