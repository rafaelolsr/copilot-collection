# Python project setup with uv + ruff + mypy + pytest

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> **Sources**: https://docs.astral.sh/uv/, https://docs.astral.sh/ruff/

## When to use this pattern

Starting a new Python project for an AI/LLM application. Result: `uv sync` installs everything, `pytest` runs tests, `ruff check` lints, `mypy --strict` type-checks. All four configured to play together.

## Directory layout

```
my-agent/
├── pyproject.toml
├── .python-version
├── .env.example
├── .gitignore
├── README.md
├── src/
│   └── my_agent/
│       ├── __init__.py
│       └── client.py
└── tests/
    ├── __init__.py
    └── unit/
        └── test_client.py
```

`src/` layout (not flat) is the modern default — prevents accidental imports of test code, enforces editable installs to behave like real packages.

## pyproject.toml

```toml
[project]
name = "my-agent"
version = "0.1.0"
description = "AI agent built on Claude with structured output"
readme = "README.md"
requires-python = ">=3.12,<3.14"

dependencies = [
    "anthropic>=0.40.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "instructor>=1.4.0",
    "tenacity>=8.5.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-mock>=3.14.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
    "pre-commit>=3.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_agent"]

# ---------- ruff ----------

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "W",   # pycodestyle warnings
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "S",   # flake8-bandit (security)
    "ASYNC",  # flake8-async
    "RUF", # ruff-specific
]
ignore = [
    "E501",  # line too long — formatter handles
    "S101",  # assert OK in tests (per-file override below)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106"]  # assert + hardcoded passwords OK in tests
"src/my_agent/__init__.py" = ["F401"]   # re-exports

# ---------- mypy ----------

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
disallow_any_generics = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # tests can be untyped

# ---------- pytest ----------

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "eval: stochastic evals (slow, costs $)",
    "integration: requires external services",
]
addopts = "-v --strict-markers --cov=src/my_agent --cov-report=term-missing"
```

## .python-version

```
3.12
```

uv reads this and uses the matching interpreter. Keeps everyone on the same version.

## .gitignore

```
# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
*.egg-info/

# Virtual environments
.venv/

# Environment
.env
.env.local
.env.*.local

# Editors
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

## .env.example

```
# Copy to .env and fill in real values. Never commit .env.
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=
LOG_LEVEL=INFO
```

## src/my_agent/__init__.py

```python
"""my-agent — AI agent on Claude."""
from my_agent.client import ClaudeClient

__all__ = ["ClaudeClient"]
__version__ = "0.1.0"
```

## src/my_agent/client.py

```python
"""Stub — replace with the actual client implementation."""
from __future__ import annotations

import anthropic


class ClaudeClient:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic()

    async def hello(self) -> str:
        return "hello"
```

## tests/unit/test_client.py

```python
import pytest
from my_agent.client import ClaudeClient


@pytest.mark.asyncio
async def test_hello() -> None:
    client = ClaudeClient()
    assert await client.hello() == "hello"
```

## Initial commands

```bash
# Install uv if not already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install everything
uv venv
uv pip install -e ".[dev]"

# Verify everything works
uv run ruff check
uv run mypy src/
uv run pytest

# Daily workflow
uv run pytest                    # tests
uv run ruff check --fix          # lint + auto-fix
uv run ruff format               # format
uv run mypy src/                 # type check
```

## pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-requests]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
```

```bash
uv run pre-commit install
```

## Done when

- `uv sync` (or `uv pip install -e ".[dev]"`) succeeds
- `uv run pytest` runs (even with 0 real tests)
- `uv run ruff check` passes on generated files
- `uv run mypy src/` passes
- `.env` is in `.gitignore`
- `.env.example` exists with placeholder keys
- Importing the package works: `uv run python -c "import my_agent; print(my_agent.__version__)"`

## Anti-patterns

- Flat layout (`my_agent/` at root, not `src/my_agent/`)
- Pinning every dependency to an exact version (use `>=` in app code; pin only at deploy via `uv lock`)
- Mixing `pip` and `uv` in the same project (lockfiles diverge)
- `requirements.txt` instead of `pyproject.toml` in new projects
- Committing `.venv/` or `__pycache__/`
- mypy strict mode disabled with `# type: ignore` everywhere — fix the types instead
- ruff with no `select` (uses default rules; better to be explicit)

## See also

- `concepts/secrets-and-key-rotation.md` — `.env` handling
- `concepts/type-safety-python.md` — what `mypy --strict` enforces
- `concepts/testing-llm-code.md` — pytest test taxonomy
