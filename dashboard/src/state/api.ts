import { batch } from '@preact/signals'
import type { PulseResponse, DashboardResponse, LastRunData, ScheduleEntry, RunDetail, ErrorEntry, AgentStat } from '../types'
import {
  pipelineStatus, isRunning, stageNum, topic, startedAt, finishedAt,
  analyticsRunning, queueDepth, errors24h, healthStatus, lastCostUsd,
  intelCache, lastRun, scheduleData, pulseHistory,
  errorSummary, agentStats,
} from './store'

declare global {
  interface Window { __TRIGGER_KEY__: string }
}

const KEY = typeof window !== 'undefined' ? window.__TRIGGER_KEY__ : ''

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      'X-Trigger-Key': KEY,
      ...init?.headers,
    },
  })
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchPulse() {
  const data = await apiFetch<PulseResponse>('/api/pulse')
  batch(() => {
    pipelineStatus.value = data.status
    isRunning.value = data.running
    stageNum.value = data.stage_num
    topic.value = data.topic
    startedAt.value = data.started_at
    finishedAt.value = data.finished_at
    analyticsRunning.value = data.analytics_running
    queueDepth.value = data.queue_depth ?? 0
    errors24h.value = data.errors_24h ?? 0
    healthStatus.value = data.health ?? 'healthy'
    lastCostUsd.value = data.last_cost_usd

    // Append to pulse history for sparklines
    const h = pulseHistory.value
    pulseHistory.value = {
      queue: [...h.queue, data.queue_depth ?? 0].slice(-10),
      errors: [...h.errors, data.errors_24h ?? 0].slice(-10),
      cost: [...h.cost, data.last_cost_usd ?? 0].slice(-10),
    }
  })
  return data
}

export async function fetchDashboard(sections: string): Promise<DashboardResponse> {
  const data = await apiFetch<DashboardResponse>(`/api/dashboard?sections=${sections}`)
  // Cache fetched sections
  const updated = { ...intelCache.value }
  for (const [key, val] of Object.entries(data)) {
    updated[key] = val
  }
  intelCache.value = updated
  return data
}

export async function fetchHistory(): Promise<LastRunData[]> {
  return apiFetch<LastRunData[]>('/history')
}

export async function fetchSchedule(): Promise<{ schedule: ScheduleEntry[] }> {
  return apiFetch<{ schedule: ScheduleEntry[] }>('/schedule')
}

export async function triggerPipeline(topicStr: string, resumeFrom = 1) {
  return apiFetch<{ ok: boolean; topic: string }>('/trigger', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: topicStr, resume_from: resumeFrom }),
  })
}

export async function killPipeline() {
  return apiFetch<{ ok: boolean }>('/kill', { method: 'POST' })
}

export async function fetchQueue() {
  return apiFetch<Array<Record<string, unknown>>>('/queue')
}

export async function addToQueue(topicStr: string) {
  return apiFetch<Record<string, unknown>>('/queue/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: topicStr }),
  })
}

export async function deleteFromQueue(id: string) {
  return apiFetch<{ ok: boolean }>('/queue/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
}

// Pulse polling with rate switching
let pulseInterval: ReturnType<typeof setInterval> | null = null

export function startPulsePolling() {
  stopPulsePolling()
  // Initial fetch
  fetchPulse().catch(() => {})
  // Poll every 5s when idle, 15s when running
  const tick = () => {
    const interval = isRunning.value ? 15000 : 5000
    pulseInterval = setTimeout(() => {
      fetchPulse().catch(() => {}).finally(tick)
    }, interval)
  }
  tick()
}

export function stopPulsePolling() {
  if (pulseInterval !== null) {
    clearTimeout(pulseInterval)
    pulseInterval = null
  }
}

// Convenience: fetch last run data on completion
export async function fetchLastRun() {
  const history = await fetchHistory()
  if (history.length > 0) {
    lastRun.value = history[history.length - 1] ?? null
  }
}

export async function fetchScheduleData() {
  const data = await fetchSchedule()
  scheduleData.value = data.schedule
}

export interface LastErrorData {
  stage_name: string
  stage_num: number
  diagnosis: string
  root_cause: string
  strategy: string
  error: string
  timestamp: string
}

export async function fetchLastError(): Promise<LastErrorData | null> {
  try {
    return await apiFetch<LastErrorData>('/api/last-error')
  } catch {
    return null
  }
}

export async function fetchRunDetail(runId?: string): Promise<RunDetail | null> {
  try {
    const url = runId ? `/api/run-detail?run_id=${runId}` : '/api/run-detail'
    return await apiFetch<RunDetail>(url)
  } catch {
    return null
  }
}

export async function fetchErrorSummary(hours = 24) {
  const data = await apiFetch<ErrorEntry[]>(`/api/errors?hours=${hours}`)
  errorSummary.value = data
  return data
}

export async function fetchAgentStats(days = 7) {
  const data = await apiFetch<AgentStat[]>(`/api/agent-stats?days=${days}`)
  agentStats.value = data
  return data
}
