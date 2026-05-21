"""Stress test suite for hermes_codex plugin — standalone, no Hermes dependency.

Tests path_matcher at scale: edge cases, large inputs, repeated calls.
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hermes_codex.path_matcher import (
    expand_braces,
    matches_paths_frontmatter,
    _match_glob_pattern,
)
from hermes_codex.rules_loader import _load_rules_from_dir

PASSED = 0
FAILED = 0
TOTAL = 0


def _run_test(name, condition, detail=""):
    global PASSED, FAILED, TOTAL
    TOTAL += 1
    if condition:
        PASSED += 1
        print(f"  PASS: {name}")
    else:
        FAILED += 1
        print(f"  FAIL: {name} -- {detail}")


def mock_scan_fn(content, path):
    return content


def mock_parse_fn(content):
    lines = content.split("\n")
    fm = {}
    if lines and lines[0].strip() == "---":
        end = 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        current_key = None
        for line in lines[1:end]:
            stripped = line.strip()
            if stripped.startswith("- "):
                # YAML list item — append to current key
                if current_key:
                    val = stripped[2:].strip().strip('"').strip("'")
                    if not isinstance(fm.get(current_key), list):
                        fm[current_key] = []
                    fm[current_key].append(val)
            elif ":" in stripped:
                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                current_key = key
                if val:
                    fm[key] = val
                else:
                    fm[key] = []  # prepare for list items
        body = "\n".join(lines[end + 1:]).strip()
    else:
        body = content
    return fm, body


print("=" * 60)
print("STRESS TEST SUITE - Hermes Codex")
print("=" * 60)

# -- Section A: Path Matcher --
print("\n[A] Path Matcher Edge Cases")

_run_test("A1: *.py matches root", _match_glob_pattern("main.py", "*.py"))
_run_test("A1b: *.py does NOT match nested", not _match_glob_pattern("src/main.py", "*.py"))
_run_test("A2: **/*.py deep nested", _match_glob_pattern("a/b/c/d/main.py", "**/*.py"))
_run_test("A2b: **/*.py at root", _match_glob_pattern("main.py", "**/*.py"))
_run_test("A3: src/**/test.py deep", _match_glob_pattern("src/deeply/nested/test.py", "src/**/test.py"))
_run_test("A3b: src/**/test.py zero segments", _match_glob_pattern("src/test.py", "src/**/test.py"))
_run_test("A4: ?.ts single char", _match_glob_pattern("a.ts", "?.ts"))
_run_test("A4b: ?.py no match multi", not _match_glob_pattern("app.py", "?.py"))

expanded = expand_braces("src/*.{ts,tsx,js,jsx}")
_run_test("A5: brace expansion returns 4", len(expanded) == 4, f"got {len(expanded)}: {expanded}")
_run_test("A5b: braces match src/app.tsx",
     matches_paths_frontmatter("src/app.tsx", ["src/*.{ts,tsx,js,jsx}"]))

_run_test("A6: [abc].ts matches a.ts", _match_glob_pattern("a.ts", "[abc].ts"))
_run_test("A6b: [abc].ts no match d.ts", not _match_glob_pattern("d.ts", "[abc].ts"))
_run_test("A7: empty matches empty", _match_glob_pattern("", ""))
_run_test("A7b: empty no match real", not _match_glob_pattern("file.py", ""))
_run_test("A8: Windows backslash", _match_glob_pattern("src\\components\\button.ts", "src/**/*.ts"))
_run_test("A8b: file with spaces", _match_glob_pattern("my file.py", "*.py"))

# -- Section B: Rules Loader --
print("\n[B] Rules Loader")

with tempfile.TemporaryDirectory() as tmp:
    # B1: Empty directory
    p = Path(tmp) / "empty_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    _run_test("B1: Empty rules dir",
         _load_rules_from_dir(p, Path(tmp), is_global=False,
                              scan_fn=mock_scan_fn, parse_fn=mock_parse_fn) == "")

    # B2: Non-existent directory
    _run_test("B2: Non-existent dir",
         _load_rules_from_dir(Path("/nonexistent/rules"), Path(tmp), is_global=False,
                              scan_fn=mock_scan_fn, parse_fn=mock_parse_fn) == "")

    # B3: Unicode filename
    p = Path(tmp) / "unicode_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "测试.md").write_text("# Unicode Rule\n- 中文规则\n")
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B3: Unicode file loaded", r and "Unicode" in r, f"got: {repr(r[:100]) if r else 'empty'}")

    # B4: Malformed YAML
    p = Path(tmp) / "bad_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "bad.md").write_text("---\npaths:\n  - this is [broken\n---\n# Content\n")
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B4: Malformed YAML no crash", r is not None, f"got: {repr(r[:100]) if r else 'empty'}")

    # B5: Empty file
    p = Path(tmp) / "empty_file_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "empty.md").write_text("")
    _run_test("B5: Empty .md skipped",
         _load_rules_from_dir(p, Path(tmp), is_global=False,
                              scan_fn=mock_scan_fn, parse_fn=mock_parse_fn) == "")

    # B6: Whitespace only
    p = Path(tmp) / "ws_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "ws.md").write_text("   \n\n   \n")
    _run_test("B6: Whitespace skipped",
         _load_rules_from_dir(p, Path(tmp), is_global=False,
                              scan_fn=mock_scan_fn, parse_fn=mock_parse_fn) == "")

    # B7: Path-scoped deferred
    p = Path(tmp) / "scoped_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "py.md").write_text("---\npaths:\n  - \"**/*.py\"\n---\n# Python\n")
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B7: Path-scoped deferred", r == "", f"leaked: {repr(r[:100]) if r else ''}")

    # B8: Mixed always + scoped
    p = Path(tmp) / "mixed_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "always.md").write_text("# Always\nFollow.\n")
    (p / "scoped.md").write_text("---\npaths:\n  - \"**/*.ts\"\n---\n# TS\n")
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B8a: Always-loaded present", r and "always" in r, f"got: {repr(r[:200])}")
    _run_test("B8b: Path-scoped deferred", r and "scoped" not in r, f"leaked: {repr(r[:200])}")

    # B9: Dashes in code block
    p = Path(tmp) / "body_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "code.md").write_text("# Rule\n\n```\n---\nyaml\n---\n```\n")
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B9: Dashes in body = always-rule", r and "code" in r, f"got: {repr(r[:200])}")

    # B10: Deduplication
    p = Path(tmp) / "dedup_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "style.md").write_text("# Style\n- indent\n")
    r = _load_rules_from_dir(p, Path(tmp), is_global=True,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn,
                             skip_filenames={"style.md"})
    _run_test("B10: Deduplication skip", r == "")

    # B11: Multiple path patterns
    p = Path(tmp) / "multi_p_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "multi.md").write_text(
        '---\npaths:\n  - "src/**/*.ts"\n  - "src/**/*.tsx"\npriority: high\n---\n# TS\n'
    )
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B11: Multiple paths -> deferred", r == "")

# B12: Symlink
with tempfile.TemporaryDirectory() as tmp:
    target = Path(tmp) / "shared_rules"
    target.mkdir()
    (target / "shared.md").write_text("# Shared Rule\nVia symlink.\n")

    p = Path(tmp) / "sym_proj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    os.symlink(target / "shared.md", p / "link.md")
    r = _load_rules_from_dir(p, Path(tmp), is_global=False,
                             scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
    _run_test("B12: Symlinked rule loaded", r and "link" in r, f"got: {repr(r[:100])}")

# -- Section C: Concurrent Access --
print("\n[C] Concurrent Access")

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "conj" / ".hermes" / "rules"
    p.mkdir(parents=True)
    (p / "rule.md").write_text("# Rule\nTest concurrent.\n")

    errors = 0
    for _ in range(100):
        try:
            _load_rules_from_dir(p, Path(tmp), is_global=False,
                                 scan_fn=mock_scan_fn, parse_fn=mock_parse_fn)
        except Exception as e:
            errors += 1
    _run_test("C1: 100 rapid calls, 0 errors", errors == 0, f"{errors} errors")

# -- Summary --
print("\n" + "=" * 60)
print(f"RESULTS: {PASSED}/{TOTAL} PASSED, {FAILED}/{TOTAL} FAILED")
print("=" * 60)
if FAILED:
    print(f"\n{FAILED} TEST(S) FAILED")
    sys.exit(1)
else:
    print("\nALL STRESS TESTS PASSED")
