"""Unit tests for path_matcher module — pure, no Hermes dependency."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hermes_codex.path_matcher import expand_braces, matches_paths_frontmatter, _match_glob_pattern


class TestExpandBraces:
    """Brace expansion {a,b,c} → multiple patterns."""

    def test_no_braces(self):
        assert expand_braces("src/*.py") == ["src/*.py"]

    def test_single_brace(self):
        result = expand_braces("src/*.{ts,tsx}")
        assert len(result) == 2
        assert "src/*.ts" in result
        assert "src/*.tsx" in result

    def test_multi_brace(self):
        result = expand_braces("**/*.{js,jsx,ts,tsx}")
        assert len(result) == 4

    def test_nested_braces(self):
        result = expand_braces("{a,{b,c}}")  # simple nested
        assert len(result) >= 2


class TestMatchGlobPattern:
    """Core glob matching — _match_glob_pattern(file_path, pattern)."""

    def test_exact_match_no_wildcards(self):
        assert _match_glob_pattern("main.py", "main.py")

    def test_single_star_root(self):
        assert _match_glob_pattern("main.py", "*.py")
        assert not _match_glob_pattern("src/main.py", "*.py")

    def test_double_star_deep_nested(self):
        assert _match_glob_pattern("a/b/c/d/main.py", "**/*.py")

    def test_double_star_at_root(self):
        assert _match_glob_pattern("main.py", "**/*.py")

    def test_double_star_mid_pattern(self):
        assert _match_glob_pattern("src/deeply/nested/test.py", "src/**/test.py")

    def test_double_star_zero_segments(self):
        assert _match_glob_pattern("src/test.py", "src/**/test.py")

    def test_question_mark_single_char(self):
        assert _match_glob_pattern("a.ts", "?.ts")
        assert not _match_glob_pattern("app.py", "?.py")

    def test_character_class(self):
        assert _match_glob_pattern("a.ts", "[abc].ts")
        assert not _match_glob_pattern("d.ts", "[abc].ts")

    def test_empty_strings(self):
        assert _match_glob_pattern("", "")

    def test_file_with_spaces(self):
        assert _match_glob_pattern("my file.py", "*.py")

    def test_file_with_dots(self):
        assert _match_glob_pattern("file.test.spec.py", "**/*.py")

    def test_windows_backslash_normalized(self):
        assert _match_glob_pattern("src\\components\\button.ts", "src/**/*.ts")


class TestMatchesPathsFrontmatter:
    """High-level matches_paths_frontmatter(file_path, patterns)."""

    def test_single_pattern_match(self):
        assert matches_paths_frontmatter("src/api/handler.py", ["src/**/*.py"])
        assert not matches_paths_frontmatter("src/api/handler.ts", ["src/**/*.py"])

    def test_brace_expansion_match(self):
        assert matches_paths_frontmatter("src/app.tsx", ["src/*.{ts,tsx,js,jsx}"])
        assert matches_paths_frontmatter("src/app.ts", ["src/*.{ts,tsx,js,jsx}"])

    def test_multiple_patterns(self):
        patterns = ["src/api/**/*.py", "tests/**/*.py"]
        assert matches_paths_frontmatter("src/api/v1/users.py", patterns)
        assert matches_paths_frontmatter("tests/test_users.py", patterns)
        assert not matches_paths_frontmatter("frontend/app.tsx", patterns)

    def test_complex_project_structure(self):
        """Real-world scenario: monorepo with mixed languages."""
        patterns = ["packages/*/src/**/*.ts", "packages/*/src/**/*.tsx"]
        assert matches_paths_frontmatter("packages/core/src/index.ts", patterns)
        assert matches_paths_frontmatter(
            "packages/ui/src/components/Button.tsx", patterns
        )
        assert not matches_paths_frontmatter("packages/core/tests/test.ts", patterns)

    def test_recursive_all_files(self):
        assert matches_paths_frontmatter("any/deep/path/file.txt", ["**"])
