# Anodet

Your machines generate data. Your technicians generate knowledge. Anodet connects the two.

## What it does

Anodet is procedure memory for an industrial maintenance shop. It ties an abnormal operating window to the procedure a technician actually used and whether that intervention worked. The next asset with the same sensor signature leads with that reviewed case. The OEM manual stays underneath, unchanged.

## Problem

Shops already collect readings. What they lose is the diagnosis, the cheaper order that worked last time, and the outcome. That knowledge stays in one person’s head, a spreadsheet, or a PDF. The next engine with the same signature starts from the expensive manual again.

## Solution

Detect an abnormal window, investigate with evidence and the shop procedure, resolve it, remember the outcome, reuse it. Isolation Forest only finds the window. The product is the remembered case.

## Core workflow

1. Sign in with your name and the shop passphrase.
2. Use the NASA demo fleet, or bring a shop CSV and mark the healthy hours.
3. Open the recommended asset at the warning hour.
4. Read evidence and the cited procedure.
5. Optionally draft a cheaper order. The server rejects invented steps.
6. Remember the case with an outcome.
7. Open the next matching asset. Shop memory leads.

## Architecture

The Next.js desk talks to FastAPI through `/backend`. FastAPI scores the fleet in memory and writes shop memory to SQLite. Optional Grok calls stay on the server. Docker publishes only the web port.

Where files live, and where to add a feature: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
Browser → Next.js :3000 → FastAPI :8000 → SQLite shop memory
                              ↓
                     Isolation Forest (RAM)
                     Grok (optional)
```

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind |
| Backend | FastAPI, scikit-learn Isolation Forest |
| Database | SQLite (`audit.db` locally, `anodet.db` in Docker) |
| AI | Optional xAI Grok-4 with template fallback |
| Infrastructure | Docker Compose, GitHub Actions |

## Local development

Terminal 1:

```powershell
cd services\api
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Terminal 2:

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:3000. Sign in with your name. On this machine the shop passphrase is `sample-shop` until you set `SHOP_PASSPHRASE`. The sign-in screen does not show that hint unless `SHOP_PASSPHRASE_HINT=1`.

```powershell
cd services\api
.\.venv\Scripts\python -m unittest discover -s tests -p "test_*.py"
cd ..\..\web
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Pilot host, HTTPS, and nightly backup: [docs/PILOT.md](docs/PILOT.md).

## Environment variables

Copy `.env.example` or `services/api/.env.example`. Never commit `.env`.

| Variable | Required | Purpose |
|---|---|---|
| `SHOP_PASSPHRASE` | Yes in production | Shared shop sign-in. Default `sample-shop`. |
| `SHOP_PASSPHRASE_HINT` | No | `1` shows the passphrase on sign-in. Keep `0` outside this machine. |
| `SHOP_ID` | No | Tenant key. Default `sample`. |
| `SHOP_NAME` | No | Desk label. |
| `DEMO_TOOLS` | No | `1` allows seed/reset/empty. Set `0` on a real shop. |
| `SHOP_LEAD` | No | This name is always lead. If empty, the first sign-in on a shop is lead. |
| `ANODET_DB` | No | SQLite path. |
| `ANODET_DATA` | No | NASA FD001 path. |
| `CORS_ORIGINS` | No | Browser origins allowed to call the API directly. |
| `XAI_API_KEY` | No | Server-side Grok. Template fallback if unset. |
| `XAI_MODEL` / `XAI_DRAFT_MODEL` | No | Default `grok-4`. |
| `API_PROXY_URL` | Web/Docker/Railway | Where the desk proxies `/backend`. Railway: `http://api.railway.internal:8000`. |

## Demo

See [docs/DEMO.md](docs/DEMO.md) for the 3–5 minute investor script.

**NASA path:** After sign-in, use the NASA demo fleet. Sample shop → Reset demo to empty. Open Engine 31. Draft a reorder with Grok. Remember this case. Open Engine 74. Shop memory leads.

**Shop path:** Bring `data/demo/marine-diesel-sample.csv`. Mark the healthy window. Remember a case. Open the other unit.

## Security

- Shared shop passphrase, compared with SHA-256 and `hmac.compare_digest`.
- Bearer tokens in SQLite, 12 hours, scoped to `SHOP_ID`.
- Author on a saved case comes from the session, not the request body.
- Sign-in is rate-limited. Grok-style calls are rate-limited per member.
- Demo wipe/seed routes can be turned off with `DEMO_TOOLS=0`.
- First sign-in on a shop (or `SHOP_LEAD`) is lead. Later names are technicians: they remember cases and score later hours; they cannot Fit or wipe.
- API keys stay on the server. The Next app never sees `XAI_API_KEY`.
- Docker does not publish the API port. Put TLS on the web port only.

## Current MVP limitations

- One shop process (`SHOP_ID`). A second shop is another deployment or env, not self-serve signup.
- Isolation Forest and fleet scores live in RAM and rebuild on restart.
- Auth is a shared passphrase plus lead/technician, not SSO.
- SQLite, not Postgres. Fine for one shop; back up the file.
- No MQTT / live sensor bus. Later hours append from a file.
- Default passphrase is `sample-shop`. Change it before a public host.

## Roadmap

Already in this repo: shop-lead vs technician, later-hours append without a refit, Playwright NASA 31→74, SQLite backup script, Caddy overlay.

1. Hosted HTTPS with a real `SHOP_PASSPHRASE` and `DEMO_TOOLS=0` for a pilot.
2. Nightly backup of the SQLite file off-box.
3. Folder-watch or MQTT that POSTs `/assets/append`.
4. Postgres when a second live shop cannot share one file.
5. Export a remembered case as a one-page job card.

## Deployment

**Railway (HTTPS, no domain of your own):** [docs/RAILWAY.md](docs/RAILWAY.md). Two services from this repo: `api` (private + SQLite volume) and `web` (public). Set `SHOP_PASSPHRASE` in the Railway UI, not in git.

**This machine / your VM:**

```powershell
docker compose up --build
```

Publish only port 3000. Terminate TLS on a reverse proxy. Set `SHOP_PASSPHRASE`, `CORS_ORIGINS`, and pass `XAI_API_KEY` to the API service if you want Grok on that host. A domain you own: [docs/PILOT.md](docs/PILOT.md).
