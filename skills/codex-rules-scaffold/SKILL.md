---
name: hermes-codex-rules-scaffold
description: "Interactive scaffold of .hermes/rules/ for any project. Part of the hermes-codex ecosystem. Scans the entire project, groups files by type, then walks you through each group step by step. For each group it presents the detected files and asks YOU what rules to apply. Refines rules based on your input, asks for improvements, and confirms before writing. Use when starting a new project, inheriting a codebase, or whenever you need to define project-specific Hermes Codex rules. NOT for editing existing rule files or global rules."
version: 1.1.0
author: mobeenx20
license: MIT
metadata:
  hermes:
    tags: [rules, scaffold, hermes-codex, interactive, project-setup, codex]
    related_skills: [hermes-rules-setup, hermes-agent, skill-creator]
---

# Project Rules Scaffold

## Purpose

Walks you through creating `.hermes/rules/` files for a project. For each detected file type, the skill presents findings, asks for your rules, refines them with your input, and confirms before writing.

This is an **interactive, step-by-step conversation** -- not a batch automation. Each decision is reviewed with you.

## Prerequisites

- `hermes_codex` plugin installed and activated (the `/hermes_codex` command works)
- Project directory exists and contains files worth creating rules for

## Trigger phrases

Say any of these and this skill should be invoked:
- "Scaffold rules for this project"
- "Create project rules"
- "Setup .hermes/rules for this project"
- "I need rules for my project"
- "Scan this project and suggest rules"
- "Initialize hermes rules"
- "Walk me through creating rules for this project"
- Any mention of setting up project rules or conventions

## Workflow

The skill follows this sequence. Each step is a conversation turn with you.

### Step 1: Confirm the project

Ask the user which project to scan. Default to the current working directory. Let them override with a path.

### Step 2: Scan and group files

Scan all files in the project recursively, excluding standard noise:
- Exclude: `.git/`, `node_modules/`, `.venv/`, `venv/`, `__pycache__/`, `.next/`, `dist/`, `build/`, `target/`, `.tox/`, `*.pyc`, `.DS_Store`, `*.log`, `.env`, IDE dirs (`.idea/`, `.vscode/`, `.zed/`)

Group files by their extension into categories. Show the user the inventory before proceeding:

```
Found in <project>:
  Python (.py)      - 14 files
  JavaScript (.js)  - 8 files
  TypeScript (.tsx) - 5 files
  Markdown (.md)    - 12 files
  YAML (.yml)       - 4 files
  CSS (.css)        - 3 files
  Shell (.sh)       - 2 files
  Other             - 6 files (<list extensions>)
```

Group "Other" files into common buckets where possible (Docker, Config, SQL, etc.).

### Step 3: Walk through each group (one per conversation turn)

For each detected group, present to the user:

```
=== Python (.py) - 14 files ===
  /path/to/main.py
  /src/utils/helpers.py
  /tests/test_auth.py
  ...

What rules should Python files in this project follow?
Or type 'suggest' for best-practice recommendations.
```

**Three paths from here:**

a) **User provides rules directly** -- Capture their input, repeat it back for confirmation, add/refine if they ask.

b) **User says 'suggest'** -- First, scan `~/.hermes/rules/` for existing global rules. Note which ones already cover this group (e.g., git-conventions.md for writing style, testing.md for test principles). Propose best-practice rules for that language, referencing global rules instead of duplicating their content. Include patterns observed in the code if relevant (e.g., "I see you use black for formatting" or "You have pytest test files"). Present as:
   ```
   Suggested rules for Python:
   1. Use type hints on all function signatures
   2. Format with black (88 char line length)
   3. Run pytest before every commit
   4. Document public APIs with docstrings
   
   Which ones do you want? Edit, add, or remove. Type 'confirm' when done.
   ```

c) **User says 'skip'** -- Move to the next group. No rule file written for this type.

After the user confirms the rules for this group, write the rule file:
- Always-loaded: `<type>-rules.md` (no frontmatter)
- Path-scoped: `<type>-rules.md` with `paths:` frontmatter

Ask: "Should these rules apply to all files (always loaded) or only when opening <extension> files (path-scoped)?"

### Step 4: Resolve overlaps

After all groups are processed, check for rule files that might conflict or overlap:
- Two groups with overlapping paths (e.g., `.js` and `.tsx` files)
- Rules that duplicate content from global `~/.hermes/rules/` files
- Suggest merging if sensible

Present the full rule set for review before writing:

```
=== Rules to be written ===
  python-rules.md     (always loaded)
  typescript-rules.md (path-scoped: **/*.{ts,tsx})
  git-conventions.md  (always loaded)
  markdown-rules.md   (always loaded)

Does this look right? [y/N]
```

### Step 5: Write and verify

Write all confirmed rule files to `.hermes/rules/`. Run a quick verification:

```bash
/hermes_codex list
```

Report the result. Remind the user: rules appear on the next Hermes turn via `pre_llm_call` hook.

## Rule writing conventions

Follow these when writing the actual `.md` files:

### Always-loaded rules (no frontmatter)

```markdown
# <Type> Rules

## Rule 1
Explanation of why this rule matters.

## Rule 2
Explanation of why this rule matters.
```

### Path-scoped rules (with YAML paths frontmatter)

```markdown
---
paths:
  - "**/*.py"
---

# Python Rules

## Rule 1
Explanation of why this rule matters.
```

### Writing style

Apply the user's global conventions:
- Plain developer English. Short, direct sentences.
- **No em dashes.** Use hyphens (-), commas, colons, or split into two sentences.
- Avoid banned words: "dedupe", "leverage", "utilize", "facilitate", "augment", "comprehensive", "robust", "seamless", "granular", "orchestrate", "streamline", "holistic", "surface" (as verb), "warranted", "defensible", "ergonomics" (outside UX)
- Use simpler alternatives: "use" not "utilize", "check" not "ensure", "show" not "surface", "makes sense" not "warranted"
- Explain WHY each rule exists, not just WHAT to do. LLMs work better with reasoning.
- Prefer specific, verifiable rules over vague principles.
- One rule per bullet. Keep each rule actionable.

### File naming

- `<language>-rules.md` for language groups (e.g., `python-rules.md`, `typescript-rules.md`)
- `<topic>-rules.md` for non-language groups (e.g., `testing.md`, `docker.md`, `git-conventions.md`)
- If only one group found, name with the project context (e.g., `project-conventions.md`)

## Pitfalls

### Large projects with many file types
If the project has 10+ groups, offer to batch similar groups. Combine JS + TS + TSX into a single `javascript-rules.md` with `paths: ["**/*.{js,jsx,ts,tsx}"]`.

### User disengagement (auto-accept mode)
If the user says "just use defaults", "accept all", "auto-generate", or the context is non-interactive (test run, background task, cron), run in **auto-accept mode**:
- Present the inventory and suggestions but do NOT wait for user input on each group
- Use best-practice suggestions for every group
- Write all rule files in a single pass
- Present a summary at the end
- This prevents the conversational loop from blocking execution when there is no interactive user

### Stuck in interactive loop (no user response)
If the skill presents suggestions and the user does not respond (timeout, test context, async invocation), fall through to auto-accept mode after one unanswered prompt. Do NOT keep waiting indefinitely. Write the suggestions and report what was written.

### Existing .hermes/rules/ directory
If `.hermes/rules/` already exists with files, show the existing files first. Ask: "Overwrite, append, or skip this group?"

### No project files
If the project is empty or has only noise files (gitignored dirs), report this and suggest creating rules manually from templates.

### Path-scoped vs always-loaded decision
Rules that apply broadly (testing principles, git conventions) work better as always-loaded. Rules specific to a language (Python formatting rules, JS style) work better as path-scoped.

### User only wants rules for a subset of groups
Common pattern: the project has 5+ file types but the user only wants rules for one or two (e.g., only Python, skip the rest). Accept skips without pushing back. Do not require the user to justify why they don't want rules for the remaining groups. Process only the confirmed groups and write rules for those alone -- the unprocessed groups produce no rule files.

## Verification

After writing rules, verify in this order:

1. **Hermes runtime available**: Run `/hermes_codex list` to confirm all files are registered.
2. **Hermes runtime NOT available**: Verify manually:
   - File exists: `ls .hermes/rules/<name>.md`
   - Frontmatter check: If path-scoped, confirm `paths:` key is present in YAML frontmatter
   - Content check: Read file back and confirm no banned words, no em dashes
   - Global overlap check: Confirm the new rule references (not duplicates) any global rule covering the same topic
3. Report the results and remind the user: rules appear on the next Hermes turn via `pre_llm_call` hook.
