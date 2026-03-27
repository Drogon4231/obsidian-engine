import { batch } from '@preact/signals'
import {
  pipelineStatus, isRunning, stageNum, topic, logLines,
  startedAt, finishedAt, analyticsRunning, activeJobs, liveCostUsd,
  intelCache, logPanelOpen, sseConnected, stageSummary,
} from './store'
import { invalidateTuningCache } from './tuning'
import type { PipelineStatus, CostEvent } from '../types'

declare global {
  interface Window { __TRIGGER_KEY__: string }
}

let eventSource: EventSource | null = null
let backoffMs = 1000
let backoffTimer: ReturnType<typeof setTimeout> | null = null
const MAX_BACKOFF = 30000
const MAX_LOG_LINES = 2000

export function connectSSE() {
  if (eventSource) return

  // NOTE: EventSource API does not support custom headers.
  // The trigger key is passed as a query parameter. This is an accepted
  // trade-off — the key appears in server logs / browser history but there
  // is no alternative with native EventSource. Authenticated sessions
  // (Flask session cookie) are also accepted by the /stream route.
  const key = typeof window !== 'undefined' ? window.__TRIGGER_KEY__ : ''
  const url = `/stream?key=${encodeURIComponent(key)}`
  eventSource = new EventSource(url)
  backoffMs = 1000
  if (backoffTimer) { clearTimeout(backoffTimer); backoffTimer = null }
  sseConnected.value = true

  eventSource.addEventListener('state', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as {
        running: boolean
        last_status: PipelineStatus
        stage: string
        stage_num: number
        topic: string
        started_at: string | null
        finished_at: string | null
        analytics_running: boolean
        active_jobs?: Record<string, string>
      }
      batch(() => {
        const wasRunning = isRunning.value
        pipelineStatus.value = data.last_status
        isRunning.value = data.running
        stageNum.value = data.stage_num
        topic.value = data.topic
        startedAt.value = data.started_at
        finishedAt.value = data.finished_at
        analyticsRunning.value = data.analytics_running
        if (data.active_jobs) activeJobs.value = data.active_jobs

        // Reset cost when run ends
        if (wasRunning && !data.running) {
          liveCostUsd.value = null
        }

        // Auto-show log panel on run start
        if (!wasRunning && data.running) {
          logPanelOpen.value = true
        }
      })
    } catch {
      // Malformed SSE data — skip
    }
  })

  eventSource.addEventListener('log', (e: MessageEvent) => {
    try {
      const newLines = JSON.parse(e.data) as string[]
      logLines.value = [...logLines.value, ...newLines].slice(-MAX_LOG_LINES)
    } catch {
      // skip
    }
  })

  eventSource.addEventListener('cost', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as CostEvent
      liveCostUsd.value = data.usd_total
    } catch {
      // skip
    }
  })

  eventSource.addEventListener('stage_summary', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as Record<string, Record<string, unknown>>
      stageSummary.value = data
    } catch {
      // skip
    }
  })

  eventSource.addEventListener('intel_updated', () => {
    intelCache.value = {}
  })

  eventSource.addEventListener('tuning_updated', () => {
    invalidateTuningCache()
  })

  eventSource.addEventListener('reconnect', () => {
    // Server requested reconnect (lifetime exceeded)
    disconnectSSE()
    setTimeout(connectSSE, 1000)
  })

  eventSource.onerror = () => {
    sseConnected.value = false
    disconnectSSE()
    // Probe pulse to check if auth is valid
    fetch('/api/pulse', { headers: { 'X-Trigger-Key': key } })
      .then(res => {
        if (res.status === 401) {
          window.location.href = '/login'
          return
        }
        // Reconnect with exponential backoff
        backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF)
        backoffTimer = setTimeout(connectSSE, backoffMs)
      })
      .catch(() => {
        backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF)
        backoffTimer = setTimeout(connectSSE, backoffMs)
      })
  }
}

export function disconnectSSE() {
  sseConnected.value = false
  if (backoffTimer) { clearTimeout(backoffTimer); backoffTimer = null }
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}
