# Changelog

## 1.0.0 (2026-05-21)

### Initial Release

- **Plugin system** — native Hermes hooks with zero core patches
- **Project-scoped rules** — `.hermes/rules/` in any project directory
- **Global rules** — `~/.hermes/rules/` for cross-project conventions
- **Path-scoped rules** — YAML `paths:` frontmatter for file-specific rules
- **Path matching** — glob with `**`, `*`, `?`, `[...]`, and `{a,b}` brace expansion
- **Deduplication** — project rules with same filename override globals
- **Slash commands** — `/hermes_rules list` and `/hermes_rules test <path>`
- **Security scanning** — prompt injection detection on rule content
- **Stress-tested** — 38 test scenarios, 36/38 passing (2 are Hermes scanner limitations)
