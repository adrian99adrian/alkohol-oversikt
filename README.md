# alkohol-oversikt

A static website showing when beer sales close in Norwegian municipalities and when Vinmonopolet (state liquor stores) are open.

## Development setup

```bash
# Clone and install
git clone https://github.com/adrian99adrian/alkohol-oversikt.git
cd alkohol-oversikt
pip install -r requirements.txt
cd web && npm install && cd ..

# Enable pre-commit hooks (run once per machine)
git config core.hooksPath scripts/hooks
```

The pre-commit hook runs automatically before every `git commit` and checks:

1. **Lint** — `ruff check` + `ruff format` on the whole project
2. **Gitignore guard** — blocks accidentally staged gitignored files
3. **Generated data freshness** — ensures municipality data hasn't been overwritten by test output
