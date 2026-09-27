export function formatUnit(unitId: number) {
  return unitId.toString().padStart(2, "0")
}

export function formatShare(value: number) {
  return `${Math.round(value * 100)}%`
}

export const STATUS_LABEL: Record<string, string> = {
  early: "Early warning",
  actionable: "Actionable",
  late: "Short notice",
  sensor: "Sensor fault",
}

export const OUTCOME_LABEL: Record<string, string> = {
  worked: "Cheaper order worked",
  did_not: "Still needed the expensive step",
  too_soon: "Too soon to know",
}

export const PATTERN_LABEL: Record<string, string> = {
  degradation: "Hot-section wear",
  mixed: "Mixed drift",
  sensor: "Possible sensor fault",
  shop: "Shop wear",
}
