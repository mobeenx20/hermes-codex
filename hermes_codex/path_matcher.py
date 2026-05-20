"""Path-matching for paths: frontmatter in .hermes/rules/ files.

Supports:
- **/*.ts (recursive glob)
- src/**/* (all files in a directory)
- *.md (root only)
- src/**/*.{ts,tsx} (brace expansion)
"""

import fnmatch
import re
from typing import List


def expand_braces(pattern: str) -> List[str]:
    """Expand brace expressions like *.{ts,tsx} into multiple patterns."""
    brace_match = re.search(r'\{([^}]+)\}', pattern)
    if not brace_match:
        return [pattern]
    alternatives = [alt.strip() for alt in brace_match.group(1).split(',')]
    expanded = []
    for alt in alternatives:
        new_pattern = pattern[:brace_match.start()] + alt + pattern[brace_match.end():]
        expanded.extend(expand_braces(new_pattern))
    return expanded


def matches_paths_frontmatter(file_path: str, patterns: List[str]) -> bool:
    """Check if a file path matches any pattern from paths: frontmatter."""
    file_path = file_path.replace('\\', '/')
    for pattern in patterns:
        for pat in expand_braces(pattern):
            if _match_glob_pattern(file_path, pat):
                return True
    return False


def _match_glob_pattern(file_path: str, pattern: str) -> bool:
    """Match a file path against a glob pattern with ** support.

    Strategy: Convert glob pattern to regex, handling ** as recursive match.
    Order of replacements matters — ** must be handled BEFORE single *.
    """
    file_path = file_path.replace('\\', '/')

    # Exact match (no wildcards at all — must exclude * ? [ too)
    if not any(c in pattern for c in '*?['):
        return file_path == pattern

    # Convert glob to regex
    regex = ''
    i = 0
    while i < len(pattern):
        c = pattern[i]

        if c == '*':
            # Check for **
            if i + 1 < len(pattern) and pattern[i + 1] == '*':
                # ** — match zero or more path segments
                # Skip both stars
                i += 2
                # Skip trailing slash if present (e.g., **/, ** /)
                if i < len(pattern) and pattern[i] == '/':
                    i += 1
                # ** at end of pattern matches everything (including file name)
                if i >= len(pattern):
                    regex += '.*'
                else:
                    # **/ followed by more — match zero or more directory levels
                    regex += '(.+/)?'
            else:
                # Single * — match anything except /
                regex += '[^/]*'
                i += 1
        elif c == '?':
            # ? — match any single character except /
            regex += '[^/]'
            i += 1
        elif c == '[':
            # [...] character class — copy literally (not escaped for regex)
            j = i + 1
            while j < len(pattern) and pattern[j] != ']':
                j += 1
            j += 1  # include ]
            regex += pattern[i:j]
            i = j
        else:
            # Regular character — escape for regex
            regex += re.escape(c)
            i += 1

    # Anchored match
    try:
        return bool(re.match(f'^{regex}$', file_path))
    except re.error:
        return False
