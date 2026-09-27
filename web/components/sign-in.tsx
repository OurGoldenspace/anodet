"use client"

import { useEffect, useState, type FormEvent } from "react"
import { getShop, signIn, storeSession } from "@/lib/api"
import type { ShopSession } from "@/lib/types"

export function SignIn({ onSignedIn }: SignInProps) {
  const [name, setName] = useState("")
  const [passphrase, setPassphrase] = useState("")
  const [hint, setHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    getShop()
      .then((shop) => setHint(shop.passphraseHint))
      .catch(() => setError("The shop is not reachable."))
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)
    try {
      const session = await signIn(name, passphrase)
      storeSession(session)
      onSignedIn(session)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not sign in.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-amber">Anodet</p>
      <h1 className="mt-3 text-2xl">Sign in to the shop</h1>
      <p className="mt-3 text-sm leading-6 text-foam">
        Your machines generate data. Your technicians generate knowledge. Anodet connects the two.
      </p>
      <p className="mt-2 text-sm leading-6 text-mist">
        Detect an abnormal window, investigate with the procedure, resolve it, remember the outcome, reuse it on the
        next matching asset. After sign-in, use the NASA demo fleet or your own shop file.
      </p>
      <form onSubmit={(event) => void onSubmit(event)} className="mt-6 space-y-3">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-label="Your name"
          data-testid="sign-in-name"
          placeholder="Your name"
          className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
        />
        <input
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
          aria-label="Shop passphrase"
          data-testid="sign-in-passphrase"
          placeholder="Shop passphrase"
          type="password"
          className="w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-amber"
        />
        {hint ? <p className="text-xs text-mist">Sample shop passphrase: {hint}</p> : null}
        {error ? <p className="text-sm text-flare">{error}</p> : null}
        <button
          type="submit"
          data-testid="sign-in-submit"
          disabled={isSubmitting}
          className="w-full rounded-md bg-amber px-3 py-2 text-sm font-medium text-ink disabled:opacity-60"
        >
          {isSubmitting ? "Signing in…" : "Enter the shop"}
        </button>
      </form>
    </main>
  )
}

interface SignInProps {
  onSignedIn: (session: ShopSession) => void
}
