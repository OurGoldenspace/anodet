"use client"

import { useState } from "react"
import { appendShopHours, importShopHistory, parseManual, previewHistory, saveShopManual } from "@/lib/api"
import type { FleetResponse, HistoryPreview, ParsedManual } from "@/lib/types"

const DIESEL_MANUAL = `S.1 Jacket-water and oil check — marine diesel

1. Confirm the engine is at the same load as the last healthy run.
2. Read oil temperature and exhaust temperature on wing before a tear-down.
3. Confirm oil pressure has dropped with both temperatures.
4. Open the case only if oil, exhaust, and pressure agree.`

export function ShopIntake({ open, onClose, onImported, selectedUnitId, hasShopAssets }: ShopIntakeProps) {
  const [fileName, setFileName] = useState<string | null>(null)
  const [raw, setRaw] = useState("")
  const [preview, setPreview] = useState<HistoryPreview | null>(null)
  const [healthyFrom, setHealthyFrom] = useState(1)
  const [healthyLimit, setHealthyLimit] = useState(20)
  const [busy, setBusy] = useState<string | null>(null)
  const [manualText, setManualText] = useState(DIESEL_MANUAL)
  const [parsed, setParsed] = useState<ParsedManual | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [appendOnly, setAppendOnly] = useState(false)

  if (!open) return null

  async function onFile(file: File | undefined) {
    if (!file) return
    const text = await file.text()
    setFileName(file.name)
    setRaw(text)
    setError(null)
    setBusy("Grok is reading the columns…")
    try {
      const next = await previewHistory(text)
      setPreview(next)
      const limit = Number(next.mapping.healthyLimit)
      if (limit) setHealthyLimit(limit)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not read that file.")
    } finally {
      setBusy(null)
    }
  }

  async function onParseManual() {
    setError(null)
    setBusy("Grok is splitting the procedure. The server will keep only text from the page…")
    try {
      setParsed(await parseManual(manualText))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not split that procedure.")
    } finally {
      setBusy(null)
    }
  }

  async function onImport() {
    if (!preview) return
    setError(null)
    setBusy(appendOnly ? "Scoring later hours. The healthy window is not refit…" : "Fitting Isolation Forest on the healthy hours only…")
    try {
      if (parsed) await saveShopManual(parsed)
      if (appendOnly) {
        const appended = await appendShopHours(raw, preview.mapping, selectedUnitId)
        setNote(`Later hours added to asset ${appended.updatedUnitIds.join(", ")}. Isolation Forest was not refit.`)
        onImported(appended.fleet, appended.updatedUnitIds[0] ?? selectedUnitId)
        return
      }
      const imported = await importShopHistory(raw, preview.mapping, healthyLimit, healthyFrom)
      const first = imported.importedUnitIds[0]
      setNote(`Imported asset ${imported.importedUnitIds.join(", ")}. The model was fit only on the healthy window.`)
      onImported(imported.fleet, first ?? null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not import that file.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fixed inset-0 z-20 bg-black/60" onClick={onClose} role="presentation">
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Bring a shop file"
        className="scroll-thin absolute right-0 top-0 h-dvh w-full max-w-lg overflow-y-auto border-l border-line bg-ink p-6 pb-16"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Shop intake</p>
            <h2 className="mt-1 text-xl">Bring a shop file</h2>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-mist">
            Close
          </button>
        </div>
        <p className="mt-3 text-sm leading-6 text-mist">
          Drop a history file and paste the procedure you actually use. Grok maps columns and splits the page.
          Isolation Forest is fit only on the healthy window you mark. Change start goes back to the NASA sample.
        </p>

        <label className="mt-5 block cursor-pointer rounded-md border border-line px-3 py-2 text-sm">
          {fileName ?? "Choose CSV or NASA text"}
          <input
            type="file"
            accept=".txt,.csv,text/plain"
            className="sr-only"
            onChange={(event) => {
              void onFile(event.target.files?.[0])
              event.target.value = ""
            }}
          />
        </label>
        <p className="mt-2 text-xs text-mist">
          Sample for the pitch: <span className="font-mono">data/shop/marine-diesel-sample.csv</span>
        </p>

        {preview ? (
          <div className="mt-4 rounded-lg border border-line p-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-amber">
              {preview.kind === "nasa" ? "NASA columns" : "Shop columns"} · {preview.provider === "xai" ? "Grok mapped" : "Name map"}
            </p>
            <p className="mt-2 text-xs leading-5 text-mist">{preview.trace}</p>
            {preview.kind === "shop" ? (
              <ul className="mt-2 space-y-1 text-sm">
                <li>Unit: {preview.mapping.unit}</li>
                <li>Cycle: {preview.mapping.cycle}</li>
                {preview.mapping.sensors.map((sensor) => (
                  <li key={sensor.column}>
                    {sensor.column} → {sensor.name}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm">This file uses the sample-fleet column order.</p>
            )}
            <p className="mt-3 text-sm">Hours that were normal (cycles if that is how the file is numbered)</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <label className="text-sm">
                From
                <input
                  type="number"
                  min={1}
                  max={2000}
                  value={healthyFrom}
                  onChange={(event) => setHealthyFrom(Number(event.target.value))}
                  className="mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
                />
              </label>
              <label className="text-sm">
                Through
                <input
                  type="number"
                  min={8}
                  max={2000}
                  value={healthyLimit}
                  onChange={(event) => setHealthyLimit(Number(event.target.value))}
                  className="mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
                />
              </label>
            </div>
            <p className="mt-2 text-xs text-mist">
              Later rows are scored, never used to train. Live readings later use this same window.
            </p>
            {hasShopAssets ? (
              <label className="mt-3 flex items-start gap-2 text-sm">
                <input type="checkbox" checked={appendOnly} onChange={(event) => setAppendOnly(event.target.checked)} className="mt-1" />
                These are later hours. Do not retrain. Score them against the healthy window already marked.
              </label>
            ) : null}
          </div>
        ) : null}

        <label className="mt-5 block text-sm">
          Paste the shop procedure
          <textarea
            value={manualText}
            onChange={(event) => setManualText(event.target.value)}
            rows={7}
            className="mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
          />
        </label>
        <button type="button" disabled={busy != null} onClick={() => void onParseManual()} className="mt-2 text-sm text-amber">
          Split with Grok
        </button>
        {parsed ? (
          <ol className="mt-3 space-y-1 text-sm leading-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist">
              {parsed.id} · {parsed.title} · {parsed.provider === "xai" ? "Grok" : "Lines"}
            </p>
            {parsed.steps.map((step, index) => (
              <li key={step}>
                <span className="mr-2 font-mono text-xs text-mist">{index + 1}</span>
                {step}
              </li>
            ))}
            <p className="text-xs text-mist">{parsed.trace}</p>
          </ol>
        ) : null}

        <button
          type="button"
          disabled={busy != null || !preview}
          onClick={() => void onImport()}
          className="mt-5 w-full rounded-md bg-amber px-3 py-2 text-sm font-medium text-ink disabled:opacity-60"
        >
          {appendOnly ? "Score later hours and open the case" : "Fit on the healthy hours and open the case"}
        </button>
        {busy ? <p className="mt-3 text-sm text-amber">{busy}</p> : null}
        {note ? <p className="mt-3 text-sm text-tide">{note}</p> : null}
        {error ? <p className="mt-3 text-sm text-flare">{error}</p> : null}
      </aside>
    </div>
  )
}

interface ShopIntakeProps {
  open: boolean
  onClose: () => void
  onImported: (fleet: FleetResponse, unitId: number | null) => void
  selectedUnitId: number | null
  hasShopAssets: boolean
}
