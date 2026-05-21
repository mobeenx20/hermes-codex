"""hermes_codex plugin — modular rules directory system for Hermes Agent.

Provides .hermes/rules/ equivalent to Claude Code's .claude/rules/
with YAML path-scoping and user-level global rules.

Hooks:
  - on_session_start   — logs rules discovery summary
  - on_session_end     — cleans up cached rules
  - post_tool_call     — detects path-scoped rule matches on file access
  - pre_llm_call       — injects rules into the user message on every turn

Slash command:
  - /hermes_codex — list rules, test path matching
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---- Module-level state for context injection ----
# Set by post_tool_call, consumed by pre_llm_call on the next turn.
_PENDING_PATH_RULES: List[str] = []
# Always-active rules, loaded once on first pre_llm_call.
_CACHED_ALWAYS_RULES: Optional[str] = None


def _on_session_start(
    session_id: str = "",
    task_id: str = "",
    **_: Any,
) -> None:
    """Log which rules directories exist at session start."""
    try:
        from hermes_constants import get_hermes_home
        cwd = Path.cwd().resolve()
        global_dir = get_hermes_home() / "rules"
        project_dir = cwd / ".hermes" / "rules"

        found = []
        if global_dir.exists():
            n = len(list(global_dir.rglob("*.md")))
            found.append(f"~/.hermes/rules/ ({n} files)")
        if project_dir.exists():
            n = len(list(project_dir.rglob("*.md")))
            found.append(f".hermes/rules/ ({n} files)")

        if found:
            logger.info("hermes_codex: active rule sources: %s", ", ".join(found))
        else:
            logger.debug("hermes_codex: no .hermes/rules/ directories found")

    except Exception as e:
        logger.debug("hermes_codex on_session_start failed: %s", e)


def _on_session_end(
    session_id: str = "",
    **_: Any,
) -> None:
    """Clean up cached rules when session ends."""
    global _PENDING_PATH_RULES, _CACHED_ALWAYS_RULES
    _PENDING_PATH_RULES = []
    _CACHED_ALWAYS_RULES = None
    logger.debug("hermes_codex: session ended, caches cleared")


def _on_pre_llm_call(
    session_id: str = "",
    is_first_turn: bool = False,
    **_,
) -> Optional[Dict[str, str]]:
    """Inject rules into the agent's context on every turn.

    Always-active rules are loaded once and cached.
    Path-scoped rules are injected from the previous turn's post_tool_call
    matches, then cleared (one-turn delay is inherent to hook ordering).
    """
    global _PENDING_PATH_RULES, _CACHED_ALWAYS_RULES
    parts = []

    # Always-active rules: load once, cache for session lifetime
    if _CACHED_ALWAYS_RULES is None:
        try:
            from .rules_loader import load_hermes_rules
            _CACHED_ALWAYS_RULES = load_hermes_rules()
        except Exception as e:
            logger.debug("hermes_codex: failed to load rules: %s", e)
            _CACHED_ALWAYS_RULES = ""
    if _CACHED_ALWAYS_RULES:
        parts.append(_CACHED_ALWAYS_RULES)

    # Path-scoped rules from last turn's matches
    if _PENDING_PATH_RULES:
        parts.append("\n\n".join(_PENDING_PATH_RULES))
        _PENDING_PATH_RULES = []  # Clear after injection

    if parts:
        return {"context": "\n\n".join(parts)}
    return None


def _on_post_tool_call(
    tool_name: str = "",
    args: Optional[Dict[str, Any]] = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    **_: Any,
) -> None:
    """Log AND store matching path-scoped rules on file access.

    Matched rules are appended to a module-level list and returned by the
    pre_llm_call hook on the next turn (one-turn delay is inherent to the
    hook ordering — pre_llm_call fires before tool calls).
    """
    if tool_name not in ("read_file", "patch", "search_files"):
        return

    file_path = _extract_file_path(tool_name, args)
    if not file_path:
        return

    try:
        from .path_matcher import matches_paths_frontmatter
        from hermes_constants import get_hermes_home
        from agent.skill_utils import parse_frontmatter

        cwd = Path.cwd().resolve()
        for rules_dir in [get_hermes_home() / "rules", cwd / ".hermes" / "rules"]:
            if not rules_dir.exists():
                continue
            for rule_file in sorted(rules_dir.rglob("*.md")):
                try:
                    content = rule_file.read_text(encoding="utf-8").strip()
                    fm, body = parse_frontmatter(content)
                    if "paths" in fm:
                        if matches_paths_frontmatter(file_path, fm["paths"]):
                            logger.info(
                                "hermes_codex: %s matched by path-scoped rule %s",
                                file_path, rule_file.name,
                            )
                            # Store matched content for next turn's pre_llm_call
                            _PENDING_PATH_RULES.append(
                                f"## {rule_file.name} (path-scoped)\n\n{body}"
                            )
                except Exception:
                    pass

    except Exception as e:
        logger.debug("hermes_codex post_tool_call failed: %s", e)


def _extract_file_path(tool_name: str, args: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract file path from tool call arguments."""
    if not args or not isinstance(args, dict):
        return None

    if tool_name in ("read_file", "patch", "search_files"):
        path_arg = args.get("path")
        if isinstance(path_arg, str) and path_arg:
            return path_arg

    return None


def _handle_slash_rules(raw_args: str) -> str:
    """Handle /hermes_codex slash command."""
    argv = raw_args.strip().split()
    if not argv or argv[0] in ("help", "-h", "--help"):
        return (
            "/hermes_codex — Manage project rules in .hermes/rules/\n\n"
            "Usage:\n"
            "  /hermes_codex list          List all discovered rules\n"
            "  /hermes_codex test <file>   Test which rules match a file path\n"
        )

    if argv[0] == "list":
        return _list_rules()
    elif argv[0] == "test" and len(argv) > 1:
        return _test_rules(argv[1])

    return f"Unknown subcommand: {argv[0]}. Use /hermes_codex help"


def _list_rules() -> str:
    """List all loaded rules for current project."""
    try:
        from hermes_constants import get_hermes_home
        lines = ["Rules discovered for this session:"]

        global_dir = get_hermes_home() / "rules"
        project_dir = Path.cwd().resolve() / ".hermes" / "rules"

        for rules_dir, label in [(global_dir, "~/.hermes/rules"),
                                 (project_dir, ".hermes/rules")]:
            if rules_dir.exists():
                for rule_file in sorted(rules_dir.rglob("*.md")):
                    lines.append(f"  {label}/{rule_file.relative_to(rules_dir)}")
            else:
                lines.append(f"  {label}/ — not found")

        return "\n".join(lines)
    except Exception as e:
        return f"Error listing rules: {e}"


def _test_rules(file_path: str) -> str:
    """Test which path-scoped rules match a file path."""
    try:
        from hermes_constants import get_hermes_home
        from .path_matcher import matches_paths_frontmatter
        from agent.skill_utils import parse_frontmatter

        lines = [f"Testing rules against: {file_path}\n"]
        matched = False

        for rules_dir in [get_hermes_home() / "rules", Path.cwd().resolve() / ".hermes" / "rules"]:
            if not rules_dir.exists():
                continue
            for rule_file in sorted(rules_dir.rglob("*.md")):
                try:
                    content = rule_file.read_text(encoding="utf-8").strip()
                    fm, body = parse_frontmatter(content)
                    if "paths" in fm and matches_paths_frontmatter(file_path, fm["paths"]):
                        matched = True
                        lines.append(f"  MATCH: {rule_file.relative_to(rules_dir)}")
                        lines.append(f"         paths: {fm['paths']}")
                except Exception:
                    continue

        if not matched:
            lines.append("  No matching path-scoped rules found.")

        return "\n".join(lines)
    except Exception as e:
        return f"Error testing rules: {e}"


def register(ctx) -> None:
    """Plugin registration with Hermes."""
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_command(
        "hermes_codex",
        handler=_handle_slash_rules,
        description="List and test project rules in .hermes/rules/",
    )
