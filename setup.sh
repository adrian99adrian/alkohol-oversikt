#!/usr/bin/env bash
set -euo pipefail

# ── Git hooks ───────────────────────────────────────────────────────
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/pre-commit 2>/dev/null || true
echo "Git hooks configured. Pre-commit hook is now active."

# ── Python dependencies ────────────────────────────────────────────
# On Windows (Git Bash / WSL), pip.exe is the native Windows pip.
# Prefer pip.exe so we don't accidentally hit WSL's locked-down Python.
if command -v pip.exe >/dev/null 2>&1; then
  PIP=pip.exe
elif command -v pip >/dev/null 2>&1; then
  PIP=pip
else
  echo "ERROR: pip not found. Install Python first: https://www.python.org/"
  exit 1
fi

if $PIP install -r requirements.txt 2>/dev/null; then
  echo "Python dependencies installed."
elif $PIP install --user -r requirements.txt; then
  echo "Python dependencies installed (--user)."
else
  echo "ERROR: could not install Python dependencies."
  echo "  Try using a virtual environment: python -m venv .venv && source .venv/bin/activate"
  exit 1
fi

# ── Frontend dependencies ──────────────────────────────────────────
if command -v npm >/dev/null 2>&1; then
  (cd web && npm install)
  echo "Frontend dependencies installed."
else
  echo "WARNING: npm not found — skipping frontend dependencies."
  echo "  Install Node.js to build the frontend: https://nodejs.org/"
fi
