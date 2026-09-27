"use client"

import { useEffect, useState, type ReactNode } from "react"
import { draftProcedure, explainCase, getCase, getInterest, saveCase, saveInterest, updateManual } from "@/lib/api"
import { formatUnit, OUTCOME_LABEL } from "@/lib/format"
import type { CaseExplanation, MaintenanceCase, Outcome, ProcedureDraft } from "@/lib/types"

export function CasePanel({ unitId, cycle, author, onOpenUnit, onSaved }: CasePanelProps) {
  const [record, setRecord] = useState<MaintenanceCase | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decision, setDecision] = useState<DecisionKind>("modify")
  const [stepsText, setStepsText] = useState("")
  const [cause, setCause] = useState("")
  const [resolved, setResolved] = useState(true)
  const [outcome, setOutcome] = useState<Outcome>("too_soon")
  const [note, setNote] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [savedLabel, setSavedLabel] = useState<string | null>(null)
  const [isEditingManual, setIsEditingManual] = useState(false)
  const [manualDraft, setManualDraft] = useState("")
  const [explanation, setExplanation] = useState<CaseExplanation | null>(null)
  const [draft, setDraft] = useState<ProcedureDraft | null>(null)
  const [isDrafting, setIsDrafting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setSavedLabel(null)
    setDraft(null)
    getCase(unitId, cycle)
      .then((next) => {
        if (cancelled) return
        setRecord(next)
        setError(null)
        setDecision("modify")
        setStepsText(next.suggestedSteps.join("\n"))
        setCause("")
        setResolved(true)
        setOutcome("too_soon")
        setIsEditingManual(false)
        setManualDraft(next.manual.steps.join("\n"))
      })
      .catch(() => {
        if (!cancelled) setError("Could not open this case.")
      })
    return () => {
      cancelled = true
    }
  }, [cycle, unitId])

  useEffect(() => {
    if (!record) return
    let cancelled = false
    setExplanation(null)
    const handle = window.setTimeout(() => {
      explainCase(record)
        .then((next) => {
          if (!cancelled) setExplanation(next)
        })
        .catch(() => {
          if (!cancelled) {
            setExplanation({
              summary: record.aiSummary,
              provider: "template",
              model: null,
              trace: "The model call did not return.",
            })
          }
        })
    }, 700)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [record])

  async function onSave() {
    if (!record) return
    if (!author.trim()) {
      setError("Add your name in the header before saving a fix.")
      return
    }
    setIsSaving(true)
    setError(null)
    try {
      const next = await saveCase({
        unitId: record.unitId,
        cycle: record.cycle,
        decision,
        steps: stepsText.split("\n"),
        cause,
        resolved,
        note,
        outcome,
      })
      setRecord(next)
      setSavedLabel("Reviewed fix saved.")
      onSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the fix.")
    } finally {
      setIsSaving(false)
    }
  }

  async function onDraft() {
    if (!record) return
    setIsDrafting(true)
    setError(null)
    try {
      const next = await draftProcedure(record.unitId, record.cycle)
      setDraft(next)
      setDecision("modify")
      setStepsText(next.steps.map((step) => step.text).join("\n"))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not draft a procedure.")
    } finally {
      setIsDrafting(false)
    }
  }

  async function onSaveManual() {
    if (!record) return
    setError(null)
    try {
      const manual = await updateManual(record.manual.pattern, manualDraft.split("\n"))
      setRecord({ ...record, manual })
      setIsEditingManual(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the manual.")
    }
  }

  if (error && !record) return <p className="p-4 text-sm text-flare">{error}</p>
  if (!record) return <p className="p-4 text-sm text-mist">Opening the case…</p>

  const shop = record.shopMemory
  const nextUnit = record.recallUnitId
  const canOpenNext = nextUnit != null && nextUnit !== record.unitId
  const hasReviewed = savedLabel != null || record.ownFix != null
  const isEmptyCase = !shop && !record.ownFix
  const stage: CaseStep = shop ? "reuse" : hasReviewed ? "reuse" : "decide"

  return (
    <aside className="scroll-thin flex h-full min-h-0 flex-col overflow-y-auto border-t border-line lg:border-l lg:border-t-0">
      <div className="border-b border-line px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Case</p>
        <h2 className="mt-1 text-lg font-medium">
          #{formatUnit(record.unitId)} · Engine {record.unitId}
        </h2>
        <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em] text-amber">
          Stage {record.stage} · {record.manual.pattern === "shop" ? "hour" : "cycle"} {record.cycle}
        </p>
        <CaseSteps current={stage} isReused={shop != null} />
      </div>

      <div className="space-y-4 px-4 py-4">
        <Block kicker="Machine evidence" tone="evidence">
          <p className="text-sm leading-6">{record.whatHappened}</p>
          <ul className="mt-2 space-y-1">
            {record.evidence.slice(0, 3).map((sensor) => (
              <li key={sensor.key} className="font-mono text-xs text-mist">
                {sensor.name} {sensor.zScore > 0 ? "+" : ""}
                {sensor.zScore.toFixed(1)}σ {sensor.direction}
              </li>
            ))}
          </ul>
        </Block>

        <Block kicker="Manual" tone="manual">
          <p className="font-mono text-xs text-amber">
            Section {record.manual.id} · {record.manual.title}
          </p>
          <p className="mt-1 text-[11px] text-mist">{record.manual.source}. A technician note does not change this.</p>
          {isEditingManual ? (
            <div className="mt-2 space-y-2">
              <textarea
                value={manualDraft}
                onChange={(event) => setManualDraft(event.target.value)}
                aria-label="Manual steps"
                rows={5}
                className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
              />
              <button type="button" onClick={() => void onSaveManual()} className="text-sm text-amber">
                Save manual section
              </button>
            </div>
          ) : (
            <>
              <StepList steps={record.manual.steps} />
              <button type="button" onClick={() => setIsEditingManual(true)} className="mt-2 text-xs text-mist">
                Edit this section
              </button>
            </>
          )}
        </Block>

        <Block kicker="Reviewed shop fix" tone="shop">
          {shop ? (
            <>
              <p className="text-sm leading-6">{shop.sharedText}</p>
              <p className="mt-2 text-xs text-mist">
                Engine {shop.unitId} · {shop.author || "Shop"} · {OUTCOME_LABEL[shop.outcome] ?? shop.outcome} · {shop.cause}
              </p>
              <StepList steps={shop.steps} />
              <InterestPrompt />
            </>
          ) : record.ownFix ? (
            <>
              <p className="text-sm leading-6">This case holds the reviewed fix. Other engines with the same signature will lead with it.</p>
              <p className="mt-2 text-xs text-mist">
                {record.ownFix.author || "Shop"} · {OUTCOME_LABEL[record.ownFix.outcome] ?? record.ownFix.outcome} · {record.ownFix.cause}
              </p>
              <StepList steps={record.ownFix.steps} />
            </>
          ) : (
            <p className="text-sm leading-6">No reviewed fix for this signature.</p>
          )}
        </Block>

        <Block kicker="AI summary" tone="ai">
          <p className="text-sm leading-6">{explanation?.summary ?? record.aiSummary}</p>
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist">
            {explanation
              ? `${explanation.provider === "xai" ? `Grok · ${explanation.model}` : "Template"} · ${explanation.trace}`
              : "Grok is reading this case"}
          </p>
        </Block>

        <section className="space-y-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-mist">Technician decision</p>
          {isEmptyCase ? (
            <p className="text-sm leading-6">
              No one has reviewed this signature. Ask Grok for a cheaper order, or edit the manual steps yourself.
            </p>
          ) : null}
          {!hasReviewed ? (
            <button
              type="button"
              disabled={isDrafting}
              onClick={() => void onDraft()}
              className="w-full rounded-md border border-amber/60 px-3 py-2 text-left text-sm leading-5 text-amber disabled:opacity-60"
            >
              {isDrafting
                ? "Grok is drafting a cheaper order. The server will reject any step that is not in the manual…"
                : draft
                  ? "Draft again"
                  : "Draft a reorder with Grok"}
            </button>
          ) : null}
          {draft ? <DraftCompare manual={record.manual.steps} manualId={record.manual.id} draft={draft} /> : null}
          {hasReviewed && canOpenNext ? (
            <button
              type="button"
              onClick={() => {
                if (nextUnit != null) onOpenUnit(nextUnit)
              }}
              className="w-full rounded-md bg-amber px-3 py-2 text-sm font-medium text-ink"
            >
              Open Engine {nextUnit}, same signature
            </button>
          ) : null}
          <div className="grid grid-cols-1 gap-2">
            <Choice label="Use manual as written" active={decision === "use_as_written"} onClick={() => setDecision("use_as_written")} />
            <Choice label="Modify procedure" active={decision === "modify"} onClick={() => setDecision("modify")} />
            <Choice label="Different cause" active={decision === "different_cause"} onClick={() => setDecision("different_cause")} />
          </div>
          {decision !== "use_as_written" ? (
            <textarea
              value={stepsText}
              onChange={(event) => setStepsText(event.target.value)}
              aria-label="Procedure steps"
              rows={5}
              className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
            />
          ) : null}
          <input
            value={cause}
            onChange={(event) => setCause(event.target.value)}
            aria-label="Actual cause"
            placeholder="What you found, e.g. hot-section wear confirmed by the cheap checks"
            className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
          />
          <p className="pt-1 text-xs text-mist">Did the cheaper order work?</p>
          <div className="grid grid-cols-1 gap-2">
            <Choice label="Too soon to know" active={outcome === "too_soon"} onClick={() => { setOutcome("too_soon"); setResolved(true) }} />
            <Choice label="Yes — cheaper order worked" active={outcome === "worked"} onClick={() => { setOutcome("worked"); setResolved(true) }} />
            <Choice label="No — still needed the expensive step" active={outcome === "did_not"} onClick={() => { setOutcome("did_not"); setResolved(false) }} />
          </div>
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            aria-label="Technician note"
            placeholder="Note for the next tech"
            className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
          />
          <button
            type="button"
            disabled={isSaving}
            onClick={() => void onSave()}
            className={`w-full rounded-md px-3 py-2 text-sm font-medium disabled:opacity-60 ${
              hasReviewed ? "border border-line text-mist" : "bg-tide text-ink"
            }`}
          >
            {isSaving ? "Saving…" : "Save reviewed fix"}
          </button>
          {savedLabel ? <p className="text-xs text-tide">{savedLabel}</p> : null}
          {error ? <p className="text-xs text-flare">{error}</p> : null}
        </section>
      </div>
    </aside>
  )
}

function InterestPrompt() {
  const [machine, setMachine] = useState("")
  const [saved, setSaved] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getInterest()
      .then((note) => {
        if (!cancelled && note.machine) setSaved(note.machine)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  async function onSubmit() {
    setError(null)
    try {
      const note = await saveInterest(machine)
      setSaved(note.machine)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save that.")
    }
  }

  if (saved) return <p className="mt-3 text-xs text-mist">You repair {saved} twice. That note is saved with your name.</p>

  return (
    <div className="mt-3 space-y-2">
      <p className="text-sm leading-6">What machine do you repair twice?</p>
      <input
        value={machine}
        onChange={(event) => setMachine(event.target.value)}
        aria-label="Machine you repair twice"
        placeholder="Pumps, diesels, turbines…"
        className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
      />
      <button type="button" onClick={() => void onSubmit()} className="text-sm text-amber">
        Save with my name
      </button>
      {error ? <p className="text-xs text-flare">{error}</p> : null}
    </div>
  )
}

function CaseSteps({ current, isReused }: { current: CaseStep; isReused: boolean }) {
  const order: CaseStep[] = ["evidence", "decide", "reuse"]
  const reached = order.indexOf(current)
  return (
    <ol className="mt-3 grid grid-cols-3 gap-1" aria-label="Case progress">
      {order.map((step, index) => {
        const isDone = index < reached || (step === "reuse" && isReused)
        const isCurrent = index === reached && !isDone
        return (
          <li
            key={step}
            aria-current={isCurrent ? "step" : undefined}
            className={`rounded px-2 py-1 text-center font-mono text-[10px] uppercase tracking-[0.14em] ${
              isDone ? "bg-tide/20 text-tide" : isCurrent ? "bg-amber/20 text-amber" : "bg-white/[0.03] text-mist"
            }`}
          >
            {index + 1} {STEP_LABEL[step]}
          </li>
        )
      })}
    </ol>
  )
}

function DraftCompare({ manual, manualId, draft }: { manual: string[]; manualId: string; draft: ProcedureDraft }) {
  const isModel = draft.provider === "xai"
  return (
    <div className="rounded-lg border border-amber/40 bg-ink/40 p-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist">Manual {manualId}</p>
          <ol className="mt-2 space-y-1 text-xs leading-5 text-mist">
            {manual.map((step, index) => (
              <li key={step}>
                <span className="mr-1 font-mono">{index + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </div>
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-amber">{isModel ? "Grok draft" : "Manual order kept"}</p>
          <ol className="mt-2 space-y-1 text-xs leading-5">
            {draft.steps.map((step, index) => (
              <li key={`${step.source}-${index}`} className={step.moved ? "rounded bg-amber/10 px-1" : "px-1"}>
                <span className="mr-1 font-mono text-amber">{index + 1}</span>
                {step.text}
                <span className="ml-1 font-mono text-[10px] text-mist">
                  {step.moved ? `moved from ${step.source}` : `step ${step.source}`}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
      {draft.reason ? <p className="mt-2 text-xs leading-5 text-foam">{draft.reason}</p> : null}
      <p className="mt-2 font-mono text-[10px] uppercase leading-4 tracking-[0.12em] text-mist">
        {isModel ? `Grok · ${draft.model} · ` : "Template · "}
        {draft.trace}
      </p>
      <p className="mt-1 text-[11px] text-mist">The draft is in the steps below. Nothing is shared until you save it.</p>
    </div>
  )
}

function Block({ kicker, tone, children }: { kicker: string; tone: "evidence" | "manual" | "shop" | "ai"; children: ReactNode }) {
  const toneClass = {
    evidence: "border-tide/40",
    manual: "border-amber/40",
    shop: "border-foam/30",
    ai: "border-line",
  }[tone]
  return (
    <section className={`rounded-lg border bg-ink/40 p-3 ${toneClass}`}>
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist">{kicker}</p>
      <div className="mt-2">{children}</div>
    </section>
  )
}

function StepList({ steps }: { steps: string[] }) {
  return (
    <ol className="mt-2 space-y-1 text-sm leading-5">
      {steps.map((step, index) => (
        <li key={step}>
          <span className="mr-2 font-mono text-xs text-mist">{index + 1}</span>
          {step}
        </li>
      ))}
    </ol>
  )
}

function Choice({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-2 text-left text-sm ${active ? "border-tide text-foam" : "border-line text-mist"}`}
    >
      {label}
    </button>
  )
}

type DecisionKind = "use_as_written" | "modify" | "different_cause"

type CaseStep = "evidence" | "decide" | "reuse"

const STEP_LABEL: Record<CaseStep, string> = {
  evidence: "Evidence",
  decide: "Decide",
  reuse: "Reuse",
}

interface CasePanelProps {
  unitId: number
  cycle: number
  author: string
  onOpenUnit: (unitId: number) => void
  onSaved: () => void
}
