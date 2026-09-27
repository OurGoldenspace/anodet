import type {
  CaseExplanation,
  DemoSeed,
  EngineDetail,
  FleetResponse,
  HistoryMapping,
  HistoryPreview,
  MaintenanceCase,
  ManualSection,
  ParsedManual,
  Outcome,
  ProcedureDraft,
  ReviewedFix,
  ShopInfo,
  ShopSession,
} from "@/lib/types"

const SESSION_KEY = "anodet-session"

export function readSession(): ShopSession | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(SESSION_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as ShopSession
    if (!parsed.token || !parsed.name) return null
    return parsed
  } catch {
    return null
  }
}

export function storeSession(session: ShopSession) {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearSession() {
  window.localStorage.removeItem(SESSION_KEY)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = readSession()
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    const detail = await response.text()
    let message = detail
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown }
      if (typeof parsed.detail === "string") message = parsed.detail
    } catch {
      message = detail
    }
    if (response.status === 401) clearSession()
    throw new Error(message || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function getNotes() {
  return request<{ notes: { name: string; machine: string }[] }>("/backend/notes")
}

export function getInterest() {
  return request<{ machine: string | null }>("/backend/interest")
}

export function saveInterest(machine: string) {
  return request<{ name: string; machine: string }>("/backend/interest", {
    method: "POST",
    body: JSON.stringify({ machine }),
  })
}

export function getShop() {
  return request<ShopInfo>("/backend/shop")
}

export function signIn(name: string, passphrase: string) {
  return request<ShopSession>("/backend/session", {
    method: "POST",
    body: JSON.stringify({ name, passphrase }),
  })
}

export function getFleet() {
  return request<FleetResponse>("/backend/engines")
}

export function getEngine(unitId: number) {
  return request<EngineDetail>(`/backend/engines/${unitId}`)
}

export function getCase(unitId: number, cycle: number) {
  return request<MaintenanceCase>(`/backend/cases/${unitId}?cycle=${cycle}`)
}

export function explainCase(record: MaintenanceCase) {
  return request<CaseExplanation>("/backend/cases/explain", {
    method: "POST",
    body: JSON.stringify({
      unitId: record.unitId,
      cycle: record.cycle,
      stage: record.stage,
      whatHappened: record.whatHappened,
      signature: record.signature.map((mark) => ({ name: mark.name, direction: mark.direction })),
      manualId: record.manual.id,
      manualTitle: record.manual.title,
      template: record.aiSummary,
      shop: record.shopMemory
        ? {
            unitId: record.shopMemory.unitId,
            sharedText: record.shopMemory.sharedText,
            author: record.shopMemory.author,
            resolved: record.shopMemory.resolved,
          }
        : null,
    }),
  })
}

export function draftProcedure(unitId: number, cycle: number) {
  return request<ProcedureDraft>("/backend/cases/draft", {
    method: "POST",
    body: JSON.stringify({ unitId, cycle }),
  })
}

export function emptyShop() {
  return request<{ status: string }>("/backend/demo/empty", { method: "POST" })
}

export function saveCase(input: {
  unitId: number
  cycle: number
  decision: "use_as_written" | "modify" | "different_cause"
  steps: string[]
  cause: string
  resolved: boolean
  note: string
  outcome: Outcome
}) {
  return request<MaintenanceCase>("/backend/cases", {
    method: "POST",
    body: JSON.stringify(input),
  })
}

export function updateManual(pattern: ManualSection["pattern"], steps: string[]) {
  return request<ManualSection>("/backend/manual", {
    method: "PUT",
    body: JSON.stringify({ pattern, steps }),
  })
}

export function previewHistory(csv: string) {
  return request<HistoryPreview>("/backend/assets/preview", {
    method: "POST",
    body: JSON.stringify({ csv }),
  })
}

export function importShopHistory(csv: string, mapping: HistoryMapping, healthyLimit: number, healthyFrom = 1) {
  return request<{ importedUnitIds: number[]; fleet: FleetResponse }>("/backend/assets/shop", {
    method: "POST",
    body: JSON.stringify({ csv, mapping, healthyLimit, healthyFrom }),
  })
}

export function removeImportedAsset(unitId: number) {
  return request<FleetResponse>(`/backend/engines/${unitId}`, { method: "DELETE" })
}

export function appendShopHours(csv: string, mapping: HistoryMapping, unitId: number | null) {
  return request<{ updatedUnitIds: number[]; fleet: FleetResponse }>("/backend/assets/append", {
    method: "POST",
    body: JSON.stringify({ csv, mapping, unitId }),
  })
}

export function parseManual(text: string) {
  return request<ParsedManual>("/backend/manual/parse", {
    method: "POST",
    body: JSON.stringify({ text }),
  })
}

export function saveShopManual(manual: ParsedManual) {
  return request<ManualSection>("/backend/manual/shop", {
    method: "POST",
    body: JSON.stringify({ title: manual.title, id: manual.id, steps: manual.steps }),
  })
}

export function importCycles(csv: string) {
  return request<{ importedUnitIds: number[]; fleet: FleetResponse }>("/backend/assets/import", {
    method: "POST",
    body: JSON.stringify({ csv }),
  })
}

export function getFixes() {
  return request<{ fixes: ReviewedFix[] }>("/backend/fixes")
}

export function seedDemo() {
  return request<DemoSeed>("/backend/demo/seed", { method: "POST" })
}

export function resetMemory() {
  return request<{ status: string }>("/backend/demo/reset", { method: "POST" })
}
