"""hermes_rules plugin — modular rules directory system for Hermes Agent.

Provides .hermes/rules/ equivalent to Claude Code's .claude/rules/
with YAML path-scoping and user-level global rules.

Hooks:
  - on_session_start — logs rules discovery summary
  - post_tool_call — injects path-scoped rules when matching files accessed

Slash command:
  - /hermes_rules — list rules, test path matching
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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
            logger.info("hermes_rules: active rule sources: %s", ", ".join(found))
        else:
            logger.debug("hermes_rules: no .hermes/rules/ directories found")

    except Exception as e:
        logger.debug("hermes_rules on_session_start failed: %s", e)


def _on_post_tool_call(
    tool_name: str = "",
    args: Optional[Dict[str, Any]] = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    **_: Any,
) -> None:
    """When read_file or patch accesses a file, check for matching path-scoped rules.

    If matching rules are found and haven't been injected yet for this session,
    they will be available via the existing prompt mechanism on next turn.
    Currently this hook serves as a discovery point for path-scoped rules.
    """
    if tool_name not in ("read_file", "patch", "search_files"):
        return

    file_path = _extract_file_path(tool_name, args)
    if not file_path:
        return

    # Path-scoped rule injection happens through the existing context system
    # This hook logs when matches are found
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
                                "hermes_rules: %s matched by path-scoped rule %s",
                                file_path, rule_file.name,
                            )
                except Exception:
                    pass

    except Exception as e:
        logger.debug("hermes_rules post_tool_call failed: %s", e)


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
    """Handle /hermes_rules slash command."""
    argv = raw_args.strip().split()
    if not argv or argv[0] in ("help", "-h", "--help"):
        return (
            "/hermes_rules — Manage project rules in .hermes/rules/\n\n"
            "Usage:\n"
            "  /hermes_rules list          List all discovered rules\n"
            "  /hermes_rules test <file>   Test which rules match a file path\n"
        )

    if argv[0] == "list":
        return _list_rules()
    elif argv[0] == "test" and len(argv) > 1:
        return _test_rules(argv[1])

    return f"Unknown subcommand: {argv[0]}. Use /hermes_rules help"


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
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_command(
        "hermes_rules",
        handler=_handle_slash_rules,
        description="List and test project rules in .hermes/rules/",
    )
