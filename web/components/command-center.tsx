"use client"

import { useCallback, useEffect, useState } from "react"
import { clearSession, emptyShop, getEngine, getFixes, getFleet, getNotes, readSession, removeImportedAsset, resetMemory, seedDemo } from "@/lib/api"
import { formatUnit, OUTCOME_LABEL } from "@/lib/format"
import type { EngineDetail, FleetResponse, ReviewedFix, ShopSession } from "@/lib/types"
import { CasePanel } from "@/components/case-panel"
import { EngineStage } from "@/components/engine-stage"
import { FleetList } from "@/components/fleet-list"
import { PathGate } from "@/components/path-gate"
import { PitchDrawer } from "@/components/pitch-drawer"
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
  const [isPitchOpen, setIsPitchOpen] = useState(false)
  const [isShopOpen, setIsShopOpen] = useState(false)
  const [isInviteOpen, setIsInviteOpen] = useState(false)
  const [demoNote, setDemoNote] = useState<string | null>(null)
  const [session, setSession] = useState<ShopSession | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [notes, setNotes] = useState<{ name: string; machine: string }[]>([])
  const [deskPath, setDeskPath] = useState<string | null>(null)
  const [pathReady, setPathReady] = useState(false)
  const [deskTab, setDeskTab] = useState<DeskTab>("case")
  const [inviteCopied, setInviteCopied] = useState(false)

  useEffect(() => {
    setSession(readSession())
    setDeskPath(window.localStorage.getItem(PATH_KEY))
    setSessionReady(true)
    setPathReady(true)
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

  async function onSeed() {
    const seeded = await seedDemo()
    const nextFixes = await getFixes()
    setFixes(nextFixes.fixes)
    if (seeded.recallUnitId != null) {
      setSelectedId(seeded.recallUnitId)
      setDemoNote(`Engine ${seeded.reviewedUnitId} is reviewed. This engine shares the signature.`)
      return
    }
    setDemoNote("Reviewed fix saved. No second engine shared two sensors.")
  }

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
      setIsShopOpen(true)
      return
    }
    setSelectedId(31)
  }

  function onShopImported(next: FleetResponse, unitId: number | null) {
    setFleet(next)
    setDemoNote("Shop desk updated. Isolation Forest stays on the healthy hours you marked.")
    if (unitId != null) {
      setSelectedId(unitId)
      setDeskTab("case")
    }
    setIsShopOpen(false)
  }

  async function onRemoveAsset() {
    if (selectedId == null) return
    if (!window.confirm("Remove this imported asset? Sample engines stay. Fixes on this asset are deleted.")) return
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

  async function onCopyInvite() {
    const origin = window.location.origin
    const text = `Anodet — ${session?.shop ?? "Sample fleet"}\nOpen ${origin}\nSign in with your own name. Ask the lead for the shop passphrase.\nYour name is stored on every fix you save.`
    try {
      await navigator.clipboard.writeText(text)
      setInviteCopied(true)
    } catch {
      setDemoNote(text)
    }
  }

  async function refreshFixes() {
    const nextFixes = await getFixes()
    setFixes(nextFixes.fixes)
  }

  async function refreshNotes() {
    const next = await getNotes()
    setNotes(next.notes)
  }

  async function onReset() {
    await resetMemory()
    setFixes([])
    setDemoNote("Sample case cleared. Saved technician fixes stay.")
    setSelectedId(fleet?.recommendedUnitId ?? selectedId)
  }

  async function onEmpty() {
    if (!window.confirm("Remove every saved fix, including technicians' fixes? The manual and the machine notes stay.")) return
    await emptyShop()
    setFixes([])
    setDemoNote("Shop memory is empty. Engine 31 starts with no reviewed fix.")
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
        <p className="text-sm text-mist">Fitting the healthy-baseline model on NASA FD001…</p>
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

  const canUndoImport = !isSampleEngine
  const showJudgeTools = !isShopDesk

  return (
    <main className="flex h-dvh flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-line px-5 py-3">
        <div>
          <div className="flex items-baseline gap-3">
            <p className="font-mono text-lg tracking-[0.22em]">ANODET</p>
            <p className="hidden text-sm text-mist sm:block">Reviewed maintenance cases</p>
          </div>
          <p className="mt-1 hidden text-xs text-mist sm:block">
            {isShopDesk
              ? hasShopAssets
                ? `Your shop file · ${shopEngines.length} assets · NASA sample is on Change start`
                : "Your shop · drop a history file to start"
              : hasShopAssets
                ? `Shop assets on the sample fleet · ${fleet.stats.engines} engines`
                : `Sample fleet · NASA C-MAPSS FD001 · not your machines · ${fleet.stats.engines} engines`}
          </p>
        </div>
        <div className="flex items-center justify-end gap-2">
          <p className="max-w-[8rem] truncate text-sm text-mist sm:max-w-none">{session.name}</p>
          <details className="relative lg:hidden">
            <summary className="cursor-pointer list-none rounded-md border border-line px-3 py-2 text-sm">Menu</summary>
            <div className="absolute right-0 z-20 mt-2 flex w-64 flex-col gap-2 rounded-md border border-line bg-ink p-2">
              <button type="button" onClick={() => { setInviteCopied(false); setIsInviteOpen(true) }} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                Invite
              </button>
              <button type="button" onClick={() => setIsShopOpen(true)} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                Bring shop file
              </button>
              {showJudgeTools && isSampleEngine ? (
                <>
                  <button type="button" onClick={() => void onSeed()} className="rounded-md bg-amber px-3 py-2 text-left text-sm font-medium text-ink">
                    Load reviewed case
                  </button>
                  <button type="button" onClick={() => void onEmpty()} className="rounded-md border border-flare/50 px-3 py-2 text-left text-sm text-flare">
                    Reset demo to empty
                  </button>
                  <button type="button" onClick={() => { void refreshNotes(); setIsPitchOpen(true) }} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                    Investor brief
                  </button>
                </>
              ) : null}
              {canUndoImport ? (
                <button type="button" onClick={() => void onRemoveAsset()} className="rounded-md border border-line px-3 py-2 text-left text-sm text-mist">
                  Undo this import
                </button>
              ) : null}
              <button type="button" onClick={onChangeStart} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                Change start
              </button>
              <button type="button" onClick={onSignOut} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                Sign out
              </button>
            </div>
          </details>
          <div className="hidden flex-wrap items-center justify-end gap-2 lg:flex">
            <button
              type="button"
              onClick={() => {
                setInviteCopied(false)
                setIsInviteOpen(true)
              }}
              className="rounded-md border border-line px-3 py-2 text-sm"
            >
              Invite
            </button>
            <button type="button" onClick={() => setIsShopOpen(true)} className="rounded-md border border-line px-3 py-2 text-sm">
              Bring shop file
            </button>
            {showJudgeTools ? (
              <details className="relative" onToggle={(event) => { if (event.currentTarget.open) void refreshNotes() }}>
                <summary className="cursor-pointer list-none rounded-md border border-line px-3 py-2 text-sm">Sample shop</summary>
                <div className="absolute right-0 z-10 mt-2 flex w-72 flex-col gap-2 rounded-md border border-line bg-ink p-2">
                  <button type="button" onClick={() => void onSeed()} className="rounded-md bg-amber px-3 py-2 text-left text-sm font-medium text-ink">
                    Load reviewed case
                  </button>
                  <button type="button" onClick={() => void onReset()} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                    Clear sample memory
                  </button>
                  <button type="button" onClick={() => void onEmpty()} className="rounded-md border border-flare/50 px-3 py-2 text-left text-sm text-flare">
                    Reset demo to empty
                  </button>
                  <button type="button" onClick={() => { void refreshNotes(); setIsPitchOpen(true) }} className="rounded-md border border-line px-3 py-2 text-left text-sm">
                    Investor brief
                  </button>
                  {canUndoImport ? (
                    <button type="button" onClick={() => void onRemoveAsset()} className="rounded-md border border-line px-3 py-2 text-left text-sm text-mist">
                      Undo this import
                    </button>
                  ) : null}
                  <div className="border-t border-line px-1 pt-2">
                    <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-mist">Machines they repair twice</p>
                    {notes.length ? (
                      <ul className="mt-2 space-y-1">
                        {notes.map((note) => (
                          <li key={note.name} className="text-sm leading-5">
                            {note.name}: {note.machine}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-mist">No one has named a machine yet.</p>
                    )}
                  </div>
                </div>
              </details>
            ) : canUndoImport ? (
              <details className="relative">
                <summary className="cursor-pointer list-none rounded-md border border-line px-3 py-2 text-sm">More</summary>
                <div className="absolute right-0 z-10 mt-2 flex w-64 flex-col gap-2 rounded-md border border-line bg-ink p-2">
                  <button type="button" onClick={() => void onRemoveAsset()} className="rounded-md border border-line px-3 py-2 text-left text-sm text-mist">
                    Undo this import
                  </button>
                  <p className="px-1 text-xs leading-5 text-mist">Only if the file was the wrong asset. Saved fixes on it are deleted.</p>
                </div>
              </details>
            ) : null}
            <button type="button" onClick={onChangeStart} className="rounded-md border border-line px-3 py-2 text-sm">
              Change start
            </button>
            <button type="button" onClick={onSignOut} className="rounded-md border border-line px-3 py-2 text-sm">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <div className="grid shrink-0 grid-cols-3 border-b border-line lg:hidden">
        {(["fleet", "engine", "case"] as DeskTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setDeskTab(tab)}
            className={`px-2 py-2 text-xs uppercase tracking-[0.14em] ${deskTab === tab ? "text-amber" : "text-mist"}`}
          >
            {tab}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-hidden lg:grid lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <div className={`h-full min-h-0 overflow-hidden ${deskTab === "fleet" ? "block" : "hidden"} lg:block`}>
          <FleetList
            engines={visibleEngines}
            recommendedUnitId={fleet.recommendedUnitId}
            emptyLabel={isShopDesk ? "Bring a shop file. The NASA sample is on Change start." : undefined}
            selectedId={selectedId}
            query={query}
            onQueryChange={setQuery}
            onSelect={(unitId) => {
              setSelectedId(unitId)
              setDeskTab("case")
            }}
            expanded={deskTab === "fleet"}
          />
        </div>
        <div className={`h-full min-h-0 overflow-hidden ${deskTab === "engine" ? "block" : "hidden"} lg:block`}>
          {shopEmpty ? (
            <section className="scroll-thin flex h-full min-h-0 flex-col items-start justify-center gap-3 overflow-y-auto px-6 text-sm leading-6 text-mist">
              <p>This desk is your shop, not the NASA sample.</p>
              <button type="button" onClick={() => setIsShopOpen(true)} className="rounded-md bg-amber px-3 py-2 text-sm font-medium text-ink">
                Bring a shop file
              </button>
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
              Drop your hours and paste the procedure you use. Isolation Forest waits until you mark the healthy window.
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
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Reviewed fixes</p>
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
      {isInviteOpen ? (
        <div className="fixed inset-0 z-20 bg-black/60" onClick={() => setIsInviteOpen(false)} role="presentation">
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Invite a technician"
            className="scroll-thin absolute right-0 top-0 h-dvh w-full max-w-md overflow-y-auto border-l border-line bg-ink p-6 pb-16"
            onClick={(event) => event.stopPropagation()}
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Same shop</p>
            <h2 className="mt-1 text-xl">Invite a technician</h2>
            <p className="mt-4 text-sm leading-6 text-mist">
              They open this desk, enter their own name, and use the same shop passphrase. Fixes they save show their name. They see the fixes you already saved.
            </p>
            <pre className="mt-4 whitespace-pre-wrap rounded-md border border-line bg-panel p-3 text-xs leading-5 text-mist">
              {`Anodet — ${session.shop}\nOpen ${typeof window !== "undefined" ? window.location.origin : ""}\nSign in with your own name. Ask the lead for the shop passphrase.`}
            </pre>
            <button type="button" onClick={() => void onCopyInvite()} className="mt-4 rounded-md bg-amber px-3 py-2 text-sm font-medium text-ink">
              {inviteCopied ? "Copied" : "Copy invite"}
            </button>
            <button type="button" onClick={() => setIsInviteOpen(false)} className="mt-4 ml-3 text-sm text-mist">
              Close
            </button>
          </aside>
        </div>
      ) : null}
      <ShopIntake
        open={isShopOpen}
        onClose={() => setIsShopOpen(false)}
        onImported={onShopImported}
        selectedUnitId={isSampleEngine ? null : selectedId}
        hasShopAssets={hasShopAssets}
      />
      <PitchDrawer
        open={isPitchOpen}
        onClose={() => setIsPitchOpen(false)}
        medianLead={fleet.stats.medianLeadTime}
        lateHit={fleet.stats.lateLifeOutlierRate}
        healthyAlarm={fleet.stats.healthyOutlierRate}
        notes={notes}
      />
    </main>
  )
}

type DeskTab = "fleet" | "engine" | "case"
