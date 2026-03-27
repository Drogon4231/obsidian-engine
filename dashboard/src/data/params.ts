import type { ParamBound } from '../types'

export const PARAM_DEFS: ParamBound[] = [
  // ── Long-Form Parameters ──────────────────────────────────────────────────
  {
    key: 'voice_speed.quote', label: 'Quote Reading Speed',
    description: 'How fast historical quotes are narrated. Lower = more dramatic.',
    group: 'long_form', groupLabel: 'Long-Form Parameters',
    min: 0.60, max: 0.90, default: 0.74, step: 0.01, unit: 'x',
  },
  {
    key: 'voice_speed.quote_legacy', label: 'Legacy Quote Speed',
    description: 'Narration speed for older-style quotes. Slightly faster.',
    group: 'long_form', groupLabel: 'Long-Form Parameters',
    min: 0.70, max: 0.95, default: 0.85, step: 0.01, unit: 'x',
  },
  {
    key: 'pause.reveal', label: 'Reveal Pause',
    description: 'Dramatic pause before a key revelation. Longer = more suspense.',
    group: 'long_form', groupLabel: 'Long-Form Parameters',
    min: 0.5, max: 5.0, default: 1.8, step: 0.05, unit: 's',
  },
  {
    key: 'pause.breathing', label: 'Breathing Pause',
    description: 'Natural pause between sentences. Affects overall pacing.',
    group: 'long_form', groupLabel: 'Long-Form Parameters',
    min: 0.3, max: 3.0, default: 1.2, step: 0.05, unit: 's',
  },
  {
    key: 'pause.act_transition', label: 'Act Transition Pause',
    description: 'Pause between major story acts. Time to absorb.',
    group: 'long_form', groupLabel: 'Long-Form Parameters',
    min: 0.2, max: 2.0, default: 0.9, step: 0.05, unit: 's',
  },
  {
    key: 'pause.default', label: 'Default Pause',
    description: 'Standard inter-sentence pause. The baseline rhythm.',
    group: 'long_form', groupLabel: 'Long-Form Parameters',
    min: 0.1, max: 1.5, default: 0.4, step: 0.05, unit: 's',
  },

  // ── Shorts Speed ──────────────────────────────────────────────────────────
  {
    key: 'short.voice_speed', label: 'Short Voice Speed',
    description: 'Main narration speed for Shorts. Faster keeps attention.',
    group: 'short_speed', groupLabel: 'Shorts Speed',
    min: 0.78, max: 1.02, default: 0.88, step: 0.01, unit: 'x',
    brandRef: 'voice_speed.quote', brandThreshold: 0.15,
  },
  {
    key: 'short.hook_speed', label: 'Short Hook Speed',
    description: 'Opening hook speed. Slightly faster to grab attention.',
    group: 'short_speed', groupLabel: 'Shorts Speed',
    min: 0.82, max: 1.05, default: 0.92, step: 0.01, unit: 'x',
  },

  // ── Shorts Voice Character ────────────────────────────────────────────────
  {
    key: 'short.voice_stability', label: 'Short Voice Stability',
    description: 'How consistent the AI voice sounds. Lower = more expressive.',
    group: 'short_voice', groupLabel: 'Shorts Voice Character',
    min: 0.20, max: 0.55, default: 0.38, step: 0.01,
  },
  {
    key: 'short.voice_style', label: 'Short Voice Style',
    description: 'Exaggeration level. Higher = more dramatic.',
    group: 'short_voice', groupLabel: 'Shorts Voice Character',
    min: 0.30, max: 0.85, default: 0.60, step: 0.01,
  },
  {
    key: 'short.hook_stability', label: 'Hook Voice Stability',
    description: 'Stability of hook voice. Lower for more energy.',
    group: 'short_voice', groupLabel: 'Shorts Voice Character',
    min: 0.15, max: 0.45, default: 0.28, step: 0.01,
  },
  {
    key: 'short.hook_style', label: 'Hook Voice Style',
    description: 'Style exaggeration for hook. High for max impact.',
    group: 'short_voice', groupLabel: 'Shorts Voice Character',
    min: 0.40, max: 0.95, default: 0.75, step: 0.01,
  },
  {
    key: 'short.similarity_boost', label: 'Voice Consistency',
    description: 'How closely Short voice matches main channel voice.',
    group: 'short_voice', groupLabel: 'Shorts Voice Character',
    min: 0.65, max: 0.95, default: 0.82, step: 0.01,
  },
  {
    key: 'short.hook_similarity_boost', label: 'Hook Voice Consistency',
    description: 'How closely hook voice matches main voice.',
    group: 'short_voice', groupLabel: 'Shorts Voice Character',
    min: 0.70, max: 0.98, default: 0.85, step: 0.01,
  },

  // ── Shorts Timing ─────────────────────────────────────────────────────────
  {
    key: 'short.tail_buffer_sec', label: 'Short Tail Buffer',
    description: 'Silence before a Short loops. Affects rewatch feel.',
    group: 'short_timing', groupLabel: 'Shorts Timing',
    min: 0.3, max: 2.5, default: 1.5, step: 0.05, unit: 's',
  },
]

export const PARAM_BY_KEY = Object.fromEntries(PARAM_DEFS.map(p => [p.key, p]))

export const PARAM_GROUPS = [
  { id: 'long_form', label: 'Long-Form Parameters' },
  { id: 'short_speed', label: 'Shorts Speed' },
  { id: 'short_voice', label: 'Shorts Voice Character' },
  { id: 'short_timing', label: 'Shorts Timing' },
] as const

export const LAYER_DEFS = [
  { id: 1, name: 'LF Param \u2192 Metrics', phase: 'Phase B', requirement: 'Requires param variation from manual overrides' },
  { id: 2, name: 'Short Param \u2192 Metrics', phase: 'Phase B', requirement: 'Requires param variation from manual overrides' },
  { id: 3, name: 'Topic Health', phase: 'Phase A', requirement: '2+ topics with 2+ videos each' },
  { id: 4, name: 'Audience Transformation', phase: 'Phase B', requirement: '3+ paired topics with before/after data' },
  { id: 5, name: 'Short \u2192 Parent Lift', phase: 'Phase B/C', requirement: 'Layers 2+4 at moderate confidence' },
  { id: 6, name: 'Era Stratification', phase: 'Phase C', requirement: '5+ videos per era with varied params' },
  { id: 7, name: 'Cross-Format Signal', phase: 'Phase C', requirement: 'Layers 1+2 at moderate confidence' },
]

export function formatParamValue(value: number, param: ParamBound): string {
  if (param.unit === 'x') return `${value.toFixed(2)}x`
  if (param.unit === 's') return `${value.toFixed(2)}s`
  return value.toFixed(2)
}
