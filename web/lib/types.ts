export interface SensorBrief {
  key: string
  name: string
  description: string
  zScore: number
  direction: "high" | "low" | "nominal"
}

export interface EngineSummary {
  unitId: number
  lifeCycles: number
  warningCycle: number
  criticalCycle: number | null
  leadTime: number
  healthAtWarning: number
  agreement: number
  pattern: "degradation" | "mixed" | "sensor" | "shop"
  status: "early" | "actionable" | "late" | "sensor"
  mechanism: string
  topSensors: SensorBrief[]
  origin: "sample" | "import"
}

export interface FleetStats {
  engines: number
  cycles: number
  features: number
  estimators: number
  healthyOutlierRate: number
  lateLifeOutlierRate: number
  medianLeadTime: number
}

export interface FleetResponse {
  dataset: string
  model: string
  shop: string
  hasShopAssets: boolean
  recommendedUnitId: number
  activeSensors: string[]
  droppedSensors: string[]
  threshold: number
  stats: FleetStats
  engines: EngineSummary[]
}

export interface SignatureSensor {
  key: string
  name: string
  description: string
  baseline: number
}

export interface SeriesPoint {
  cycle: number
  health: number
  isAnomaly: boolean
  rul: number
  readings: Record<string, number>
}

export interface EngineDetail {
  unitId: number
  lifeCycles: number
  warningCycle: number
  criticalCycle: number | null
  leadTime: number
  healthAtWarning: number
  pattern: "degradation" | "mixed" | "sensor" | "shop"
  agreement: number
  mechanism: string
  origin: "sample" | "import"
  trainedOn: string
  signatureSensors: SignatureSensor[]
  series: SeriesPoint[]
}

export interface Contributor extends SensorBrief {
  value: number
  baseline: number
  delta: number
}

export interface SignatureMark {
  key: string
  name: string
  direction: "high" | "low"
}

export interface SensorMap {
  column: string
  key: string
  name: string
  description: string
}

export interface HistoryMapping {
  unit: string
  cycle: string
  sensors: SensorMap[]
  healthyLimit: number
}

export interface HistoryPreview {
  kind: "nasa" | "shop"
  headers: string[]
  preview: Record<string, string | number>[]
  mapping: HistoryMapping
  provider: "xai" | "template"
  trace: string
}

export interface ParsedManual {
  id: string
  title: string
  steps: string[]
  provider: "xai" | "template"
  trace: string
}

export interface ManualSection {
  pattern: "degradation" | "sensor" | "mixed" | "shop"
  id: string
  title: string
  source: string
  steps: string[]
}

export type Outcome = "worked" | "did_not" | "too_soon"

export interface ShopMemory {
  unitId: number
  cycle: number
  shared: SignatureMark[]
  sharedText: string
  steps: string[]
  cause: string
  resolved: boolean
  outcome: Outcome
  decision: string
  manualSection: string
  author: string
}

export interface ShopInfo {
  name: string
  shopId?: string
  passphraseHint: string | null
  demoTools?: boolean
}

export interface ShopSession {
  shop: string
  shopId?: string
  name: string
  token: string
  role?: "lead" | "technician"
}

export interface CaseExplanation {
  summary: string
  provider: "xai" | "template"
  model: string | null
  trace: string
}

export interface DraftStep {
  source: number
  text: string
  sensors: string[]
  moved: boolean
}

export interface ProcedureDraft {
  steps: DraftStep[]
  reason: string | null
  provider: "xai" | "template"
  model: string | null
  trace: string
}

export interface MaintenanceCase {
  unitId: number
  cycle: number
  stage: "early" | "degrading" | "late"
  whatHappened: string
  evidence: Contributor[]
  signature: SignatureMark[]
  manual: ManualSection
  suggestedSteps: string[]
  shopMemory: ShopMemory | null
  ownFix: { cause: string; resolved: boolean; outcome: Outcome; steps: string[]; author: string } | null
  aiSummary: string
  recallUnitId: number | null
}

export interface ReviewedFix {
  id: number
  createdAt: string
  unitId: number
  cycle: number
  cause: string
  resolved: boolean
  decision: string
  steps: string[]
  author: string
  outcome: Outcome
}

export interface DemoSeed {
  reviewedUnitId: number
  recallUnitId: number | null
  fixes: ReviewedFix[]
}

