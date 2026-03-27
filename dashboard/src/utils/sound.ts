let ctx: AudioContext | null = null
const STORAGE_KEY = 'obsidian-sound'

function getEnabled(): boolean {
  try {
    return typeof localStorage !== 'undefined' && globalThis.localStorage?.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function ensureContext(): AudioContext | null {
  if (!ctx) {
    try {
      ctx = new AudioContext()
    } catch {
      return null
    }
  }
  return ctx
}

function playTone(freq: number, duration: number, type: OscillatorType = 'sine', amp = 0.15) {
  if (!getEnabled()) return
  const c = ensureContext()
  if (!c) return
  const osc = c.createOscillator()
  const gain = c.createGain()
  osc.type = type
  osc.frequency.value = freq
  gain.gain.value = amp
  gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + duration + 0.3)
  osc.connect(gain)
  gain.connect(c.destination)
  osc.start()
  osc.stop(c.currentTime + duration + 0.3)
}

export function playStageChange() {
  if (!getEnabled()) return
  const c = ensureContext()
  if (!c) return
  const osc = c.createOscillator()
  const gain = c.createGain()
  osc.frequency.setValueAtTime(520, c.currentTime)
  osc.frequency.exponentialRampToValueAtTime(780, c.currentTime + 0.1)
  gain.gain.value = 0.15
  gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 0.4)
  osc.connect(gain)
  gain.connect(c.destination)
  osc.start()
  osc.stop(c.currentTime + 0.4)
}

export function playComplete() {
  playTone(440, 0.15)
  setTimeout(() => playTone(660, 0.15), 150)
}

export function playError() {
  playTone(220, 0.2, 'sawtooth')
}

export function toggleSound(): boolean {
  const next = !getEnabled()
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, next ? '1' : '0')
  } catch {
    // no-op
  }
  if (next) ensureContext()
  return next
}

export function isSoundEnabled(): boolean {
  return getEnabled()
}
