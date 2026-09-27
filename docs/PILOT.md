# Pilot host

Two ways to put Anodet on the internet:

1. **Railway** (HTTPS on `*.up.railway.app`, no domain required): [RAILWAY.md](RAILWAY.md).
2. **Your own VM** (below). Do not invent a hostname. Use a domain you already own.

## HTTPS + real passphrase

On the server, export (not in git):

```
ANODET_HOST=your.domain
SHOP_PASSPHRASE=a-long-random-string
SHOP_PASSPHRASE_HINT=0
DEMO_TOOLS=0
SHOP_ID=halifax-diesel
SHOP_NAME=The shop name
SHOP_LEAD=The lead first name
CORS_ORIGINS=https://your.domain
XAI_API_KEY=
```

Then:

```powershell
docker compose -f docker-compose.yml -f docker-compose.pilot.yml up --build
```

Caddy in `deploy/Caddyfile` terminates TLS and proxies to the web app. Port 8000 stays unpublished.

Tell the lead the passphrase in person. Technicians sign in with their own name and that passphrase. They can remember cases and score later hours. They cannot Fit a new file or wipe memory.

## Nightly backup

From the repo root, after a case has been saved:

```powershell
.\scripts\backup-shop-memory.ps1
```

Or:

```powershell
python scripts\backup-shop-memory.py --dest backups --keep 14
```

On the VM, schedule that at 03:00 and copy `backups/` off-box.

Restore: stop the API, replace `ANODET_DB` (Docker: `/var/lib/anodet/anodet.db`) with last night’s file, start the API. Scores rebuild. Remembered cases stay.

## Local judging

Keep `DEMO_TOOLS=1` on this machine. Use the NASA path in [DEMO.md](DEMO.md).
