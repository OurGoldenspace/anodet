import path from "node:path"
import { defineConfig, devices } from "@playwright/test"

const webDir = process.cwd()
const apiDir = path.join(webDir, "..", "services", "api")
const venvPython = path.join(apiDir, ".venv", process.platform === "win32" ? "Scripts\\python.exe" : "bin/python")
const python = process.env.CI ? "python" : venvPython
const dbFile = path.join(process.env.RUNNER_TEMP || webDir, "anodet-e2e.db")

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8001`,
      cwd: apiDir,
      url: "http://127.0.0.1:8001/health",
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        ANODET_DB: dbFile,
        DEMO_TOOLS: "1",
        SHOP_PASSPHRASE: process.env.SHOP_PASSPHRASE || "sample-shop",
        SHOP_PASSPHRASE_HINT: "0",
        SHOP_ID: "e2e",
      },
    },
    {
      command: "npx next dev --port 3001",
      cwd: webDir,
      url: "http://127.0.0.1:3001",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        API_PROXY_URL: "http://127.0.0.1:8001",
      },
    },
  ],
})
