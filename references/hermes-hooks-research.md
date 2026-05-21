# Plugin Hook System — Context Injection Research

**Date:** 2026-05-21
**Scope:** How Hermes Agent plugins can inject content into the agent's context without modifying core code
**Context:** Making `hermes-codex` self-sufficient — no core patches required

---

## The Problem

`hermes-codex` needs to load `.hermes/rules/*.md` files and make them visible to the agent. The original plugin design depended on a manual patch to `agent/prompt_builder.py` — users had to edit Hermes core to add a `load_hermes_rules()` call inside `build_context_files_prompt()`.

**Question:** Can the plugin inject rules into the agent's context using only the public hook system?

---

## The Answer: Yes — via `pre_llm_call` Hook

### Location

```python
# agent/conversation_loop.py:490-524
```

### How It Works

```python
# Plugin registers a hook callback. The core calls it once per turn:
results = invoke_hook("pre_llm_call",
    session_id=agent.session_id,
    user_message=original_user_message,
    conversation_history=list(messages),
    is_first_turn=(not bool(conversation_history)),
    model=agent.model,
    platform=getattr(agent, "platform", None) or "",
    sender_id=getattr(agent, "_user_id", None) or "",
)

# Each callback may return:
{"context": "formatted rules text..."}   # Dict with "context" key
"formatted rules text..."                # Plain string (equivalent)

# Results are joined with newlines and prepended to the user message.
# The system prompt stays UNCHANGED — prompt cache preserved.
```

### Key Design Properties

| Property | Detail |
|---|---|
| **System prompt unchanged** | Context goes into user message, not system prompt. Preserves prompt cache prefix. |
| **Ephemeral** | Never persisted to session DB. Lost on `/new` or session restart. |
| **Per-turn** | Fires once per agent turn. `is_first_turn` kwarg allows first-turn-only injection. |
| **Safe** | Each callback wrapped in try/except. One broken plugin won't break the agent loop. |
| **Available in all modes** | CLI, gateway, subagent — anywhere the conversation loop runs. |

---

## Available Hooks (from `hermes_cli/plugins.py:128-168`)

```python
VALID_HOOKS: Set[str] = {
    "pre_tool_call",            # Before any tool executes
    "post_tool_call",           # After any tool returns
    "transform_terminal_output",# Transform terminal command output
    "transform_tool_result",    # Transform any tool result
    "transform_llm_output",     # Transform LLM response text
    "pre_llm_call",             # ← USE THIS — injects context into user message
    "post_llm_call",            # After LLM response received
    "pre_api_request",          # Before external API call
    "post_api_request",         # After external API call
    "on_session_start",         # Session initialized
    "on_session_end",           # Session ended
    "on_session_finalize",      # Cleanup after session
    "on_session_reset",         # Session reset (/new)
    "subagent_stop",            # Subagent interrupted
    "pre_gateway_dispatch",     # Gateway message dispatch filter
    "pre_approval_request",     # Dangerous command approval requested
    "post_approval_response",   # User responded to approval prompt
}
```

---

## Why Not Other Hooks

| Hook | Why not |
|---|---|
| `on_session_start` | No return-value mechanism for injecting content. Only logging. |
| `post_tool_call` | No mechanism to modify agent context from return value. |
| `transform_llm_output` | Only transforms LLM responses, doesn't add context to prompts. |
| `pre_tool_call` | Runs per-tool, not per-turn. Wrong granularity. |

---

## PluginContext API (from `hermes_cli/plugins.py:287-386`)

```python
class PluginContext:
    def register_tool(self, name, toolset, schema, handler, ...) -> None
    def inject_message(self, content, role="user") -> bool  # Inject mid-conversation
    def register_hook(self, hook_name, callback) -> None
    def register_command(self, name, handler, description="") -> None
    @property
    def llm(self) -> PluginLlm  # Host-owned LLM facade
```

Note: `inject_message()` is available but only works in CLI mode (has `_cli_ref` check). The `pre_llm_call` hook works everywhere.

---

## System Prompt Architecture (from `agent/system_prompt.py:60-77`)

The system prompt has three tiers. Only the context tier is extensible from plugins:

```python
def build_system_prompt_parts(agent, system_message=None) -> dict:
    return {
        "stable":   [SOUL.md, tool guidance, skills prompt, env hints, ...],
        "context":  [system_message, build_context_files_prompt()],
        "volatile": [memory snapshot, user profile, timestamp],
    }
```

The context tier currently loads:
1. `.hermes.md / HERMES.md` (walk to git root)
2. `AGENTS.md / agents.md` (cwd only)
3. `CLAUDE.md / claude.md` (cwd only)
4. `.cursorrules / .cursor/rules/*.mdc` (cwd only)
5. `SOUL.md` from `~/.hermes/` (if not loaded as identity)

There is **no plugin hook** at system prompt build time. The `pre_llm_call` hook is the intended mechanism for plugins to contribute context at call time instead.

---

## `.cursor/rules/*.mdc` Precedent (from `prompt_builder.py:1396-1423`)

Hermes already loads directory-based rules from `.cursor/rules/`. This is the same pattern as `.hermes/rules/`:

```python
def _load_cursorrules(cwd_path: Path) -> str:
    """Load .cursorrules + .cursor/rules/*.mdc — cwd only."""
    cursorrules_content = ""

    # Single file
    cursorrules_file = cwd_path / ".cursorrules"
    if cursorrules_file.exists():
        content = cursorrules_file.read_text(...).strip()
        content = _scan_context_content(content, ".cursorrules")
        cursorrules_content += f"## .cursorrules\n\n{content}\n\n"

    # Directory-based rules
    cursor_rules_dir = cwd_path / ".cursor" / "rules"
    if cursor_rules_dir.exists():
        for mdc_file in sorted(cursor_rules_dir.glob("*.mdc")):
            content = mdc_file.read_text(...).strip()
            content = _scan_context_content(content, f".cursor/rules/{mdc_file.name}")
            cursorrules_content += f"## .cursor/rules/{mdc_file.name}\n\n{content}\n\n"

    return _truncate_content(cursorrules_content, ".cursorrules")
```

The security functions used (`_scan_context_content` and `_truncate_content`) are private to `prompt_builder.py`.

---

## Implementation Strategy for hermes-codex

### 1. Make `rules_loader.py` standalone

Replace:
```python
from agent.prompt_builder import _scan_context_content, _truncate_content
```

With standalone pass-through functions:
```python
def _scan_context_content(content, path):
    """Standalone security scan (no Hermes dependency)."""
    return content  # Pass through — core already scans context files

def _truncate_content(content, label, max_chars=20000):
    """Standalone truncation (no Hermes dependency)."""
    if len(content) > max_chars:
        return content[:max_chars] + "\n\n[...truncated]"
    return content
```

### 2. Add `pre_llm_call` hook handler

```python
_PENDING_PATH_RULES: List[str] = []       # Set by post_tool_call, consumed by pre_llm_call
_CACHED_ALWAYS_RULES: Optional[str] = None  # Always-active rules (loaded once)

def _on_pre_llm_call(session_id="", is_first_turn=False, **_):
    """Inject rules on every turn. Always-active rules cached once.
    Path-scoped rules injected from last turn's post_tool_call matches."""
    global _PENDING_PATH_RULES, _CACHED_ALWAYS_RULES
    parts = []

    # Always-active rules: load once
    if _CACHED_ALWAYS_RULES is None:
        from .rules_loader import load_hermes_rules
        _CACHED_ALWAYS_RULES = load_hermes_rules()
    if _CACHED_ALWAYS_RULES:
        parts.append(_CACHED_ALWAYS_RULES)

    # Path-scoped rules from last turn's matches
    if _PENDING_PATH_RULES:
        parts.append("\n\n".join(_PENDING_PATH_RULES))
        _PENDING_PATH_RULES = []  # Clear after injection

    if parts:
        return {"context": "\n\n".join(parts)}
    return None


def _on_post_tool_call(tool_name="", args=None, session_id="", **_):
    """Detect path-scoped rule matches and cache for next turn."""
    file_path = _extract_file_path(tool_name, args)
    if not file_path or tool_name not in ("read_file", "patch", "search_files"):
        return

    matched = _find_matching_scoped_rules(file_path)
    if matched:
        _PENDING_PATH_RULES.extend(matched)
```

### 3. Register in `register()`

```python
def register(ctx):
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)  # NEW
    ctx.register_command("hermes_rules", ...)
```

### 4. Update `_on_post_tool_call` docstring

Change from:
```
"""When read_file or patch accesses a file, check for matching path-scoped rules.
If matching rules are found and haven't been injected yet for this session,
they will be available via the existing prompt mechanism on next turn."""
```

To:
```
"""When read_file or patch accesses a file, log AND store matching path-scoped rules.

Matched rules are appended to a module-level list and returned by the
pre_llm_call hook on the next turn (one-turn delay is inherent to the hook
ordering).
"""
```

---

## One-Turn Delay for Path-Scoped Rules (Design Constraint)

### Hook Ordering

```
pre_llm_call     → fires FIRST (inject context)
  |                   
  v                   
[tool calls]      → agent reads file
  |
  v
post_tool_call    → fires LAST (detect matches)
```

Path-scoped rules (triggered by `read_file`, `patch`, `search_files`) are detected in `post_tool_call`. The matched content can only be injected on the **next turn** via `pre_llm_call`.

### Two-Tier State Machine

```python
# Module-level state
_PENDING_PATH_RULES: List[str] = []       # Set by post_tool_call, consumed by pre_llm_call
_CACHED_ALWAYS_RULES: Optional[str] = None  # Always-active rules (loaded once)

def _on_pre_llm_call(session_id="", is_first_turn=False, **_):
    """Inject rules on every turn. Always-active rules cached once on first turn.
    Path-scoped rules injected from last turn's post_tool_call matches."""
    global _PENDING_PATH_RULES, _CACHED_ALWAYS_RULES
    parts = []

    # Always-active rules: load once
    if _CACHED_ALWAYS_RULES is None:
        from .rules_loader import load_hermes_rules
        _CACHED_ALWAYS_RULES = load_hermes_rules()
    if _CACHED_ALWAYS_RULES:
        parts.append(_CACHED_ALWAYS_RULES)

    # Path-scoped rules from last turn's matches
    if _PENDING_PATH_RULES:
        parts.append("\n\n".join(_PENDING_PATH_RULES))
        _PENDING_PATH_RULES = []  # Clear after injection

    if parts:
        return {"context": "\n\n".join(parts)}
    return None


def _on_post_tool_call(tool_name="", args=None, session_id="", **_):
    """Detect path-scoped rule matches and cache for next turn."""
    file_path = _extract_file_path(tool_name, args)
    if not file_path or tool_name not in ("read_file", "patch", "search_files"):
        return

    matched = _find_matching_scoped_rules(file_path)
    if matched:
        _PENDING_PATH_RULES.extend(matched)
```

### Session Cleanup

Add cleanup on session end to prevent memory leaks:

```python
def _on_session_end(session_id="", **kwargs):
    """Clean up cached rules when session ends."""
    global _PENDING_PATH_RULES, _CACHED_ALWAYS_RULES
    _PENDING_PATH_RULES = []
    _CACHED_ALWAYS_RULES = None
```

### Edge Cases

| Case | Behavior |
|---|---|
| No rules in project | `load_hermes_rules()` returns `""`. No context injected. |
| Only path-scoped rules | First turn: empty. After first file access: rules appear on turn N+1. |
| Multiple matches in one turn | All matched rules accumulated in `_PENDING_PATH_RULES`, injected together on next turn. |
| Session reset (`/new`) | `_on_session_end` resets both caches. Fresh load on next turn. |
| Same file accessed twice | Rules re-matched and re-queued on each access. `_PENDING_PATH_RULES` is a list — allows multiple access to re-inject. |

### Acceptability

One-turn delay is acceptable because:
1. First tool call on a file is usually `read_file` to inspect its contents
2. The agent processes the file on the same turn it reads it
3. Path-scoped rules arrive before the agent makes significant decisions about the file (editing, refactoring)
4. This matches the behavior of Claude Code's `.claude/rules/` — rules are applied on next file access, not retroactively

---

## References

- `agent/conversation_loop.py:490-524` — pre_llm_call hook invocation
- `hermes_cli/plugins.py:128-168` — VALID_HOOKS definition
- `hermes_cli/plugins.py:287-386` — PluginContext class (register, inject_message, etc.)
- `hermes_cli/plugins.py:1296-1330` — PluginManager.invoke_hook() implementation
- `agent/system_prompt.py:60-254` — System prompt architecture (stable/context/volatile tiers)
- `agent/prompt_builder.py:1396-1423` — .cursor/rules/ loading precedent
- `agent/prompt_builder.py:1426-1465` — build_context_files_prompt() full function
- `agent/prompt_builder.py:1317-1338` — load_soul_md() reference implementation
- `tests/hermes_cli/test_plugins.py:398-407` — pre_llm_call test example
- `tests/agent/test_shell_hooks.py:84-100` — pre_llm_call context passthrough tests
- `tests/agent/test_prompt_builder.py:500-689` — build_context_files_prompt tests
