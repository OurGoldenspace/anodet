# Architecture

Short map for a new engineer. The product is procedure memory: detect a window, investigate, resolve, remember, reuse.

## Repository

```
web/                 Next.js desk (UI, session, /backend rewrite)
  app/               App Router pages
  components/        Desk UI (one file per surface)
    lib/               API client, /backend proxy, shared types, labels
  e2e/               Playwright golden path
services/api/        FastAPI + Isolation Forest + SQLite
  app/               Runtime modules (see below)
  tests/             unittest
data/
  cmapss/            NASA FD001 labeled demo fleet
  demo/              Shop-path sample CSV
docs/                Product, pilot, audit
scripts/             Shop-memory backup
deploy/              Caddy TLS overlay (own VM)
.railway/            Optional Railway Infrastructure as Code
```

Keep this layout. Do not invent a parallel `frontend/` / `backend/` tree — Docker and Next already use `web/` and `services/api/`.

## Frontend (`web/`)

The desk is a single page. `app/page.tsx` mounts `CommandCenter`, which owns session, path (NASA vs shop), and which pane is open.

| File | Responsibility |
|---|---|
| `sign-in.tsx` | Name + shop passphrase |
| `path-gate.tsx` | NASA demo vs shop file |
| `fleet-list.tsx` | Detect · fleet |
| `engine-stage.tsx` | Investigate · engine chart |
| `case-panel.tsx` | Case blocks + remember |
| `shop-intake.tsx` | Preview, Fit, later hours |
| `pitch-drawer.tsx` | Investor brief (sample path) |
| `lib/api.ts` | `/backend` fetch + session storage |
| `lib/backend-proxy.ts` | Server-side proxy to FastAPI (runtime `API_PROXY_URL`) |
| `lib/types.ts` | Desk models (keep in sync with API JSON) |

New UI: add a component next to these, then wire it from `command-center.tsx`. Do not put scoring or SQLite access in the browser.

## Backend (`services/api/app/`)

| Module | Responsibility |
|---|---|
| `main.py` | Routes, CORS, lifespan, human error bodies |
| `auth.py` | Passphrase, tokens, lead vs technician, rate limits |
| `detect.py` | Load FD001, Isolation Forest, health, signatures |
| `shop_intake.py` | CSV peek/map, Fit, append (no refit), parse manual |
| `cases.py` | Build/save case, shop-memory match, demo seed |
| `store.py` | SQLite shop memory (`SHOP_ID` on every row) |
| `manual.py` | OEM + shop procedure sections |
| `draft.py` | Cheaper-order draft + vocabulary check |
| `explain.py` | Optional Grok summary + template fallback |
| `limits.py` | Shared upload size |

Route → validate (Pydantic) → service module → `store.py`. Do not add a repository layer unless a second database appears.

## AI / ML

- **Training / fit:** Isolation Forest + scaler on healthy hours only (`detect.py`, `shop_intake.py`).
- **Inference:** score the rest of the unit; health is top-3 \|z\| + roll.
- **LLM:** optional, server-side, never the source of truth. Drafts are checked against the manual.
- NASA labels stay in `data/cmapss`. Shop samples stay in `data/demo`. Experiments do not belong on the request path.

## Data flow

```
CSV or FD001 → detect / shop_intake → in-memory Fleet
                                      → SQLite reviewed_fixes, manuals, imports
Browser → Next /backend → FastAPI → Fleet + SQLite
Save case → store.py → next matching signature reads that row first
```

Scores rebuild on process start. Remembered cases do not.

## Domain words

| Term | Meaning |
|---|---|
| **Asset** | Product noun for a machine under watch (copy, empty states). |
| **Engine** | Runtime record and API id (`/engines/{id}`, `EngineRecord`). NASA FD001 units and shop units share this shape. |
| **Sensor** | A mapped column with a direction (high / low). |
| **Dataset** | History file (FD001 or shop CSV). |
| **Analysis** | Detector scores and health series. |
| **Anomaly** | Abnormal operating window, not the product. |
| **Incident** | The warning hour a technician opens. |
| **Procedure** | Cited manual or shop steps. |
| **Case** | Evidence + procedure + technician decision. |
| **Outcome** | `worked` / `did_not` / `too_soon`. |
| **Evidence** | Sensor marks and readings on the case. |
| **Shop** | One tenant (`SHOP_ID`). |

Do not rename API `engine` fields to `asset` without a versioned change. Keep NASA turbofan names on FD001 labels, not as generic architecture.

## Demo vs shop

- NASA path trains on FD001 and is labeled “NASA demo” in the desk.
- Shop path Fits `data/demo/marine-diesel-sample.csv` or a customer file. Append scores later hours without refitting the healthy window.
- Demo wipe/seed live behind `DEMO_TOOLS`. Pilot shops set `DEMO_TOOLS=0`.

## Where new code goes

| Change | Place |
|---|---|
| Desk surface | `web/components/` |
| API JSON shape | `web/lib/types.ts` + the FastAPI handler |
| Scoring / signature | `detect.py` or `shop_intake.py` |
| Remember / reuse | `cases.py` + `store.py` |
| Auth / roles | `auth.py` |
| Sample files | `data/demo/` or `data/cmapss/` |
| Pilot / ops | `docs/`, `scripts/`, `deploy/` |
