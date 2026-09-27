"use client"

export function PathGate({ onSample, onShop }: PathGateProps) {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-amber">Anodet</p>
      <h1 className="mt-3 text-2xl">How do you want to start?</h1>
      <p className="mt-3 text-sm leading-6 text-mist">
        The sample fleet is NASA turbofan runs so you can finish a case without your machines. A shop file uses
        your hours and your procedure. Isolation Forest is fit only on the healthy window you mark.
      </p>
      <div className="mt-6 grid gap-3">
        <button type="button" onClick={onSample} className="rounded-md bg-amber px-3 py-3 text-left text-sm font-medium text-ink">
          Use the sample fleet
          <span className="mt-1 block font-normal text-ink/70">Engine 31, then the matching engine. Two minutes.</span>
        </button>
        <button type="button" onClick={onShop} className="rounded-md border border-line px-3 py-3 text-left text-sm">
          Bring a shop file
          <span className="mt-1 block text-mist">Your CSV, your healthy hours, your procedure.</span>
        </button>
      </div>
    </main>
  )
}

interface PathGateProps {
  onSample: () => void
  onShop: () => void
}
