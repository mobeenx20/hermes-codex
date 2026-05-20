"""Unit tests for rules_loader module.

Uses mocking to avoid Hermes Agent runtime dependencies.
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hermes_codex.rules_loader import _load_rules_from_dir


# ---- Fixtures ----

@pytest.fixture
def mock_scan_fn():
    """Mock _scan_context_content — passes through content unchanged."""
    return MagicMock(side_effect=lambda content, path: content)


@pytest.fixture
def mock_parse_fn():
    """Mock parse_frontmatter."""
    def _parse(content):
        lines = content.split("\n")
        fm = {}
        if lines and lines[0].strip() == "---":
            end = 1
            while end < len(lines) and lines[end].strip() != "---":
                end += 1
            for line in lines[1:end]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if val.startswith("["):
                        import json
                        val = json.loads(val.replace("'", '"'))
                    fm[key] = val
            body = "\n".join(lines[end + 1:]).strip()
        else:
            body = content
        return fm, body
    return _parse


@pytest.fixture
def temp_rules_dir(tmp_path):
    """Create a temporary .hermes/rules/ directory."""
    d = tmp_path / ".hermes" / "rules"
    d.mkdir(parents=True)
    return d


# ---- Tests ----

class TestLoadRulesFromDir:
    """Direct tests of _load_rules_from_dir (core logic)."""

    def test_empty_directory(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert result == ""

    def test_always_loaded_rule(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "style.md").write_text("# Style\n- 2-space indent\n")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert "style" in result
        assert "2-space" in result

    def test_path_scoped_deferred(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "py.md").write_text(
            "---\npaths:\n  - \"**/*.py\"\n---\n# Python rules\n"
        )
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert result == ""  # Path-scoped rules are deferred

    def test_mixed_rules(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "always.md").write_text("# Always\nFollow.\n")
        (temp_rules_dir / "scoped.md").write_text(
            "---\npaths:\n  - \"**/*.ts\"\n---\n# TS\n"
        )
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert "always" in result
        assert "scoped" not in result

    def test_empty_file_skipped(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "empty.md").write_text("")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert result == ""

    def test_whitespace_only_skipped(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "ws.md").write_text("   \n\n   \n")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert result == ""

    def test_malformed_yaml_handled(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "bad.md").write_text("---\npaths:\n  - this is [broken\n---\n# Content\n")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        # Should not crash — malformed YAML means frontmatter not parsed, treated as body
        assert result is not None

    def test_dashes_in_codeblock_not_frontmatter(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "code.md").write_text("# Rule\n\n```\n---\nyaml\n---\n```\n")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert result and "code" in result

    def test_deduplication_skip_filenames(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "style.md").write_text("# Style\n- indent\n")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
            skip_filenames={"style.md"},
        )
        assert result == ""

    def test_nonexistent_directory(self, mock_scan_fn, mock_parse_fn):
        result = _load_rules_from_dir(
            Path("/nonexistent/rules"), Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert result == ""

    def test_unicode_filename(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "测试.md").write_text("# Unicode Rules\n- 中文规则\n")
        result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert "Unicode" in result

    def test_global_label_in_output(self, temp_rules_dir, mock_scan_fn, mock_parse_fn):
        (temp_rules_dir / "rule.md").write_text("# Test\nContent\n")
        global_result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=True,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        project_result = _load_rules_from_dir(
            temp_rules_dir, Path.cwd(), is_global=False,
            scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
        )
        assert "Global" in global_result
        assert "Project" in project_result
