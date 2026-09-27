import { NextRequest } from "next/server"
import { proxyBackend } from "@/lib/backend-proxy"

export const dynamic = "force-dynamic"
export const maxDuration = 60

interface RouteContext {
  params: Promise<{ path: string[] }>
}

async function handle(request: NextRequest, context: RouteContext) {
  const { path } = await context.params
  return proxyBackend(request, path)
}

export function GET(request: NextRequest, context: RouteContext) {
  return handle(request, context)
}

export function POST(request: NextRequest, context: RouteContext) {
  return handle(request, context)
}

export function PUT(request: NextRequest, context: RouteContext) {
  return handle(request, context)
}

export function DELETE(request: NextRequest, context: RouteContext) {
  return handle(request, context)
}
