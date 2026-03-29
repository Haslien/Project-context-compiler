---
name: claude-md-writer
description: Creates or improves CLAUDE.md files for any project. Use when the user wants to set up Claude Code guidance, document project conventions, or improve how Claude understands their codebase. Trigger phrases: "create CLAUDE.md", "write a CLAUDE.md", "improve my CLAUDE.md", "lag CLAUDE.md", "hjelp med CLAUDE.md", "set up Claude for this project".
---

# CLAUDE.md Writer

This skill creates lean, effective CLAUDE.md files that give Claude Code the right context to work well in a project — without over-explaining or duplicating what Claude can derive from code.

## Process

### Step 1: Understand the project

Read the following before writing anything:
- README.md (if present)
- Key config files (package.json, pyproject.toml, Makefile, etc.)
- Folder structure (top-level + src/)
- Any existing CLAUDE.md

Ask yourself three questions:

**WHY** — Why does this project exist? What problem does it solve?
**WHAT** — What does the codebase contain? What are the main components?
**HOW** — How does a developer work in this repo day-to-day? Build, test, lint, run?

### Step 2: Draft the CLAUDE.md

Follow this structure — only include sections that add real value:

```markdown
# <Project Name>

<One-line description of what this project does and why it exists.>

## Commands

<Essential commands only. Exactly what to type.>

```bash
python main.py my-project.json   # compile a project to output/
```

## Architecture

<Only what's non-obvious from the file structure. Skip if self-evident.>

## Conventions

<Project-specific rules that Claude might otherwise get wrong.>

## Key Files

<Only list files that are central and non-obvious to navigate.>
```

### Step 3: Apply the leanness filter

Before writing the final file, remove anything that:
- Claude can infer by reading the code
- Is general best practice (not specific to this project)
- Restates what the README already says
- Describes hypothetical future behavior

**Lean test**: Would a senior developer joining this project find this line useful on day 1? If no — cut it.

### Step 4: Structure for progressive disclosure

Put the most critical, frequently-needed information first. Use agent_docs/ for deep reference material that Claude only needs for specific tasks.

```
.claude/
├── CLAUDE.md           ← essentials (short)
└── agent_docs/
    ├── config-schema.md    ← JSON config format details
    └── output-format.md    ← output file structure
```

Only create agent_docs/ if there is genuinely deep reference content that would clutter the main CLAUDE.md.

## Output

Write the final CLAUDE.md to the project root. Keep it under 80 lines where possible. Confirm the file was written and offer to create agent_docs/ if the project warrants it.

## Example — This project (Project Context Compiler)

```markdown
# Project Context Compiler

Python utility that consolidates source files into a single `.txt` for LLM context sharing.

## Commands

\`\`\`bash
python main.py my-project.json   # compile → output/my-project.txt
\`\`\`

## Architecture

- `projects/` — JSON config files (one per project to compile)
- `output/`   — generated `.txt` files (gitignored)
- `main.py`   — single entry point, no external dependencies

## Config schema

JSON fields: `title`, `absolute_path`, `files[]`, and optionally `start_prompt`, `start_text`, `stop_text`.
Use `{file}` placeholder in `start_text`/`stop_text` to interpolate the relative file path.
```
