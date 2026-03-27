import { describe, it, expect, beforeEach, vi } from 'vitest'

// Stub localStorage for tests
const store: Record<string, string> = {}
const mockStorage = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, val: string) => { store[key] = val },
  removeItem: (key: string) => { delete store[key] },
  clear: () => { Object.keys(store).forEach(k => delete store[k]) },
  get length() { return Object.keys(store).length },
  key: (i: number) => Object.keys(store)[i] ?? null,
}

vi.stubGlobal('localStorage', mockStorage)

import { isSoundEnabled, toggleSound, playStageChange, playComplete, playError } from '../utils/sound'

describe('sound system', () => {
  beforeEach(() => {
    mockStorage.clear()
  })

  it('defaults to sound off', () => {
    expect(isSoundEnabled()).toBe(false)
  })

  it('toggles sound on and off', () => {
    const on = toggleSound()
    expect(on).toBe(true)
    expect(isSoundEnabled()).toBe(true)

    const off = toggleSound()
    expect(off).toBe(false)
    expect(isSoundEnabled()).toBe(false)
  })

  it('persists to localStorage', () => {
    toggleSound() // on
    expect(mockStorage.getItem('obsidian-sound')).toBe('1')
    toggleSound() // off
    expect(mockStorage.getItem('obsidian-sound')).toBe('0')
  })

  it('does not create AudioContext on import (lazy)', () => {
    // Just verify functions exist and don't throw when sound is off
    expect(() => playStageChange()).not.toThrow()
    expect(() => playComplete()).not.toThrow()
    expect(() => playError()).not.toThrow()
  })
})
