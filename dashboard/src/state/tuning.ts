import { signal } from '@preact/signals'
import type { TuningData, Override, OverrideHistoryEntry, CorrelationResults } from '../types'
import { showToast } from '../components/Toast'

declare global {
  interface Window { __TRIGGER_KEY__: string }
}

const KEY = typeof window !== 'undefined' ? window.__TRIGGER_KEY__ : ''

// ── Signals ─────────────────────────────────────────────────────────────────
export const tuningData = signal<TuningData | null>(null)
export const tuningLoading = signal(false)
export const tuningError = signal<string | null>(null)
export const localEdits = signal<Record<string, number>>({})
export const savingParams = signal<Record<string, boolean>>({})

// ── Internal fetch helper ───────────────────────────────────────────────────
async function tuningFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { 'X-Trigger-Key': KEY, ...init?.headers },
  })
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as Record<string, string>).error || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Data fetching ───────────────────────────────────────────────────────────
export async function fetchTuningData() {
  tuningLoading.value = true
  tuningError.value = null
  try {
    const [overridesResult, correlationResult] = await Promise.allSettled([
      tuningFetch<{
        overrides: Override[]
        bounds: Record<string, { min: number; max: number }>
        defaults: Record<string, number>
        history: OverrideHistoryEntry[]
      }>('/api/overrides'),
      tuningFetch<CorrelationResults>('/api/correlation'),
    ])

    const overrides = overridesResult.status === 'fulfilled'
      ? overridesResult.value
      : { overrides: [], bounds: {}, defaults: {}, history: [] }

    const correlation = correlationResult.status === 'fulfilled'
      ? correlationResult.value
      : { layers: {}, recommendations: [], maturity: 'early' as const }

    tuningData.value = { ...overrides, correlation }
  } catch (e) {
    tuningError.value = (e as Error).message
  } finally {
    tuningLoading.value = false
  }
}

// ── Mutations ───────────────────────────────────────────────────────────────
export async function approveOverride(key: string, value: number) {
  savingParams.value = { ...savingParams.value, [key]: true }
  try {
    await tuningFetch('/api/overrides/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    })
    // Clear local edit
    const { [key]: _, ...rest } = localEdits.value
    localEdits.value = rest
    // Refetch data
    await fetchTuningData()
    showToast(`Saved: ${key}`)
  } catch (e) {
    showToast((e as Error).message, 'error')
  } finally {
    const { [key]: _, ...rest } = savingParams.value
    savingParams.value = rest
  }
}

export async function revertOverride(key: string) {
  savingParams.value = { ...savingParams.value, [key]: true }
  try {
    await tuningFetch('/api/overrides/revert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key }),
    })
    const { [key]: _, ...rest } = localEdits.value
    localEdits.value = rest
    await fetchTuningData()
    showToast(`Reverted: ${key}`)
  } catch (e) {
    showToast((e as Error).message, 'error')
  } finally {
    const { [key]: _, ...rest } = savingParams.value
    savingParams.value = rest
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────────
export function setLocalEdit(key: string, value: number) {
  localEdits.value = { ...localEdits.value, [key]: value }
}

export function clearLocalEdit(key: string) {
  const { [key]: _, ...rest } = localEdits.value
  localEdits.value = rest
}

export function getActiveValue(key: string, defaultVal: number): number {
  const overrides = tuningData.value?.overrides ?? []
  const match = overrides.find(o => o.key === key)
  return match ? match.value : defaultVal
}

export function hasOverride(key: string): boolean {
  return (tuningData.value?.overrides ?? []).some(o => o.key === key)
}

export function invalidateTuningCache() {
  tuningData.value = null
}
