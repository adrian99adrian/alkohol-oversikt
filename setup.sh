#!/usr/bin/env bash
set -euo pipefail

# ── Git hooks ───────────────────────────────────────────────────────
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/pre-commit 2>/dev/null || true
echo "Git hooks configured. Pre-commit hook is now active."

# ── Python dependencies ────────────────────────────────────────────
# Prefer "python -m pip" so we respect an active virtualenv.
# Fall back to pip.exe (Windows native) then pip.
if python -m pip --version >/dev/null 2>&1; then
  PIP="python -m pip"
elif command -v pip.exe >/dev/null 2>&1; then
  PIP=pip.exe
elif command -v pip >/dev/null 2>&1; then
  PIP=pip
else
  echo "ERROR: pip not found. Install Python first: https://www.python.org/"
  exit 1
fi

if ! $PIP install -r requirements.txt; then
  echo ""
  echo "pip install failed. Retrying with --user..."
  if ! $PIP install --user -r requirements.txt; then
    echo ""
    echo "ERROR: could not install Python dependencies."
    echo "  Try using a virtual environment: python -m venv .venv && source .venv/bin/activate"
    exit 1
  fi
  echo "Python dependencies installed (--user)."
else
  echo "Python dependencies installed."
fi

# ── Frontend dependencies ──────────────────────────────────────────
if command -v npm >/dev/null 2>&1; then
  (cd web && npm install)
  # Generate .astro/types.d.ts so TypeScript/IDE type-checking works
  # without needing `npm run dev` first.
  (cd web && npx astro sync)
  echo "Frontend dependencies installed."
else
  echo "WARNING: npm not found — skipping frontend dependencies."
  echo "  Install Node.js to build the frontend: https://nodejs.org/"
fi
