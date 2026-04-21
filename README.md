# owl-api

FastAPI wrapper around [mdlacasse/Owl](https://github.com/mdlacasse/Owl) with
state-tax post-processing. Backs the Retirement tab in FinanceKeeper.

License: GPL-3.0-or-later (inherits from Owl).

## Run locally (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn owl_api.main:app --reload --host 127.0.0.1 --port 8787
```

## Endpoints

- `GET  /health` — liveness
- `POST /optimize` — submit a scenario, returns job id
- `GET  /jobs/{job_id}` — poll status + result
- `GET  /states` — list supported state tax rules

## State tax

Owl models federal + IRMAA + ACA but not state income tax. `owl_api.state_tax`
applies a post-solve adjustment per state code. Alabama is the only implementation
shipped today; add more in `state_tax.py`.

Alabama (AL) 2026 rules: 5% on ordinary income, 0% on Social Security,
0% on qualified distributions from IRAs/401(k)s/defined-benefit pensions after
age 65 (AL Code §40-18-19(a)(7) and §40-18-19.1).

## Deploy to mac-mini

See `docker/` directory and `compose.yml`. Host via Cloudflare Tunnel on the
mac-mini alongside the Matrix Formulation API.
