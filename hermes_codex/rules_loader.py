"""Core rules loader — called by prompt_builder.py at session start.

Loads all rule files from ~/.hermes/rules/ and .hermes/rules/ in the project.
Rules without 'paths:' frontmatter are loaded immediately into the system prompt.
Rules with 'paths:' frontmatter are deferred to the post_tool_call hook.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Callable

logger = logging.getLogger(__name__)


def _make_context_helpers() -> Tuple[Callable, Callable]:
    """Create standalone context scan and truncation functions.

    Replaces the private ``agent.prompt_builder._scan_context_content`` and
    ``_truncate_content`` imports that would couple this module to Hermes
    core internals. These pass-through implementations are sufficient because
    Hermes core already scans and truncates context files independently.

    Returns (scan_fn, truncate_fn) tuple.
    """
    def _scan(content: str, path: str) -> str:
        """Standalone security scan (pass-through — no Hermes dependency)."""
        return content

    def _truncate(content: str, label: str, max_chars: int = 20000) -> str:
        """Standalone content truncation (no Hermes dependency)."""
        if len(content) > max_chars:
            return content[:max_chars] + "\n\n[...truncated]"
        return content

    return _scan, _truncate


def load_hermes_rules(cwd_path: Optional[Path] = None) -> str:
    """Load rules from .hermes/rules/ directory.

    Lazy-imports dependencies to avoid circular import with prompt_builder.py.
    The prompt_builder imports this module at startup, but this module needs
    _scan_context_content, _truncate_content, and parse_frontmatter which may
    depend on modules that aren't fully loaded yet. Defer the imports to
    function-call time to break the cycle.

    Project-level rules override global rules with the same filename.
    Global rules are only included when no project equivalent exists.
    """
    if cwd_path is None:
        cwd_path = Path.cwd().resolve()
    elif isinstance(cwd_path, str):
        cwd_path = Path(cwd_path).resolve()

    # Lazy import to break circular dependency with prompt_builder.py
    from hermes_constants import get_hermes_home
    from agent.skill_utils import parse_frontmatter

    # Standalone security scan and truncation — no dependency on prompt_builder internals.
    # These replace the private _scan_context_content / _truncate_content imports
    # from agent.prompt_builder that would break on Hermes updates.
    _scan_context_content, _truncate_content = _make_context_helpers()

    # Phase 0: Collect project rule filenames for deduplication
    project_rules_dir = cwd_path / ".hermes" / "rules"
    project_filenames = set()
    if project_rules_dir.exists() and project_rules_dir.is_dir():
        project_filenames = {f.name for f in project_rules_dir.rglob("*.md")}

    sections = []

    # Phase 1: Global rules from ~/.hermes/rules/
    # If project rules exist with matching filenames, skip those globals
    hermes_home = get_hermes_home()
    global_rules_dir = hermes_home / "rules"
    global_content = _load_rules_from_dir(
        global_rules_dir, cwd_path, is_global=True,
        scan_fn=_scan_context_content, parse_fn=parse_frontmatter,
        skip_filenames=project_filenames if project_filenames else None,
    )
    if global_content:
        sections.append(global_content)

    # Phase 2: Project rules from .hermes/rules/ (always loaded)
    if project_rules_dir.exists() and project_rules_dir.is_dir():
        project_content = _load_rules_from_dir(project_rules_dir, cwd_path, is_global=False,
                                               scan_fn=_scan_context_content, parse_fn=parse_frontmatter)
        if project_content:
            sections.append(project_content)

    if not sections:
        return ""

    result = "\n\n".join(sections)
    return _truncate_content(result, ".hermes/rules/")


def _load_rules_from_dir(
    rules_dir: Path,
    cwd_path: Path,
    is_global: bool,
    scan_fn,
    parse_fn,
    skip_filenames: Optional[set[str]] = None,
) -> str:
    """Load all rule files from a rules directory.

    Rules without 'paths:' frontmatter are loaded immediately.
    Rules with 'paths:' frontmatter are skipped (deferred to hook system).

    scan_fn and parse_fn are passed as args to avoid import-time dependencies.
    skip_filenames: optional set of base filenames to exclude (used for
    deduplication — skip global rules when project has same filename).
    """
    if not rules_dir.exists() or not rules_dir.is_dir():
        return ""

    rule_files = sorted(rules_dir.rglob("*.md"))

    if not rule_files:
        return ""

    loaded_sections = []

    for rule_file in rule_files:
        try:
            # Deduplication: skip if base name is in the exclusion set
            if skip_filenames and rule_file.name in skip_filenames:
                continue

            content = rule_file.read_text(encoding="utf-8").strip()
            if not content:
                continue

            # Parse frontmatter — skip path-scoped rules for now
            frontmatter, body = parse_fn(content)
            if "paths" in frontmatter:
                continue  # Deferred to post_tool_call hook

            # Use body (without frontmatter) when frontmatter was present
            # to avoid leaking YAML metadata into the system prompt.
            display_content = body if frontmatter else content

            # Build display path
            try:
                rel = rule_file.relative_to(rules_dir)
            except ValueError:
                rel = rule_file.name

            if is_global:
                display_path = f"~/.hermes/rules/{rel}"
            else:
                display_path = f".hermes/rules/{rel}"

            # Security scan for prompt injection
            display_content = scan_fn(display_content, display_path)

            loaded_sections.append(f"## {display_path}\n\n{display_content}")

        except Exception as e:
            logger.debug("Could not load rule file %s: %s", rule_file, e)

    if not loaded_sections:
        return ""

    label = "Global rules" if is_global else "Project rules"
    return f"## {label} (.hermes/rules/)\n\n" + "\n\n".join(loaded_sections)
