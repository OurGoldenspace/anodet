import { lookup } from "node:dns/promises"
import { request as httpRequest } from "node:http"
import { request as httpsRequest } from "node:https"
import type { IncomingMessage, RequestOptions } from "node:http"
import { NextRequest, NextResponse } from "next/server"

export async function proxyBackend(request: NextRequest, path: string[]) {
  const base = (process.env.API_PROXY_URL || "http://127.0.0.1:8000").replace(/\/$/, "")
  let url: URL
  try {
    url = new URL(`${base}/${(path ?? []).join("/")}${request.nextUrl.search}`)
    if (!url.hostname)
      throw new Error("empty host")
  } catch {
    return NextResponse.json(
      { detail: "The shop desk is not pointed at the scoring service. Set API_PROXY_URL to http://HOST:8000 using the api service private domain." },
      { status: 502 },
    )
  }

  const headers: Record<string, string> = {}
  const authorization = request.headers.get("authorization")
  if (authorization)
    headers.authorization = authorization
  const contentType = request.headers.get("content-type")
  if (contentType)
    headers["content-type"] = contentType

  const body = request.method !== "GET" && request.method !== "HEAD"
    ? Buffer.from(await request.arrayBuffer())
    : undefined

  const attempts = await listAttempts(url)
  const failures: string[] = []

  for (const attempt of attempts) {
    try {
      const upstream = await requestUpstream({
        url,
        hostname: attempt.hostname,
        family: attempt.family,
        method: request.method,
        headers,
        body,
      })
      const chunks: Buffer[] = []
      for await (const chunk of upstream)
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
      const out = new Headers()
      const type = upstream.headers["content-type"]
      if (typeof type === "string")
        out.set("content-type", type)
      else if (Array.isArray(type) && type[0])
        out.set("content-type", type[0])
      return new NextResponse(Buffer.concat(chunks), {
        status: upstream.statusCode || 502,
        headers: out,
      })
    } catch (error) {
      failures.push(`${attempt.label}:${proxyError(error)}`)
    }
  }

  return NextResponse.json(
    { detail: `The shop desk could not reach the scoring service [http-ipv6 ${failures.join(" | ") || "unknown"}].` },
    { status: 502 },
  )
}

interface Attempt {
  hostname: string
  family?: 4 | 6
  label: string
}

async function listAttempts(url: URL) {
  const attempts: Attempt[] = []
  const seen = new Set<string>()

  function add(hostname: string, family: 4 | 6 | undefined, label: string) {
    const key = `${family || 0}:${hostname}`
    if (seen.has(key))
      return
    seen.add(key)
    attempts.push({ hostname, family, label })
  }

  if (url.hostname === "127.0.0.1" || url.hostname === "localhost") {
    add(url.hostname === "localhost" ? "127.0.0.1" : url.hostname, 4, "local")
    return attempts
  }

  try {
    const records = await lookup(url.hostname, { all: true, verbatim: true })
    for (const record of records.sort((left, right) => right.family - left.family))
      add(record.address, record.family === 6 ? 6 : 4, record.family === 6 ? "aaaa" : "a")
  } catch {
    // Hostname attempts below still run when private DNS lookup fails.
  }

  add(url.hostname, 6, "name6")
  add(url.hostname, undefined, "name")
  return attempts
}

function requestUpstream(input: {
  url: URL
  hostname: string
  family?: 4 | 6
  method: string
  headers: Record<string, string>
  body?: Buffer
}) {
  return new Promise<IncomingMessage>((resolve, reject) => {
    const isTls = input.url.protocol === "https:"
    const options: RequestOptions = {
      hostname: input.hostname,
      port: Number(input.url.port || (isTls ? 443 : 80)),
      path: `${input.url.pathname}${input.url.search}`,
      method: input.method,
      headers: {
        ...input.headers,
        host: input.url.host,
      },
      family: input.family,
    }
    const req = (isTls ? httpsRequest : httpRequest)(options, resolve)
    req.on("error", reject)
    req.setTimeout(15000, () => {
      req.destroy(new Error("timeout"))
    })
    if (input.body)
      req.write(input.body)
    req.end()
  })
}

function proxyError(error: unknown) {
  let current = error
  for (let index = 0; index < 5 && current; index += 1) {
    if (typeof current === "object" && current && "code" in current && current.code)
      return String(current.code)
    if (typeof current === "object" && current && "cause" in current)
      current = current.cause
    else
      break
  }
  return error instanceof Error ? error.message.slice(0, 80) : "unknown"
}
