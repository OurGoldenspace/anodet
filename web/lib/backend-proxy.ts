import { NextRequest, NextResponse } from "next/server"

export async function proxyBackend(request: NextRequest, path: string[]) {
  const base = (process.env.API_PROXY_URL || "http://127.0.0.1:8000").replace(/\/$/, "")
  let target: string
  try {
    const url = new URL(`${base}/${(path ?? []).join("/")}${request.nextUrl.search}`)
    if (!url.hostname)
      throw new Error("empty host")
    target = url.toString()
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
  } catch {
    return NextResponse.json(
      { detail: "The shop desk could not reach the scoring service. Reload and try again." },
      { status: 502 },
    )
  }
}
