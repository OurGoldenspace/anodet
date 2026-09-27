# Anodet

Reviewed maintenance cases for one shop. A case cites machine evidence, the shop manual, and a fix a technician saved on purpose. The next asset with the same sensor signature leads with that fix. The manual stays underneath, unchanged.

The sample fleet is NASA C-MAPSS FD001. A shop can also bring its own history file and procedure.

## Run on this machine

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

Open http://localhost:3000. Sign in with your name. On this machine the shop passphrase is `sample-shop` until you set `SHOP_PASSPHRASE`. The sign-in screen does not show that hint unless `SHOP_PASSPHRASE_HINT=1`. After sign-in, stay on the NASA sample or bring a shop file. On a phone the desk is Fleet, Engine, Case.

**Judging run:** Sample shop → Reset demo to empty. Open Engine 31. The manual books a borescope first. **Draft a reorder with Grok.** The server rejects invented steps. Save. Open Engine 74. Shop memory leads. The match is the same sensors, same direction.

**Shop file:** After sign-in, pick **Bring a shop file**. Use `data/shop/marine-diesel-sample.csv`. Paste a procedure. Mark the healthy window. Isolation Forest is fit only on those rows. Later hours append without a refit. A saved fix records whether the cheaper order worked. The NASA sample is on **Change start**.

**The venture** is the brief for NBIF, the J. Herbert Smith Centre, and operators: who pays first, why the check is the moat, and the machines testers said they repair twice.

A sign-in lasts 12 hours. Stored rows are scoped to `SHOP_ID` (default `sample`). A second shop is another id, not a rewrite. In Docker the API is only reachable from the web app. Set `SHOP_PASSPHRASE` and keep `SHOP_PASSPHRASE_HINT=0` before anyone outside this machine signs in.

**HTTPS:** Put Compose behind a reverse proxy that terminates TLS. Publish only the web port. Leave the API unpublished. Do not put the Grok key in the browser.

## Stack

- Next.js desk
- FastAPI
- scikit-learn Isolation Forest on the healthy window only
- Grok-4 for the case summary, a checked procedure draft, column mapping, and manual split
- SQLite for reviewed fixes, the shop manual, and tester notes

## Import

NASA files stay in FD001 column order. A shop CSV needs a unit column, a cycle or hour column, and at least two numeric channels. Each asset needs rows through the healthy window.
