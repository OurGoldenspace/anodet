export const LOOP_STEPS = ["detect", "investigate", "resolve", "remember", "reuse"] as const

export type LoopStep = (typeof LOOP_STEPS)[number]

const LOOP_LABEL: Record<LoopStep, string> = {
  detect: "Detect",
  investigate: "Investigate",
  resolve: "Resolve",
  remember: "Remember",
  reuse: "Reuse",
}

export function ProductLoop({ current, compact = false }: ProductLoopProps) {
  const reached = LOOP_STEPS.indexOf(current)
  return (
    <ol
      className={`grid grid-cols-5 ${compact ? "gap-0.5" : "gap-1"}`}
      aria-label="Detect, investigate, resolve, remember, reuse"
    >
      {LOOP_STEPS.map((step, index) => {
        const isDone = index < reached
        const isCurrent = index === reached
        return (
          <li
            key={step}
            aria-current={isCurrent ? "step" : undefined}
            className={`rounded px-1 py-1 text-center font-mono uppercase ${
              compact ? "text-[9px] tracking-[0.08em]" : "text-[10px] tracking-[0.12em]"
            } ${
              isDone ? "bg-tide/20 text-tide" : isCurrent ? "bg-amber/20 text-amber" : "bg-white/[0.03] text-mist"
            }`}
          >
            {LOOP_LABEL[step]}
          </li>
        )
      })}
    </ol>
  )
}

interface ProductLoopProps {
  current: LoopStep
  compact?: boolean
}
