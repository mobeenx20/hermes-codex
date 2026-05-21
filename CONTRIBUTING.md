# Contributing to Hermes Codex

## Development Setup

```bash
git clone https://github.com/mobeenx20/hermes-codex.git
cd hermes-codex
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# Run specific test
pytest tests/test_path_matcher.py -v

# Run stress tests
python tests/stress_test.py
```

## Code Style

- Python 3.10+ type hints on all public functions
- 100-character line limit
- Docstrings on all modules and public functions
- Follow existing patterns in `hermes_codex/`

## Pull Request Process

1. Ensure tests pass with `pytest tests/ -v`
2. Update `CHANGELOG.md` with your changes
3. Bump version in `plugin.yaml` and `pyproject.toml` (semver)
4. Open PR with a clear description of the change

## Plugin Architecture Notes

- `hermes_codex/` is both a Python package AND a Hermes plugin
- Installation works via both `pip install` and direct copy to `~/.hermes/hermes-agent/plugins/`
- The `register()` function in `__init__.py` is Hermes' plugin entry point
- All hooks and commands are registered through the `ctx` object passed to `register()`
