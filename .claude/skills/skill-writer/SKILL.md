---
name: skill-writer
description: Guide users through creating Agent Skills for Claude Code. Use when the user wants to create, write, author, or design a new Skill, or needs help with SKILL.md files, frontmatter, or skill structure.
---

# Skill Writer

This Skill helps you create well-structured Agent Skills for Claude Code that follow best practices and validation requirements.

## When to use this Skill

Use this Skill when:
- Creating a new Agent Skill
- Writing or updating SKILL.md files
- Designing skill structure and frontmatter
- Troubleshooting skill discovery issues
- Converting existing prompts or workflows into Skills

## Instructions

### Step 1: Determine Skill scope

First, understand what the Skill should do:

1. **Ask clarifying questions**:
   - What specific capability should this Skill provide?
   - When should Claude use this Skill?
   - What tools or resources does it need?
   - Is this for personal use or team sharing?

2. **Keep it focused**: One Skill = one capability
   - Good: "PDF form filling", "Excel data analysis"
   - Too broad: "Document processing", "Data tools"

### Step 2: Choose Skill location

Determine where to create the Skill:

**Personal Skills** (`~/.claude/skills/`):
- Individual workflows and preferences
- Experimental Skills
- Personal productivity tools

**Project Skills** (`.claude/skills/`):
- Team workflows and conventions
- Project-specific expertise
- Shared utilities (committed to git)

### Step 3: Create Skill structure

Create the directory and files:

```bash
# Personal
mkdir -p ~/.claude/skills/skill-name

# Project
mkdir -p .claude/skills/skill-name
```

For multi-file Skills:
```
skill-name/
├── SKILL.md (required)
├── reference.md (optional)
├── examples.md (optional)
├── scripts/
│   └── helper.py (optional)
└── templates/
    └── template.txt (optional)
```

### Step 4: Write SKILL.md frontmatter

Create YAML frontmatter with required fields:

```yaml
---
name: skill-name
description: Brief description of what this does and when to use it
---
```

**Field requirements**:

- **name**:
  - Lowercase letters, numbers, hyphens only
  - Max 64 characters
  - Must match directory name
  - Good: `pdf-processor`, `git-commit-helper`
  - Bad: `PDF_Processor`, `Git Commits!`

- **description**:
  - Max 1024 characters
  - Include BOTH what it does AND when to use it
  - Use specific trigger words users would say
  - Mention file types, operations, and context

### Step 5: Write effective descriptions

The description is critical for Claude to discover your Skill.

**Formula**: `[What it does] + [When to use it] + [Key triggers]`

### Step 6: Validate the Skill

Check these requirements:

- [ ] SKILL.md exists in correct location
- [ ] Directory name matches frontmatter `name`
- [ ] Valid YAML frontmatter
- [ ] `name` follows naming rules
- [ ] `description` is specific and < 1024 chars
- [ ] Clear instructions for Claude
- [ ] Concrete examples provided
- [ ] Dependencies listed (if any)
