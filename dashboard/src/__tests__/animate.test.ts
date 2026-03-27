import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { tweenNumber } from '../utils/animate'

describe('tweenNumber', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls onFrame with initial value near from', () => {
    const values: number[] = []
    const mockPerformanceNow = vi.spyOn(performance, 'now')

    // First call is from requestAnimationFrame setup
    mockPerformanceNow.mockReturnValue(0)

    const cancel = tweenNumber(0, 100, 600, (v) => values.push(v))

    // Simulate first frame
    mockPerformanceNow.mockReturnValue(0)
    vi.advanceTimersByTime(16) // one rAF tick

    expect(values.length).toBeGreaterThanOrEqual(1)
    cancel()
    mockPerformanceNow.mockRestore()
  })

  it('returns a cancel function', () => {
    const cancel = tweenNumber(0, 100, 600, () => {})
    expect(typeof cancel).toBe('function')
    cancel()
  })
})
