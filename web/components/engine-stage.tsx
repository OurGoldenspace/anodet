"use client"

import { useEffect, useState } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { formatUnit, PATTERN_LABEL } from "@/lib/format"
import type { EngineDetail, SeriesPoint } from "@/lib/types"

export function EngineStage({ engine, cycle, onCycleChange }: EngineStageProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const point = engine.series.find((item) => item.cycle === cycle) ?? engine.series[0]
  const tick = engine.pattern === "shop" || engine.origin === "import" ? "hour" : "cycle"

  useEffect(() => {
    setIsPlaying(false)
  }, [engine.unitId])

  useEffect(() => {
    if (!isPlaying) return
    if (cycle >= engine.lifeCycles) {
      setIsPlaying(false)
      return
    }
    const timer = window.setTimeout(() => onCycleChange(cycle + 1), 160)
    return () => window.clearTimeout(timer)
  }, [cycle, engine.lifeCycles, isPlaying, onCycleChange])

  function jump(next: number) {
    setIsPlaying(false)
    onCycleChange(next)
  }

  return (
    <section className="scroll-thin h-full min-h-0 overflow-y-auto px-5 py-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Investigate · engine</p>
          <h2 className="mt-1 text-2xl font-medium">ENG {formatUnit(engine.unitId)}</h2>
          <p className="mt-1 text-sm text-mist">
            {PATTERN_LABEL[engine.pattern]} · warning at {tick} {engine.warningCycle} · {engine.leadTime} {tick}s of lead
            time
          </p>
          {engine.trainedOn ? <p className="mt-1 text-xs text-mist">Baseline: {engine.trainedOn}</p> : null}
          <p className="mt-1 text-xs text-mist">
            {engine.origin === "import"
              ? "Shop file · your hours"
              : "NASA C-MAPSS FD001 demo fleet · not a customer"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <JumpButton label="Warning" onClick={() => jump(engine.warningCycle)} />
          {engine.criticalCycle != null ? (
            <JumpButton label="Critical" onClick={() => jump(engine.criticalCycle ?? engine.warningCycle)} />
          ) : null}
          <JumpButton label="Failure" onClick={() => jump(engine.lifeCycles)} />
          <button
            type="button"
            onClick={() => setIsPlaying((current) => !current)}
            className="rounded-md bg-amber px-3 py-1.5 text-sm font-medium text-ink"
          >
            {isPlaying ? "Pause" : "Play"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
        <Stat label={tick === "hour" ? "Hour" : "Cycle"} value={`${point.cycle} / ${engine.lifeCycles}`} />
        <Stat label="Health" value={point.health.toFixed(0)} tone={point.health < 50 ? "alert" : "ok"} />
        <Stat label={tick === "hour" ? "Hours left" : "Cycles left"} value={String(point.rul)} />
        <Stat label="Warning health" value={String(Math.round(engine.healthAtWarning))} />
      </div>

      <div className="mt-4 rounded-lg border border-line bg-panel/80 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-mist">Health index</p>
          <p className="text-xs text-mist">{PATTERN_LABEL[engine.pattern]}</p>
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={engine.series} onClick={(state) => handleChartClick(state, jump)}>
              <CartesianGrid stroke="#1c2940" vertical={false} />
              <XAxis dataKey="cycle" tick={{ fill: "#93a4bd", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: "#93a4bd", fontSize: 11 }} axisLine={false} tickLine={false} width={32} />
              <Tooltip content={<HealthTooltip />} />
              <ReferenceLine x={engine.warningCycle} stroke="#7aa2ff" strokeDasharray="4 4" />
              {engine.criticalCycle != null ? (
                <ReferenceLine x={engine.criticalCycle} stroke="#ff6b7d" strokeDasharray="4 4" />
              ) : null}
              <ReferenceLine x={point.cycle} stroke="#f5b942" />
              <Line type="monotone" dataKey="health" stroke="#3ee0c5" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-1 font-mono text-[11px] text-mist">
          Blue dash is the warning. Red dash is critical. Amber is the cycle under review.
        </p>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        {engine.signatureSensors.map((sensor) => (
          <article key={sensor.key} className="rounded-lg border border-line bg-panel/80 p-3">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm">{sensor.name}</p>
              <p className="truncate text-xs text-mist">{sensor.description}</p>
            </div>
            <div className="mt-2 h-28">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={engine.series.map((item) => ({
                    cycle: item.cycle,
                    value: item.readings[sensor.key],
                  }))}
                  onClick={(state) => handleChartClick(state, jump)}
                >
                  <CartesianGrid stroke="#1c2940" vertical={false} />
                  <XAxis dataKey="cycle" hide />
                  <YAxis
                    domain={["auto", "auto"]}
                    tick={{ fill: "#93a4bd", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={48}
                  />
                  <Tooltip content={<SensorTooltip name={sensor.name} />} />
                  <ReferenceLine y={sensor.baseline} stroke="#35506e" strokeDasharray="3 3" />
                  <ReferenceLine x={point.cycle} stroke="#f5b942" />
                  <Line type="monotone" dataKey="value" stroke="#d7e3f4" strokeWidth={1.6} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        ))}
      </div>

      <label className="mt-4 block">
        <div className="mb-2 flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.16em] text-mist">
          <span>Cycle scrubber</span>
          <span>Arrow keys</span>
        </div>
        <input
          type="range"
          min={engine.series[0]?.cycle ?? 1}
          max={engine.lifeCycles}
          value={point.cycle}
          aria-label="Select cycle"
          onChange={(event) => jump(Number(event.target.value))}
          className="w-full"
        />
      </label>
    </section>
  )
}

function JumpButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-line px-3 py-1.5 text-sm text-mist hover:text-foam"
    >
      {label}
    </button>
  )
}

function Stat({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "ok" | "alert" }) {
  const color = tone === "alert" ? "text-flare" : tone === "ok" ? "text-tide" : "text-foam"
  return (
    <div className="rounded-lg border border-line bg-panel/70 px-3 py-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist">{label}</p>
      <p className={`mt-1 font-mono text-lg ${color}`}>{value}</p>
    </div>
  )
}

function HealthTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: SeriesPoint }> }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-md border border-line bg-ink px-2 py-1 text-xs">
      Cycle {point.cycle} · health {point.health.toFixed(0)} · {point.rul} left
    </div>
  )
}

function SensorTooltip({
  active,
  payload,
  name,
}: {
  active?: boolean
  payload?: Array<{ payload: { cycle: number; value: number } }>
  name: string
}) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-md border border-line bg-ink px-2 py-1 text-xs">
      {name} · cycle {point.cycle} · {point.value.toFixed(2)}
    </div>
  )
}

function handleChartClick(
  state: { activeLabel?: string | number },
  jump: (cycle: number) => void,
) {
  if (state?.activeLabel == null) return
  jump(Number(state.activeLabel))
}

interface EngineStageProps {
  engine: EngineDetail
  cycle: number
  onCycleChange: (cycle: number) => void
}
