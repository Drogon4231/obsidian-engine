import { describe, it, expect, beforeEach } from 'vitest'
import {
  pipelineStatus, isRunning, finishedAt, completionDismissed,
  systemState, resetAllSignals, stageNum, topic, logLines,
  startedAt, analyticsRunning, liveCostUsd, queueDepth,
  errors24h, healthStatus, lastCostUsd, currentView,
  logPanelOpen, slideAgent, quickTriggerOpen, shortcutHelpOpen, stageSummary, intelCache,
  lastRun, scheduleData, pulseHistory, sseConnected,
  errorSummary, agentStats,
} from '../state/store'

beforeEach(() => {
  resetAllSignals()
})

describe('systemState', () => {
  it('returns running when isRunning is true', () => {
    isRunning.value = true
    expect(systemState.value).toBe('running')
  })

  it('returns just-completed when done + not dismissed', () => {
    pipelineStatus.value = 'done'
    finishedAt.value = '2026-01-01T00:00:00Z'
    completionDismissed.value = ''
    expect(systemState.value).toBe('just-completed')
  })

  it('returns idle when done + dismissed', () => {
    pipelineStatus.value = 'done'
    finishedAt.value = '2026-01-01T00:00:00Z'
    completionDismissed.value = '2026-01-01T00:00:00Z'
    expect(systemState.value).toBe('idle')
  })

  it('returns error on failed', () => {
    pipelineStatus.value = 'failed'
    expect(systemState.value).toBe('error')
  })

  it('returns error on error', () => {
    pipelineStatus.value = 'error'
    expect(systemState.value).toBe('error')
  })

  it('returns error on killed (not idle)', () => {
    pipelineStatus.value = 'killed'
    expect(systemState.value).toBe('error')
  })

  it('returns idle by default', () => {
    expect(systemState.value).toBe('idle')
  })
})

describe('resetAllSignals', () => {
  it('resets all signals to defaults', () => {
    // Mutate everything
    pipelineStatus.value = 'running'
    isRunning.value = true
    stageNum.value = 5
    topic.value = 'test'
    logLines.value = ['line1']
    startedAt.value = 'x'
    finishedAt.value = 'x'
    analyticsRunning.value = true
    liveCostUsd.value = 1.5
    sseConnected.value = true
    queueDepth.value = 10
    errors24h.value = 5
    healthStatus.value = 'unhealthy'
    lastCostUsd.value = 2.0
    currentView.value = 'intel'
    logPanelOpen.value = true
    slideAgent.value = 3
    quickTriggerOpen.value = true
    shortcutHelpOpen.value = true
    stageSummary.value = { '1': { facts: 5 } }
    completionDismissed.value = 'x'
    intelCache.value = { a: 1 }
    lastRun.value = { topic: 't', status: 's', started_at: '', finished_at: '', elapsed_seconds: 0, cost_usd: 0, stages_completed: 0 }
    scheduleData.value = []
    pulseHistory.value = { queue: [1], errors: [2], cost: [3] }
    errorSummary.value = [{ timestamp: '', agent: 'test', error_type: 'Error', error_message: '', severity: 'error', count: 1, dedup_key: 'x' }]
    agentStats.value = [{ agent: 'test', calls: 1, avg_latency: 0, p95_latency: 0, success_rate: 100, sla_breach_rate: 0, avg_input_tokens: 0, avg_output_tokens: 0 }]

    resetAllSignals()

    expect(pipelineStatus.value).toBe('idle')
    expect(isRunning.value).toBe(false)
    expect(stageNum.value).toBe(0)
    expect(topic.value).toBe('')
    expect(logLines.value).toEqual([])
    expect(startedAt.value).toBeNull()
    expect(finishedAt.value).toBeNull()
    expect(analyticsRunning.value).toBe(false)
    expect(liveCostUsd.value).toBeNull()
    expect(sseConnected.value).toBe(false)
    expect(queueDepth.value).toBe(0)
    expect(errors24h.value).toBe(0)
    expect(healthStatus.value).toBe('healthy')
    expect(lastCostUsd.value).toBeNull()
    expect(currentView.value).toBe('home')
    expect(logPanelOpen.value).toBe(false)
    expect(slideAgent.value).toBeNull()
    expect(quickTriggerOpen.value).toBe(false)
    expect(shortcutHelpOpen.value).toBe(false)
    expect(stageSummary.value).toEqual({})
    expect(completionDismissed.value).toBe('')
    expect(intelCache.value).toEqual({})
    expect(lastRun.value).toBeNull()
    expect(scheduleData.value).toBeNull()
    expect(pulseHistory.value).toEqual({ queue: [], errors: [], cost: [] })
    expect(errorSummary.value).toBeNull()
    expect(agentStats.value).toBeNull()
  })
})
