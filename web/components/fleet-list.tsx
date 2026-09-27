"use client"

import { useEffect, useRef } from "react"
import { formatUnit, PATTERN_LABEL, STATUS_LABEL } from "@/lib/format"
import type { EngineSummary } from "@/lib/types"

export function FleetList({
  engines,
  recommendedUnitId,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  emptyLabel,
}: FleetListProps) {
  const selectedRef = useRef<HTMLButtonElement>(null)
  const needle = query.trim()
  const filtered = engines.filter(
    (engine) => formatUnit(engine.unitId).includes(needle) || String(engine.unitId).includes(needle),
  )
  const visible = [...filtered].sort((left, right) => {
    if (left.unitId === recommendedUnitId) return -1
    if (right.unitId === recommendedUnitId) return 1
    return 0
  })

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" })
  }, [selectedId])

  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden border-b border-line lg:border-b-0 lg:border-r">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist">Detect · fleet</p>
          <p className="font-mono text-[11px] text-mist">{visible.length}</p>
        </div>
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Find an engine"
          aria-label="Find an engine"
          className="mt-3 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-mist/70 focus:border-amber"
        />
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {visible.length === 0 && emptyLabel ? <p className="px-4 py-6 text-sm leading-6 text-mist">{emptyLabel}</p> : null}
        {visible.map((engine) => {
          const isSelected = engine.unitId === selectedId
          const isStart = engine.unitId === recommendedUnitId
          return (
            <button
              key={engine.unitId}
              ref={isSelected ? selectedRef : undefined}
              type="button"
              data-testid={`engine-${engine.unitId}`}
              onClick={() => onSelect(engine.unitId)}
              className={`block w-full border-b border-line px-4 py-3 text-left transition ${
                isSelected ? "bg-white/[0.04] shadow-[inset_3px_0_0_#f5b942]" : "hover:bg-white/[0.03]"
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-mono text-sm">ENG {formatUnit(engine.unitId)}</span>
                <span className="font-mono text-xs text-amber">{engine.leadTime} {engine.pattern === "shop" ? "hr" : "cyc"} lead</span>
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-mist">
                <span>{STATUS_LABEL[engine.status] ?? engine.status}</span>
                <span aria-hidden="true">·</span>
                <span>{PATTERN_LABEL[engine.pattern] ?? engine.pattern}</span>
                {isStart ? <span className="text-tide">Start here</span> : null}
                <span>{engine.origin === "import" ? "Shop file" : "NASA demo"}</span>
              </div>
              <p className="mt-2 font-mono text-[11px] text-mist">
                {sensorWords(engine.topSensors)}
              </p>
              <p className="mt-1 text-[11px] text-mist">Health {Math.round(engine.healthAtWarning)} at warning</p>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

function sensorWords(sensors: EngineSummary["topSensors"]) {
  const words = sensors
    .filter((sensor) => sensor.direction === "high" || sensor.direction === "low")
    .map((sensor) => `${sensor.name} ${sensor.direction}`)
  return words.join(" · ")
}

interface FleetListProps {
  engines: EngineSummary[]
  recommendedUnitId: number
  selectedId: number | null
  query: string
  onQueryChange: (query: string) => void
  onSelect: (unitId: number) => void
  emptyLabel?: string
}
