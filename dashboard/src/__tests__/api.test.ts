import { describe, it, expect, beforeEach } from 'vitest'
import { resetAllSignals, pipelineStatus, queueDepth, errors24h } from '../state/store'
import { fetchPulse } from '../state/api'

beforeEach(() => {
  resetAllSignals()
})

describe('fetchPulse', () => {
  it('updates store signals from pulse response', async () => {
    await fetchPulse()
    expect(pipelineStatus.value).toBe('idle')
    expect(queueDepth.value).toBe(3)
    expect(errors24h.value).toBe(0)
  })
})
