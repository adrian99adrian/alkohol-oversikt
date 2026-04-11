#!/usr/bin/env bash
set -euo pipefail

# ── Git hooks ───────────────────────────────────────────────────────
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/pre-commit 2>/dev/null || true
echo "Git hooks configured. Pre-commit hook is now active."

# ── Python dependencies ────────────────────────────────────────────
pip install -r requirements.txt
echo "Python dependencies installed."

# ── Frontend dependencies ──────────────────────────────────────────
if command -v npm >/dev/null 2>&1; then
  (cd web && npm install)
  echo "Frontend dependencies installed."
else
  echo "WARNING: npm not found — skipping frontend dependencies."
  echo "  Install Node.js to build the frontend: https://nodejs.org/"
fi
