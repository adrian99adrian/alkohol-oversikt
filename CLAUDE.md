# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A static, open source website showing when beer sales close in Norwegian municipalities and when Vinmonopolet (state liquor stores) are open. Built with Python (data pipeline) + Astro (static frontend), deployed to GitHub Pages.

## Commands

```bash
# Python pipeline
pip install -r requirements.txt
python scripts/build_calendar.py          # Generate holidays + day types
python scripts/fetch_vinmonopolet.py      # Fetch store hours from API
python scripts/build_municipality.py --all # Calculate sales times per municipality
python scripts/validate_data.py           # Validate all generated data

# Tests
pytest -q tests/ -m "not slow"           # Run all tests (default)
pytest -q tests/unit/ -m "not slow"      # Unit tests only
pytest -q tests/integration/              # Integration tests only
pytest -q tests/infra/                    # Infrastructure tests only
pytest -q tests/ -m slow                  # Network tests only (hits real APIs)

# Linting
ruff check .                              # Lint Python
ruff format --check .                     # Check formatting

# Frontend (requires Node.js)
cd web && npm install                     # Install frontend dependencies
cd web && npm run dev                     # Local dev server
cd web && npm run build                   # Build static site to docs/
```

## Workflow

1. **Always run `pytest -q tests/ -m "not slow"` before committing** — no exceptions
2. **Always run `ruff check . && ruff format --check .` before committing** — no exceptions
3. **Every new function must have unit tests** — no exceptions
4. **New functionality spanning multiple scripts requires integration tests**
5. **Never push directly to `main`** — ask for confirmation first
6. **PRs to feature branches** — push without asking
7. **Never merge PRs** — I will handle all merges manually
8. **Update relevant docs before committing** — `docs/`, `CLAUDE.md`, `CHANGELOG.md`
9. **Test-driven development** — write tests first, then implement

## Communication

- Always ask clarifying questions about design decisions rather than assuming
- When unsure about scope, ask before implementing
- Explain frontend concepts since this is a learning project for the user

## Language Conventions

- All display text on the website must be in Norwegian
- All variables, code, comments, and other repository files must be in English
- Git commit messages in English
