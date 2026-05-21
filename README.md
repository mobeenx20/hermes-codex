# Hermes Codex

**Scoped project rules for Hermes Agent.**

Hermes Codex brings Claude Code-style `.claude/rules/` to Hermes Agent - a modular rules directory system that lets you define per-project development conventions with YAML path-scoping.

```bash
# Copy plugin to Hermes plugins directory
cp -r hermes_codex ~/.hermes/hermes-agent/plugins/hermes_codex/
```

## Features

- **Project-scoped rules** - `.hermes/rules/` in any project directory
- **Global rules** - `~/.hermes/rules/` for conventions shared across all projects
- **Path-scoped rules** - YAML `paths:` frontmatter activates rules only when matching files are accessed
- **Automatic deduplication** - project rules override global rules with the same filename
- **Plugin hook system** - uses Hermes' native hooks, no core code modifications
- **Slash commands** - `/hermes_codex list` and `/hermes_codex test <path>`

## Installation

### Plugin install (recommended)

```bash
git clone https://github.com/mobeenx20/hermes-codex.git
cp -r hermes-codex/hermes_codex ~/.hermes/hermes-agent/plugins/hermes_codex/
```

No restart needed - the plugin activates on the next Hermes session start
via the `on_session_start` hook.

> **Note:** hermes-codex requires the Hermes Agent runtime. Install inside
> the Hermes Agent Python environment only. The plugin uses Hermes' native
> hook system - no core code modifications needed.
>
> Rules are injected into the agent's context on every turn via the
> `pre_llm_call` plugin hook. Always-active rules appear immediately;
> path-scoped rules have a one-turn delay (matching file access → detected
> in post_tool_call → injected on next turn).

### Package install (advanced)

> **Note:** hermes-codex requires the Hermes Agent runtime. Install inside
> the Hermes Agent Python environment only.

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

**Always-active rules** - no frontmatter required:

```markdown
# .hermes/rules/testing.md
- Run `pytest` before every commit
- Maintain minimum 80% coverage
- Mock external APIs in unit tests
```

**Path-scoped rules** - use YAML `paths:` frontmatter:

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
/hermes_codex list

# Test path matching
/hermes_codex test src/api/handler.py
```

## Rule Resolution Order

1. **Global rules** (`~/.hermes/rules/`) are loaded first - but skipped if a project rule with the same filename exists
2. **Project rules** (`.hermes/rules/`) are loaded second and always included
3. **Path-scoped rules** (any rule with `paths:` frontmatter) are deferred - injected on the next turn after a matching file is accessed via `read_file`, `patch`, or `search_files`

## Architecture

```
hermes_codex/
├── __init__.py          # Plugin registration + hooks + slash commands
├── rules_loader.py      # Rule loading from .hermes/rules/ directories
└── path_matcher.py      # Glob-based path matching for paths: frontmatter
```

The plugin registers four hooks with Hermes:
- **`on_session_start`** - logs active rule sources
- **`on_session_end`** - cleans up cached rules
- **`post_tool_call`** - detects path-scoped rule matches on file access
- **`pre_llm_call`** - injects rules into the user message on every turn

## Requirements

- Hermes Agent (any recent version with plugin hook support)
- Python 3.10+

## License

MIT - see [LICENSE](LICENSE)
