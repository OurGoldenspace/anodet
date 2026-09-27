"use client"

import { useCallback, useEffect, useState } from "react"
import { clearSession, emptyShop, getEngine, getFixes, getFleet, getShop, readSession, removeImportedAsset } from "@/lib/api"
import { formatUnit, OUTCOME_LABEL } from "@/lib/format"
import type { EngineDetail, FleetResponse, ReviewedFix, ShopSession } from "@/lib/types"
import { CasePanel } from "@/components/case-panel"
import { EngineStage } from "@/components/engine-stage"
import { FleetList } from "@/components/fleet-list"
import { PathGate } from "@/components/path-gate"
import { ShopIntake } from "@/components/shop-intake"
import { SignIn } from "@/components/sign-in"

const PATH_KEY = "anodet-desk-path"

export function CommandCenter() {
  const [fleet, setFleet] = useState<FleetResponse | null>(null)
  const [fleetError, setFleetError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [query, setQuery] = useState("")
  const [detail, setDetail] = useState<EngineDetail | null>(null)
  const [cycle, setCycle] = useState<number | null>(null)
  const [fixes, setFixes] = useState<ReviewedFix[]>([])
  const [isShopOpen, setIsShopOpen] = useState(false)
  const [demoNote, setDemoNote] = useState<string | null>(null)
  const [session, setSession] = useState<ShopSession | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [deskPath, setDeskPath] = useState<string | null>(null)
  const [pathReady, setPathReady] = useState(false)
  const [deskTab, setDeskTab] = useState<DeskTab>("case")
  const [demoTools, setDemoTools] = useState(true)
  const [appendMode, setAppendMode] = useState(false)

  useEffect(() => {
    setSession(readSession())
    setDeskPath(window.localStorage.getItem(PATH_KEY))
    setSessionReady(true)
    setPathReady(true)
    getShop()
      .then((shop) => setDemoTools(shop.demoTools !== false))
      .catch(() => undefined)
  }, [])

  const onCycleChange = useCallback((next: number) => {
    setCycle(next)
  }, [])

  useEffect(() => {
    let cancelled = false
    if (!session) return
    getFleet()
      .then((next) => {
        if (cancelled) return
        setFleet(next)
        const shopFirst = next.engines.find((engine) => engine.origin === "import")
        const path = window.localStorage.getItem(PATH_KEY)
        if (path === "shop") setSelectedId(shopFirst?.unitId ?? null)
        else setSelectedId(next.recommendedUnitId)
      })
      .catch((caught: unknown) => {
        if (cancelled) return
        if (caught instanceof Error && caught.message.includes("Sign in")) {
          setSession(null)
          return
        }
        setFleetError("The diagnostic API is not running on port 8000.")
      })
    getFixes()
      .then((next) => {
        if (!cancelled) setFixes(next.fixes)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [session])

  useEffect(() => {
    if (selectedId == null) return
    let cancelled = false
    getEngine(selectedId)
      .then((next) => {
        if (cancelled) return
        setDetail(next)
        setCycle(next.warningCycle)
      })
      .catch(() => {
        if (!cancelled) setFleetError("Could not load that engine.")
      })
    return () => {
      cancelled = true
    }
  }, [selectedId])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return
      if (!detail || cycle == null) return
      if (event.key === "ArrowRight") onCycleChange(Math.min(detail.lifeCycles, cycle + 1))
      if (event.key === "ArrowLeft") onCycleChange(Math.max(detail.series[0]?.cycle ?? 1, cycle - 1))
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [cycle, detail, onCycleChange])

  function onSignOut() {
    clearSession()
    setSession(null)
    setFleet(null)
    setFixes([])
  }

  function onChangeStart() {
    window.localStorage.removeItem(PATH_KEY)
    setDeskPath(null)
    setIsShopOpen(false)
  }

  function choosePath(path: "sample" | "shop") {
    window.localStorage.setItem(PATH_KEY, path)
    setDeskPath(path)
    if (path === "shop") {
      const shopFirst = fleet?.engines.find((engine) => engine.origin === "import")
      setSelectedId(shopFirst?.unitId ?? null)
      if (session?.role !== "technician") {
        setAppendMode(false)
        setIsShopOpen(true)
      }
      return
    }
    setSelectedId(31)
  }

  function onShopImported(next: FleetResponse, unitId: number | null) {
    setFleet(next)
    setDemoNote("Shop file loaded.")
    if (unitId != null) {
      setSelectedId(unitId)
      setDeskTab("case")
    }
    setIsShopOpen(false)
  }

  async function onRemoveAsset() {
    if (selectedId == null) return
    if (!window.confirm("Remove this imported asset? Saved fixes on it are deleted.")) return
    try {
      const next = await removeImportedAsset(selectedId)
      setFleet(next)
      setSelectedId(next.recommendedUnitId)
      setDemoNote("Imported asset removed.")
      setDeskTab("fleet")
    } catch (caught) {
      setDemoNote(caught instanceof Error ? caught.message : "Could not remove that asset.")
    }
  }

  async function refreshFixes() {
    const nextFixes = await getFixes()
    setFixes(nextFixes.fixes)
  }

  async function onEmpty() {
    if (!window.confirm("Clear all saved fixes and start Engine 31 over?")) return
    await emptyShop()
    setFixes([])
    setDemoNote("Shop memory is empty. Engine 31 starts with nothing remembered.")
    const start = fleet?.recommendedUnitId ?? selectedId
    setSelectedId(null)
    window.setTimeout(() => setSelectedId(start), 0)
  }

  if (!sessionReady || !pathReady) return null
  if (!session) return <SignIn onSignedIn={setSession} />
  if (deskPath == null) return <PathGate onSample={() => choosePath("sample")} onShop={() => choosePath("shop")} />

  if (fleetError) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-amber">Anodet</p>
        <h1 className="mt-3 text-2xl">Start the diagnostic API</h1>
        <p className="mt-3 text-sm leading-6 text-mist">{fleetError}</p>
        <pre className="mt-4 overflow-x-auto rounded-lg border border-line bg-panel p-4 text-xs text-mist">
          {`cd services\\api\n.\\.venv\\Scripts\\python -m uvicorn app.main:app --port 8000`}
        </pre>
      </main>
    )
  }

  if (!fleet) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <p className="text-sm text-mist">Loading the shop…</p>
      </main>
    )
  }

  const shopEngines = fleet.engines.filter((engine) => engine.origin === "import")
  const hasShopAssets = shopEngines.length > 0
  const isShopDesk = deskPath === "shop"
  const visibleEngines = isShopDesk ? shopEngines : fleet.engines
  const selectedEngine = fleet.engines.find((engine) => engine.unitId === selectedId)
  const isSampleEngine = selectedEngine?.origin !== "import"
  const shopEmpty = isShopDesk && !hasShopAssets
  const stageReady = !shopEmpty && detail != null && detail.unitId === selectedId && cycle != null

  const isLead = session.role !== "technician"
  const canUndoImport = isLead && !isSampleEngine
  const showStartOver = isLead && demoTools && !isShopDesk
  const more = {
    isLead,
    hasShopAssets,
    canUndoImport,
    onBringFile: () => {
      setAppendMode(false)
      setIsShopOpen(true)
    },
    onLaterHours: () => {
      setAppendMode(true)
      setIsShopOpen(true)
    },
    onRemoveAsset: () => void onRemoveAsset(),
    onChangeStart,
    onSignOut,
  }

  return (
    <main className="flex h-dvh flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-line px-5 py-3">
        <p className="font-mono text-lg tracking-[0.22em]">ANODET</p>
        <div className="flex items-center justify-end gap-2">
          <p className="max-w-[8rem] truncate text-sm text-mist sm:max-w-none">{session.name}</p>
          {showStartOver ? (
            <button
              type="button"
              data-testid="start-over"
              onClick={() => void onEmpty()}
              className="rounded-md border border-line px-3 py-2 text-sm"
            >
              Start over
            </button>
          ) : null}
          <details className="relative">
            <summary className="cursor-pointer list-none rounded-md border border-line px-3 py-2 text-sm">More</summary>
            <div className="absolute right-0 z-20 mt-2 flex w-56 flex-col gap-2 rounded-md border border-line bg-ink p-2">
              <MoreActions {...more} />
            </div>
          </details>
        </div>
      </header>
      <div className="hidden shrink-0 items-center gap-6 border-b border-line px-5 py-2 text-xs text-mist lg:flex">
        <p>
          <span className="font-mono uppercase tracking-[0.12em] text-foam">Assets </span>
          {visibleEngines.length}
        </p>
        <p>
          <span className="font-mono uppercase tracking-[0.12em] text-foam">Remembered </span>
          {fixes.length}
        </p>
      </div>

      <div className="grid shrink-0 grid-cols-3 border-b border-line lg:hidden">
        {([
          ["fleet", "Detect"],
          ["engine", "Investigate"],
          ["case", "Case"],
        ] as [DeskTab, string][]).map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            onClick={() => setDeskTab(tab)}
            className={`px-2 py-2 text-xs uppercase tracking-[0.14em] ${deskTab === tab ? "text-amber" : "text-mist"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-hidden lg:grid lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <div className={`h-full min-h-0 overflow-hidden ${deskTab === "fleet" ? "block" : "hidden"} lg:block`}>
          <FleetList
            engines={visibleEngines}
            recommendedUnitId={fleet.recommendedUnitId}
            emptyLabel={isShopDesk ? "Bring a shop file from More." : undefined}
            selectedId={selectedId}
            query={query}
            onQueryChange={setQuery}
            onSelect={(unitId) => {
              setSelectedId(unitId)
              setDeskTab("case")
            }}
          />
        </div>
        <div className={`h-full min-h-0 overflow-hidden ${deskTab === "engine" ? "block" : "hidden"} lg:block`}>
          {shopEmpty ? (
            <section className="scroll-thin flex h-full min-h-0 flex-col items-start justify-center gap-3 overflow-y-auto px-6 text-sm leading-6 text-mist">
              <p>Drop a shop file to start.</p>
              {isLead ? (
                <button type="button" onClick={more.onBringFile} className="rounded-md bg-amber px-3 py-2 text-sm font-medium text-ink">
                  Bring a shop file
                </button>
              ) : (
                <p>Ask the shop lead to load the first file.</p>
              )}
            </section>
          ) : stageReady ? (
            <EngineStage engine={detail} cycle={cycle} onCycleChange={onCycleChange} />
          ) : (
            <section className="flex h-full items-center justify-center text-sm text-mist">Loading engine…</section>
          )}
        </div>
        <div className={`h-full min-h-0 overflow-hidden ${deskTab === "case" ? "block" : "hidden"} lg:block`}>
          {shopEmpty ? (
            <aside className="scroll-thin h-full overflow-y-auto p-4 text-sm leading-6 text-mist">
              Drop your hours and paste the procedure you use.
            </aside>
          ) : stageReady ? (
            <CasePanel
              unitId={detail.unitId}
              cycle={cycle}
              author={session.name}
              onOpenUnit={(unitId) => {
                setSelectedId(unitId)
                setDeskTab("case")
              }}
              onSaved={() => void refreshFixes()}
            />
          ) : (
            <aside className="p-4 text-sm text-mist">Opening the case…</aside>
          )}
        </div>
      </div>
      <footer className="shrink-0 border-t border-line bg-panel/90 px-4 py-3">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Shop memory</p>
          <p className="text-xs text-mist">{demoNote ?? (fixes.length ? `${fixes.length} saved` : "None yet")}</p>
        </div>
        {fixes.length > 0 ? (
          <ul className="mt-2 flex gap-2 overflow-x-auto">
            {fixes.map((fix) => (
              <li key={fix.id} className="min-w-[220px] rounded-md border border-line bg-ink px-3 py-2">
                <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-mist">
                  ENG {formatUnit(fix.unitId)} · {fix.author || "Shop"} · {OUTCOME_LABEL[fix.outcome] ?? (fix.resolved ? "Resolved" : "Open")}
                </p>
                <p className="mt-1 text-sm">{fix.cause}</p>
              </li>
            ))}
          </ul>
        ) : null}
      </footer>
      <ShopIntake
        open={isShopOpen}
        onClose={() => setIsShopOpen(false)}
        onImported={onShopImported}
        selectedUnitId={isSampleEngine ? null : selectedId}
        hasShopAssets={hasShopAssets}
        appendMode={appendMode}
        canFit={isLead}
      />
    </main>
  )
}

function MoreActions({
  isLead,
  hasShopAssets,
  canUndoImport,
  onBringFile,
  onLaterHours,
  onRemoveAsset,
  onChangeStart,
  onSignOut,
}: MoreActionsProps) {
  return (
    <>
      {isLead ? (
        <button type="button" onClick={onBringFile} className="rounded-md border border-line px-3 py-2 text-left text-sm">
          Bring shop file
        </button>
      ) : null}
      {hasShopAssets ? (
        <button type="button" onClick={onLaterHours} className="rounded-md border border-line px-3 py-2 text-left text-sm">
          Later hours
        </button>
      ) : null}
      {canUndoImport ? (
        <button type="button" onClick={onRemoveAsset} className="rounded-md border border-line px-3 py-2 text-left text-sm text-mist">
          Undo this import
        </button>
      ) : null}
      <button type="button" onClick={onChangeStart} className="rounded-md border border-line px-3 py-2 text-left text-sm">
        Change start
      </button>
      <button type="button" onClick={onSignOut} className="rounded-md border border-line px-3 py-2 text-left text-sm">
        Sign out
      </button>
    </>
  )
}

interface MoreActionsProps {
  isLead: boolean
  hasShopAssets: boolean
  canUndoImport: boolean
  onBringFile: () => void
  onLaterHours: () => void
  onRemoveAsset: () => void
  onChangeStart: () => void
  onSignOut: () => void
}

type DeskTab = "fleet" | "engine" | "case"
