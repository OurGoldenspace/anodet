import { NextResponse } from "next/server"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export function GET() {
  let apiHost = ""
  try {
    apiHost = new URL(process.env.API_PROXY_URL || "http://127.0.0.1:8000").host
  } catch {
    apiHost = "invalid"
  }
  return NextResponse.json({
    desk: "ok",
    proxy: "http-ipv6",
    commit: process.env.RAILWAY_GIT_COMMIT_SHA || "local",
    apiHost,
  })
}
