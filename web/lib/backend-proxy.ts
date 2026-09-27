import { lookup } from "node:dns/promises"
import { setDefaultResultOrder } from "node:dns"
import { NextRequest, NextResponse } from "next/server"

setDefaultResultOrder("ipv6first")

export async function proxyBackend(request: NextRequest, path: string[]) {
  const base = (process.env.API_PROXY_URL || "http://127.0.0.1:8000").replace(/\/$/, "")
  let target: string
  try {
    const url = new URL(`${base}/${(path ?? []).join("/")}${request.nextUrl.search}`)
    if (!url.hostname)
      throw new Error("empty host")
    target = await resolvePrivateTarget(url)
  } catch {
    return NextResponse.json(
      { detail: "The shop desk is not pointed at the scoring service. Set API_PROXY_URL to http://HOST:8000 using the api service private domain." },
      { status: 502 },
    )
  }

  const headers = new Headers()
  const authorization = request.headers.get("authorization")
  if (authorization) headers.set("authorization", authorization)
  const contentType = request.headers.get("content-type")
  if (contentType) headers.set("content-type", contentType)

  const init: RequestInit = { method: request.method, headers }
  if (request.method !== "GET" && request.method !== "HEAD")
    init.body = await request.arrayBuffer()

  try {
    const upstream = await fetch(target, { ...init, cache: "no-store" })
    const body = await upstream.arrayBuffer()
    const out = new Headers()
    const type = upstream.headers.get("content-type")
    if (type) out.set("content-type", type)
    return new NextResponse(body, { status: upstream.status, headers: out })
  } catch (error) {
    const code = error instanceof Error && "code" in error ? String((error as { code?: string }).code) : ""
    return NextResponse.json(
      {
        detail: code
          ? `The shop desk could not reach the scoring service (${code}).`
          : "The shop desk could not reach the scoring service. Reload and try again.",
      },
      { status: 502 },
    )
  }
}

async function resolvePrivateTarget(url: URL) {
  if (url.hostname === "127.0.0.1" || url.hostname === "localhost")
    return url.toString()
  try {
    const { address } = await lookup(url.hostname, { family: 6 })
    const port = url.port || "80"
    return `http://[${address}]:${port}${url.pathname}${url.search}`
  } catch {
    return url.toString()
  }
}
