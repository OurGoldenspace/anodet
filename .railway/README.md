Railway Infrastructure as Code for Anodet. Dashboard steps: [docs/RAILWAY.md](../docs/RAILWAY.md).

```powershell
npm install railway
railway login
railway link
railway config plan
```

Apply only after you review the plan. Secrets stay in the Railway UI (`preserve()`). This file is not read during a GitHub deploy.
