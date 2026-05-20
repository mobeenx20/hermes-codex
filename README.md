# Hermes Codex

**Scoped project rules for Hermes Agent.**

Hermes Codex brings Claude Code-style `.claude/rules/` to Hermes Agent — a modular rules directory system that lets you define per-project development conventions with YAML path-scoping.

```bash
# Drop into plugins and restart
cp -r hermes_codex ~/.hermes/hermes-agent/plugins/
hermes restart
```

## Features

- **Project-scoped rules** — `.hermes/rules/` in any project directory
- **Global rules** — `~/.hermes/rules/` for conventions shared across all projects
- **Path-scoped rules** — YAML `paths:` frontmatter activates rules only when matching files are accessed
- **Automatic deduplication** — project rules override global rules with the same filename
- **Zero core patches** — uses Hermes' native plugin hook system
- **Slash commands** — `/hermes_rules list` and `/hermes_rules test <path>`

## Installation

### Plugin install (recommended)

```bash
git clone https://github.com/mobeenx20/hermes-codex.git
cp -r hermes-codex/hermes_codex ~/.hermes/hermes-agent/plugins/hermes_codex/
hermes restart
```

### Package install

```bash
pip install hermes-codex
# Then add to ~/.hermes/config.yaml:
# plugins:
#   - hermes_codex
```

## Quick Start

### 1. Create project rules

```bash
mkdir -p my-project/.hermes/rules
```

### 2. Add rule files

**Always-active rules** — no frontmatter required:

```markdown
# .hermes/rules/testing.md
- Run `pytest` before every commit
- Maintain minimum 80% coverage
- Mock external APIs in unit tests
```

**Path-scoped rules** — use YAML `paths:` frontmatter:

```markdown
---
paths:
  - "src/api/**/*.py"
  - "tests/**/*.py"
---

# API Development Rules
- Validate all input with Pydantic schemas
- Use standard error response format
- Every endpoint needs integration tests
```

### 3. Verify

```bash
# List all active rules
/hermes_rules list

# Test path matching
/hermes_rules test src/api/handler.py
```

## Rule Resolution Order

1. **Project rules** (`.hermes/rules/`) are loaded first
2. **Global rules** (`~/.hermes/rules/`) fill in gaps — skipped if a project rule with the same filename exists
3. **Path-scoped rules** are injected only when a matching file is accessed via `read_file`, `patch`, or `search_files`

## Architecture

```
hermes_codex/
├── __init__.py          # Plugin registration + hooks + slash commands
├── rules_loader.py      # Rule loading from .hermes/rules/ directories
└── path_matcher.py      # Glob-based path matching for paths: frontmatter
```

The plugin registers three hooks with Hermes:
- **`on_session_start`** — logs active rule sources
- **`post_tool_call`** — detects path-scoped rule matches on file access
- **`/hermes_rules`** — interactive command for listing and testing rules

## Requirements

- Hermes Agent (any recent version with plugin hook support)
- Python 3.10+

## License

MIT — see [LICENSE](LICENSE)
