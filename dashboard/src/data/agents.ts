import type { Agent } from '../types'

// Colors grouped by stage type:
// Writing stages (1-4) = cyan family
// Verification (5) = amber
// SEO (6) = teal
// Media (7-10) = purple family
// Delivery (11-13) = green family
export const AGENT_COLORS: Record<number, string> = {
  1: '#06B6D4',  // cyan-500
  2: '#22D3EE',  // cyan-400
  3: '#0891B2',  // cyan-600
  4: '#67E8F9',  // cyan-300
  5: '#F59E0B',  // amber-500
  6: '#14B8A6',  // teal-500
  7: '#8B5CF6',  // violet-500
  8: '#A78BFA',  // violet-400
  9: '#7C3AED',  // violet-600
  10: '#C4B5FD', // violet-300
  11: '#22C55E', // green-500
  12: '#4ADE80', // green-400
  13: '#16A34A', // green-600
}

export const AGENTS: Agent[] = [
  { num: 1,  name: 'Research Agent',       codename: 'ORACLE' },
  { num: 2,  name: 'Originality Agent',    codename: 'ARCHAEON' },
  { num: 3,  name: 'Narrative Architect',   codename: 'ARCHITECT' },
  { num: 4,  name: 'Script Writer',        codename: 'SCRIBE' },
  { num: 5,  name: 'Fact Verification',    codename: 'ARBITER' },
  { num: 6,  name: 'SEO Agent',            codename: 'CIPHER' },
  { num: 7,  name: 'Scene Breakdown',      codename: 'SPECTER' },
  { num: 8,  name: 'Audio Engine',         codename: 'RESONANCE' },
  { num: 9,  name: 'Footage Hunter',       codename: 'HUNTER' },
  { num: 10, name: 'Image Generator',      codename: 'VISION' },
  { num: 11, name: 'Video Assembly',       codename: 'HERALD' },
  { num: 12, name: 'Render Engine',        codename: 'CARVER' },
  { num: 13, name: 'Upload & Publish',     codename: 'MIRROR' },
]

export const SHORT_AGENTS: Agent[] = [
  { num: 1, name: 'Short Script',     codename: 'SHORT SCRIBE', short: true },
  { num: 2, name: 'Short Storyboard', codename: 'SHORT BOARD',  short: true },
  { num: 3, name: 'Short Audio',      codename: 'SHORT AUDIO',  short: true },
  { num: 4, name: 'Short Images',     codename: 'SHORT VISION', short: true },
  { num: 5, name: 'Short Convert',    codename: 'SHORT CONV',   short: true },
  { num: 6, name: 'Short Render',     codename: 'SHORT RENDER', short: true },
  { num: 7, name: 'Short Upload',     codename: 'SHORT HERALD', short: true },
]
