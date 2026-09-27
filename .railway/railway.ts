import { defineRailway, github, group, preserve, project, service, volume } from "railway/iac"

export default defineRailway(() => {
  const memory = volume("shop-memory", { sizeMB: 1024 })

  const api = service("api", {
    source: github("OurGoldenspace/anodet"),
    healthcheck: "/health",
    healthcheckTimeout: 180,
    volumeMounts: {
      "/var/lib/anodet": memory,
    },
    env: {
      PORT: "8000",
      RAILWAY_DOCKERFILE_PATH: "services/api/Dockerfile",
      ANODET_DB: "/var/lib/anodet/anodet.db",
      ANODET_DATA: "/data/cmapss/train_FD001.txt",
      SHOP_PASSPHRASE_HINT: "0",
      DEMO_TOOLS: "0",
      SHOP_ID: "pilot",
      SHOP_NAME: "Pilot shop",
      SHOP_PASSPHRASE: preserve(),
      SHOP_LEAD: preserve(),
      CORS_ORIGINS: preserve(),
      XAI_API_KEY: preserve(),
      XAI_MODEL: "grok-4",
    },
  })

  const web = service("web", {
    source: github("OurGoldenspace/anodet"),
    env: {
      PORT: "3000",
      RAILWAY_DOCKERFILE_PATH: "web/Dockerfile",
      API_PROXY_URL: "http://api.railway.internal:8000",
    },
  })

  return project("anodet", {
    resources: [group("Anodet", [api, web, memory])],
  })
})
