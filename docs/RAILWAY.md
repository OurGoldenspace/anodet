# Deploy on Railway

Railway gives you HTTPS on a `*.up.railway.app` URL. You do not need Caddy or a domain you own. Do not invent a hostname or passphrase.

Open your project: [Railway dashboard](https://railway.com/project/aa7f7b70-dc84-4f72-9b03-15262d6deed7?environmentId=a3d53800-56cc-4235-bd90-00ae4908790d).

Both images **must build from the repo root**. The API copies `data/cmapss/train_FD001.txt`. Do not set a service root directory to `web/` or `services/api/`.

## 1. Push this repo

Railway deploys from GitHub. This repo is already on `main`. Never commit `services/api/.env`.

On your machine, generate a local passphrase and open the dashboard:

```powershell
.\scripts\setup-railway.ps1
```

That writes gitignored files under `backups/` and opens the Railway project. Paste `backups/railway-api.env` and `backups/railway-web.env` into each service’s **Variables → Raw Editor**. Leave `CORS_ORIGINS` empty until the web URL exists.

Ready-to-copy templates without a secret: `deploy/railway-api.env.example` and `deploy/railway-web.env.example`.

## 2. Create two services from the same repo

In the project: **New** → **GitHub repo** → `anodet`. Rename that service to **`api`**.

**New** again → same repo. Rename the second service to **`web`**.

Private DNS is `http://api.railway.internal:8000` only if the API service is named `api`.

## 3. Service `api`

**Settings → Build**

- Builder: Dockerfile
- Dockerfile path: `services/api/Dockerfile`
- Root directory: empty (repo root)

**Settings → Networking**

- Target port: **8000**
- Generate a **private** domain
- Do **not** generate a public domain

**Settings → Volumes**

- Mount path: `/var/lib/anodet`  
  Without this, remembered cases disappear on every deploy.

**Variables**

| Variable | Set to |
|---|---|
| `PORT` | `8000` |
| `RAILWAY_DOCKERFILE_PATH` | `services/api/Dockerfile` |
| `ANODET_DB` | `/var/lib/anodet/anodet.db` |
| `ANODET_DATA` | `/data/cmapss/train_FD001.txt` |
| `SHOP_PASSPHRASE` | a long string you generate. Not `sample-shop`. |
| `SHOP_PASSPHRASE_HINT` | `0` |
| `DEMO_TOOLS` | `0` for a real shop. `1` if this URL is for judging. |
| `SHOP_ID` | e.g. `pilot` |
| `SHOP_NAME` | desk label |
| `SHOP_LEAD` | lead’s sign-in name, or empty (first sign-in is lead) |
| `CORS_ORIGINS` | `https://YOUR-WEB.up.railway.app` after step 4 |
| `XAI_API_KEY` | optional. Server only. |

Generate a passphrase on your machine (keep it off git and off chat):

```powershell
-join ((48..57 + 97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
```

First boot can take about 90 seconds while FD001 loads.

## 4. Service `web`

**Settings → Build**

- Builder: Dockerfile
- Dockerfile path: `web/Dockerfile`
- Root directory: empty (repo root)

**Settings → Networking**

- Target port: **3000**
- **Generate a domain** — that HTTPS URL is the desk you share

**Variables**

| Variable | Set to |
|---|---|
| `PORT` | `3000` |
| `RAILWAY_DOCKERFILE_PATH` | `web/Dockerfile` |
| `API_PROXY_URL` | `http://` + **api** service `RAILWAY_PRIVATE_DOMAIN` + `:8000`. Copy the hostname from api Variables. A broken `${{api.RAILWAY_PRIVATE_DOMAIN}}` becomes `http://:8000` and the desk 500s. |

`/backend` is proxied at **runtime**. You do not need a rebuild if you only change `API_PROXY_URL`.

Copy the public web URL. Set `CORS_ORIGINS=https://that-host` on **api**. Redeploy **api**.

## 5. Deploy order

1. Deploy **api**. Wait until it is healthy.
2. Deploy **web**.
3. Open **only** the web HTTPS URL. Sign in with your name and your passphrase.
4. NASA path: remember Engine 31, open Engine 74. Shop memory should lead.

## 6. Drag-and-drop alternative

You can drag `docker-compose.railway.yml` onto the Railway canvas to stage `api`, `web`, and the volume. Then still set `SHOP_PASSPHRASE` and `CORS_ORIGINS` in the UI. Do not run that compose file on your laptop — local Docker uses `docker-compose.yml`.

## 7. Optional CLI (Infrastructure as Code)

`.railway/railway.ts` describes the same two services. It does not deploy by itself.

The Railway CLI is installed globally as `@railway/cli` (`railway` in a new terminal).

```powershell
railway login
railway link
railway config plan
```

Run `railway config apply` only after you review the plan. Do not put the passphrase in that file (`preserve()` keeps whatever you already set in Railway).

## 8. After it is up

- Share the **web** URL only.
- Tell the lead the passphrase in person.
- Snapshot the `shop-memory` volume, or download it and run `scripts/backup-shop-memory.py`.
- Custom domain later: point DNS at Railway, then update `CORS_ORIGINS`.

## Failures

| Symptom | Fix |
|---|---|
| `/backend` 502 | API not healthy, or `API_PROXY_URL` / service name is not `api` |
| Service unavailable | Target port is not 8000 (api) or 3000 (web) |
| Cases vanish after deploy | Volume missing on `/var/lib/anodet` |
| Sign-in fails | Railway passphrase is not the local `sample-shop` |
| Anyone can wipe | `DEMO_TOOLS=1` on a public shop — set `0` |
