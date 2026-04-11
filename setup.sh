#!/usr/bin/env bash
set -euo pipefail

# ── Git hooks ───────────────────────────────────────────────────────
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/pre-commit 2>/dev/null || true
echo "Git hooks configured. Pre-commit hook is now active."

# ── Python dependencies ────────────────────────────────────────────
# Try normal pip first; fall back to --user if blocked by PEP 668
# (externally-managed-environment, common on Debian/Ubuntu and WSL).
if pip install -r requirements.txt 2>/dev/null; then
  echo "Python dependencies installed."
elif pip install --user -r requirements.txt 2>/dev/null; then
  echo "Python dependencies installed (--user)."
else
  echo "ERROR: could not install Python dependencies."
  echo "  Try: python -m pip install -r requirements.txt"
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
