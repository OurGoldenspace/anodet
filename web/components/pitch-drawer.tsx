"use client"

export function PitchDrawer({ open, onClose, medianLead, lateHit, healthyAlarm, notes }: PitchDrawerProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-20 bg-black/60" onClick={onClose} role="presentation">
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Investor brief"
        className="scroll-thin absolute right-0 top-0 h-dvh w-full max-w-lg overflow-y-auto border-l border-line bg-ink p-6 pb-16"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Anodet</p>
            <h2 className="mt-1 text-xl">Investor brief</h2>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-mist">
            Close
          </button>
        </div>

        <p className="mt-4 text-sm leading-6 text-foam">
          Your machines generate data. Your technicians generate knowledge. Anodet connects the two.
        </p>
        <p className="mt-3 text-sm leading-6 text-mist">
          The last cheap-check order dies with whoever was on the last job. The next asset with the same
          signature starts from the expensive manual again. Anodet stores the case so the shop can reuse it.
        </p>
        <p className="mt-3 font-mono text-xs uppercase tracking-[0.12em] text-amber">
          Detect → Investigate → Resolve → Remember → Reuse
        </p>

        <h3 className="mt-6 text-sm font-medium text-foam">Who pays first</h3>
        <p className="mt-2 text-sm leading-6 text-mist">
          A marine-diesel or millwright lead in Halifax, Saint John, or St. John’s who can say yes this month.
          Irving, shipyards, and utilities are a later contract. Instructors at NSCC and NBCC are design partners.
        </p>

        <h3 className="mt-6 text-sm font-medium text-foam">Why it is defendable</h3>
        <ul className="mt-2 space-y-2 text-sm leading-6 text-mist">
          <li>
            The moat is organization-specific history: reviewed cases, procedures, machine context, and outcomes. The
            OEM manual stays underneath, unchanged.
          </li>
          <li>
            Isolation Forest only finds the abnormal window. It learns the healthy hours the shop marked. The model
            is not the product.
          </li>
          <li>
            Grok-4 may draft a cheaper order. The server rejects any step that is not in the manual, names a sensor
            that did not move, or invents a part.
          </li>
          <li>NASA C-MAPSS FD001 is the labeled demo fleet. A shop file is the buyer path.</li>
        </ul>

        <h3 className="mt-6 text-sm font-medium text-foam">If they ask about live data</h3>
        <p className="mt-2 text-sm leading-6 text-mist">
          Old data teaches normal and stores the first fix. Live data only asks “did this happen again?” A live
          reading without a healthy window is a number, not evidence. Once the column map and the first reviewed
          fix exist, a stream only appends a row and rescoring.
        </p>

        <h3 className="mt-6 text-sm font-medium text-foam">The two-minute run</h3>
        <ol className="mt-2 space-y-3 text-sm leading-6 text-mist">
          {SCRIPT.map((step, index) => (
            <li key={step}>
              <span className="mr-2 font-mono text-amber">{index + 1}</span>
              {step}
            </li>
          ))}
        </ol>

        <h3 className="mt-6 text-sm font-medium text-foam">Evidence from testers</h3>
        {notes.length ? (
          <ul className="mt-2 space-y-1 text-sm leading-6">
            {notes.map((note) => (
              <li key={note.name}>
                {note.name}: {note.machine}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm leading-6 text-mist">
            After the second engine, the desk asks what machine they repair twice and stores that with their name.
            That list is the first investor artifact. None yet.
          </p>
        )}

        <details className="mt-6">
          <summary className="cursor-pointer text-sm font-medium text-foam">How the sample was built</summary>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-mist">
            <li>Median warning lead time: {medianLead} cycles before failure.</li>
            <li>Isolation Forest late-life outlier rate: {Math.round(lateHit * 1000) / 10}% on this NASA file only. Not field accuracy.</li>
            <li>Healthy-cycle false alarm rate: {Math.round(healthyAlarm * 1000) / 10}%.</li>
            <li>A per-engine standard deviation made every engine warn at cycle 31. The fleet healthy scale does not.</li>
            <li>The match is the same sensors, same direction. There is no similarity percentage.</li>
          </ul>
        </details>
      </aside>
    </div>
  )
}

const SCRIPT = [
  "Open Engine 31. No reviewed fix. The manual books a borescope first.",
  "Ask Grok for a cheaper order. The server checks it. Edit and save.",
  "Open Engine 74. Same signature in words. Shop memory leads. The manual is unchanged.",
  "Or bring data/demo/marine-diesel-sample.csv and paste a diesel procedure. Same three blocks.",
]

interface PitchDrawerProps {
  open: boolean
  onClose: () => void
  medianLead: number
  lateHit: number
  healthyAlarm: number
  notes: { name: string; machine: string }[]
}
