# Technical audit

Date: 2026-09-26. Scope: MVP production-readiness pass on the existing Anodet desk.

## What was broken

- The desk clipped case and engine scroll (`overflow-hidden` + grid `min-height: auto`).
- Tester chrome put **Remove this asset** and **The venture** on the primary path.
- Isolation Forest was spoken as if it were the product.
- `/health` always returned ok, even if SQLite or the fleet was down.
- `POST /session` had no rate limit.
- Any member could wipe shop memory (`/demo/empty`) with no kill switch.
- CORS allowed every method and header.
- CI tested the API only. The web app could fail to typecheck unnoticed.
- README still described a turbofan dashboard more than procedure memory.
- Shop intake always said “Grok is…” even on the template path.

## What was fixed

- Desk panes scroll; drawers use `h-dvh` and `overflow-y-auto`.
- Remove lives under **More** / **Menu** as **Undo this import**. Investor brief is sample-path only.
- Product loop is visible: Detect → Investigate → Resolve → Remember → Reuse.
- NASA C-MAPSS is labeled as a demo fleet on the path gate, fleet cards, and engine stage.
- `/health` checks SQLite and whether the fleet is loaded; 503 while starting.
- Sign-in rate limit: 8 attempts / 10 minutes per client.
- `DEMO_TOOLS=0` disables seed/reset/empty.
- Unexpected errors return a human sentence. Validation errors are 400, not a raw schema dump.
- Request logs omit passphrases and tokens.
- SQLite indexes on `reviewed_fixes(shop_id)`, `members(shop_id, token)`, `shop_imports(shop_id)`.
- Tests for shop isolation, signature reuse, draft guards, shop intake, sign-in rate limit, and demo gate.
- CI typechecks and builds the web app.

## Security improvements

- Author on save still comes from the session (unchanged, preserved).
- Shop rows stay scoped by `SHOP_ID` (unchanged, preserved).
- Passphrase hint still off unless `SHOP_PASSPHRASE_HINT=1`.
- Sign-in brute-force window added.
- Demo destructive routes can be disabled.
- CORS methods/headers narrowed.
- Next.js sends `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`.
- Compose can pass `XAI_API_KEY` into the API only. The web image still has no key.
- `.env` remains gitignored. Root and API `.env.example` document variables without secrets.

## Architecture improvements

- Healthcheck on the API image; web waits until the fleet is ready.
- Honest dashboard strip: assets, remembered cases, NASA lead labeled as demo.
- No Postgres/Kafka/K8s rewrite. One process, one SQLite file, one shop id.

## UX improvements

- Sign-in and path gate state the loop and the NASA/shop split.
- Case blocks are named for the loop. Save is **Remember this case**.
- Mobile tabs: Detect / Investigate / Case.
- Footer is **Shop memory**.
- Investor brief leads with knowledge, not the model.

## Remaining technical debt

- Tokens in `localStorage` (XSS would steal a 12-hour session).
- Raw CSV kept in SQLite; disk grows with every import.
- Global in-memory fleet and rate-limit maps assume one API worker.
- No structured log sink (stdout only).
- API JSON still uses `engine` for the runtime asset record (NASA + shop). Product copy says asset.

## Known MVP limitations

- Shared shop passphrase, not SSO.
- One tenant per process.
- Scores rebuild on restart; memory does not.
- No live MQTT bus.
- Default passphrase is for this machine only.

## Production risks

- Shipping `SHOP_PASSPHRASE=sample-shop` or `SHOP_PASSPHRASE_HINT=1` on a public host.
- Publishing API port 8000 to the internet.
- Putting `XAI_API_KEY` in the Next.js build.
- Leaving `DEMO_TOOLS=1` on a pilot shop that should not wipe memory.
- Forgetting to schedule `scripts/backup-shop-memory.py` and copy `backups/` off-box.

## Recommended next 5 engineering priorities

1. Run a real host with `docs/PILOT.md` (your domain, your passphrase, `DEMO_TOOLS=0`).
2. Schedule `scripts/backup-shop-memory.py` nightly and copy `backups/` off-box.
3. Keep `npm run test:e2e` green on the NASA 31→74 path.
4. Folder-watch or MQTT that POSTs `/assets/append` for later hours.
5. Postgres only when a second live shop cannot share one SQLite file.
