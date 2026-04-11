# alkohol-oversikt

A static website showing when beer sales close in Norwegian municipalities and when Vinmonopolet (state liquor stores) are open.

## Development setup

```bash
git clone https://github.com/adrian99adrian/alkohol-oversikt.git
cd alkohol-oversikt
bash setup.sh
```

`setup.sh` configures git hooks, installs Python dependencies, and installs frontend dependencies (requires Node.js).

The pre-commit hook runs automatically before every `git commit` and checks:

1. **Gitignore guard** — blocks accidentally staged gitignored files
2. **Lint** — `ruff check` + `ruff format` on the whole project
3. **Tests** — `pytest` (excluding slow/network tests)
4. **Generated data freshness** — ensures municipality data hasn't been overwritten by test output
