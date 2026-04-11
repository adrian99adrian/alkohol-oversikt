# alkohol-oversikt

![CI](https://github.com/adrian99adrian/alkohol-oversikt/actions/workflows/ci.yml/badge.svg)
![Build & Deploy](https://github.com/adrian99adrian/alkohol-oversikt/actions/workflows/build-deploy.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

A static website showing when beer sales close in Norwegian municipalities and when Vinmonopolet (state liquor stores) are open.

**Live site:** [adrian99adrian.github.io/alkohol-oversikt](https://adrian99adrian.github.io/alkohol-oversikt)

## Disclaimer

This site is for informational purposes only. Sale times and store hours may be inaccurate, outdated, or incomplete. Always check your municipality's official regulations and [Vinmonopolet's website](https://www.vinmonopolet.no/) for authoritative information. The authors accept no responsibility for errors in the data presented.

## Tech stack

- **Data pipeline** — Python scripts that generate holidays, fetch Vinmonopolet hours, and calculate per-municipality sale times
- **Frontend** — [Astro](https://astro.build/) static site with Tailwind CSS
- **Hosting** — GitHub Pages, rebuilt automatically on push to `main`

## Development setup

```bash
git clone https://github.com/adrian99adrian/alkohol-oversikt.git
cd alkohol-oversikt
bash setup.sh
```

`setup.sh` configures git hooks, installs Python dependencies, and installs frontend dependencies (requires Node.js).

```bash
# Run the data pipeline
python scripts/build_calendar.py
python scripts/fetch_vinmonopolet.py
python scripts/build_municipality.py --all

# Run tests
pytest -q tests/ -m "not slow"    # Python tests
cd web && npm test                 # Frontend tests (Vitest)

# Start dev server
cd web && npm run dev
```

The pre-commit hook runs automatically before every commit and checks linting, tests, gitignore violations, and data freshness.


## License

[MIT](LICENSE)
