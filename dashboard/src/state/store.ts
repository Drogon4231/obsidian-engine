import { signal, computed } from '@preact/signals'
import type { PipelineStatus, HealthStatus, LastRunData, ScheduleEntry, ErrorEntry, AgentStat } from '../types'

// Utility (safe for test environments where location may not exist)
const parseHash = () => {
  try { return location.hash.replace('#', '') || null } catch { return null }
}
const safeLocalGet = (key: string): string | null => {
  try { return globalThis.localStorage?.getItem(key) ?? null } catch { return null }
}

// ── SSE-driven signals ──────────────────────────────────────────────────────
export const pipelineStatus = signal<PipelineStatus>('idle')
export const isRunning = signal(false)
export const stageNum = signal(0)
export const topic = signal('')
export const logLines = signal<string[]>([])
export const startedAt = signal<string | null>(null)
export const finishedAt = signal<string | null>(null)
export const analyticsRunning = signal(false)
export const activeJobs = signal<Record<string, string>>({})
export const liveCostUsd = signal<number | null>(null)
export const sseConnected = signal(false)

// ── Pulse-driven signals ────────────────────────────────────────────────────
export const queueDepth = signal(0)
export const errors24h = signal(0)
export const healthStatus = signal<HealthStatus>('healthy')
export const lastCostUsd = signal<number | null>(null)

// ── UI signals ──────────────────────────────────────────────────────────────
export const currentView = signal(parseHash() || safeLocalGet('obsidian-view') || 'home')
export const logPanelOpen = signal(false)
export const slideAgent = signal<number | null>(null)
export const quickTriggerOpen = signal(false)
export const shortcutHelpOpen = signal(false)
export const completionDismissed = signal(safeLocalGet('obsidian-cd') || '')

// ── Stage telemetry (Phase D) ────────────────────────────────────────────────
export const stageSummary = signal<Record<string, Record<string, unknown>>>({})

// ── Data cache signals ──────────────────────────────────────────────────────
export const intelCache = signal<Record<string, unknown>>({})
export const lastRun = signal<LastRunData | null>(null)
export const scheduleData = signal<ScheduleEntry[] | null>(null)

// ── Observability signals (isolated — NOT in systemState) ────────
export const errorSummary = signal<ErrorEntry[] | null>(null)
export const agentStats = signal<AgentStat[] | null>(null)
export const pulseHistory = signal<{ queue: number[]; errors: number[]; cost: number[] }>({
  queue: [],
  errors: [],
  cost: [],
})

// ── Derived ─────────────────────────────────────────────────────────────────
export const systemState = computed(() => {
  if (isRunning.value) return 'running' as const
  if (
    pipelineStatus.value === 'done' &&
    finishedAt.value &&
    completionDismissed.value !== finishedAt.value
  )
    return 'just-completed' as const
  if (['failed', 'error', 'killed'].includes(pipelineStatus.value)) return 'error' as const
  return 'idle' as const
})

// ── Reset for tests ─────────────────────────────────────────────────────────
export function resetAllSignals() {
  pipelineStatus.value = 'idle'
  isRunning.value = false
  stageNum.value = 0
  topic.value = ''
  logLines.value = []
  startedAt.value = null
  finishedAt.value = null
  analyticsRunning.value = false
  activeJobs.value = {}
  liveCostUsd.value = null
  sseConnected.value = false
  queueDepth.value = 0
  errors24h.value = 0
  healthStatus.value = 'healthy'
  lastCostUsd.value = null
  currentView.value = 'home'
  logPanelOpen.value = false
  slideAgent.value = null
  quickTriggerOpen.value = false
  shortcutHelpOpen.value = false
  stageSummary.value = {}
  completionDismissed.value = ''
  intelCache.value = {}
  lastRun.value = null
  scheduleData.value = null
  pulseHistory.value = { queue: [], errors: [], cost: [] }
  errorSummary.value = null
  agentStats.value = null
}
