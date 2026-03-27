import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  pipelineStatus, isRunning, stageNum, topic, logLines,
  startedAt, analyticsRunning, liveCostUsd,
  intelCache, logPanelOpen, resetAllSignals, sseConnected, stageSummary,
} from '../state/store'
import { connectSSE, disconnectSSE } from '../state/sse'

// Mock EventSource
type EventHandler = (e: MessageEvent) => void

class MockEventSource {
  static instances: MockEventSource[] = []
  listeners: Record<string, EventHandler[]> = {}
  onerror: (() => void) | null = null
  closed = false

  constructor(_url: string) {
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, fn: EventHandler) {
    if (!this.listeners[type]) this.listeners[type] = []
    this.listeners[type]!.push(fn)
  }

  close() {
    this.closed = true
  }

  emit(type: string, data: unknown) {
    for (const fn of this.listeners[type] ?? []) {
      fn(new MessageEvent(type, { data: JSON.stringify(data) }))
    }
  }

  emitRaw(type: string) {
    for (const fn of this.listeners[type] ?? []) {
      fn(new MessageEvent(type))
    }
  }
}

vi.stubGlobal('EventSource', MockEventSource)

beforeEach(() => {
  resetAllSignals()
  disconnectSSE()
  MockEventSource.instances = []
})

describe('SSE state event', () => {
  it('updates signals from state event', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!
    es.emit('state', {
      running: true,
      last_status: 'running',
      stage: 'Stage 3',
      stage_num: 3,
      topic: 'Test Topic',
      started_at: '2026-01-01T00:00:00Z',
      finished_at: null,
      analytics_running: false,
    })

    expect(isRunning.value).toBe(true)
    expect(pipelineStatus.value).toBe('running')
    expect(stageNum.value).toBe(3)
    expect(topic.value).toBe('Test Topic')
    expect(startedAt.value).toBe('2026-01-01T00:00:00Z')
    expect(analyticsRunning.value).toBe(false)
  })

  it('resets liveCostUsd when run ends', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!

    // Simulate running state first
    es.emit('state', {
      running: true, last_status: 'running',
      stage: '', stage_num: 5, topic: 'T',
      started_at: '2026-01-01', finished_at: null,
      analytics_running: false,
    })
    liveCostUsd.value = 1.5

    // End the run
    es.emit('state', {
      running: false, last_status: 'done',
      stage: '', stage_num: 13, topic: 'T',
      started_at: null, finished_at: '2026-01-01',
      analytics_running: false,
    })

    expect(liveCostUsd.value).toBeNull()
  })

  it('auto-shows log panel on run start', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!
    logPanelOpen.value = false

    es.emit('state', {
      running: true, last_status: 'running',
      stage: '', stage_num: 1, topic: 'T',
      started_at: '2026-01-01', finished_at: null,
      analytics_running: false,
    })

    expect(logPanelOpen.value).toBe(true)
  })
})

describe('SSE log event', () => {
  it('appends log lines', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!

    es.emit('log', ['line 1', 'line 2'])
    expect(logLines.value).toEqual(['line 1', 'line 2'])

    es.emit('log', ['line 3'])
    expect(logLines.value).toEqual(['line 1', 'line 2', 'line 3'])
  })

  it('enforces 2000-line cap', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!

    logLines.value = Array.from({ length: 1999 }, (_, i) => `old-${i}`)
    es.emit('log', ['new-1', 'new-2'])
    expect(logLines.value.length).toBeLessThanOrEqual(2000)
    expect(logLines.value[logLines.value.length - 1]).toBe('new-2')
  })
})

describe('SSE cost event', () => {
  it('updates liveCostUsd', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!
    es.emit('cost', { usd_total: 2.45, tokens: 10000 })
    expect(liveCostUsd.value).toBe(2.45)
  })
})

describe('SSE stage_summary event', () => {
  it('updates stageSummary signal', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!
    const data = {
      '1': { facts: 12, sources: 5 },
      '4': { words: 1847, opening: 'In 1942...' },
    }
    es.emit('stage_summary', data)
    expect(stageSummary.value).toEqual(data)
  })
})

describe('SSE intel_updated event', () => {
  it('clears intel cache', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!
    intelCache.value = { summary: { signals: [] } }

    es.emitRaw('intel_updated')
    expect(intelCache.value).toEqual({})
  })
})

describe('sseConnected signal', () => {
  it('is true after connectSSE, false after disconnectSSE', () => {
    expect(sseConnected.value).toBe(false)
    connectSSE()
    expect(sseConnected.value).toBe(true)
    disconnectSSE()
    expect(sseConnected.value).toBe(false)
  })
})

describe('disconnectSSE', () => {
  it('closes the EventSource', () => {
    connectSSE()
    const es = MockEventSource.instances[0]!
    expect(es.closed).toBe(false)

    disconnectSSE()
    expect(es.closed).toBe(true)
  })

  it('clears backoff timer during backoff', () => {
    vi.useFakeTimers()
    connectSSE()
    const es = MockEventSource.instances[0]!

    // Trigger error to start backoff
    // Mock fetch for the pulse probe
    vi.stubGlobal('fetch', () => Promise.resolve({ status: 200 }))
    es.onerror?.()

    // Disconnect during backoff — should not reconnect
    disconnectSSE()
    vi.advanceTimersByTime(60000)

    // Only the initial connect + error-triggered one
    expect(MockEventSource.instances.length).toBeLessThanOrEqual(2)
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.stubGlobal('EventSource', MockEventSource)
  })
})
