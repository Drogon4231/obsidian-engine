import { http, HttpResponse } from 'msw'
import type { PulseResponse, DashboardResponse, LastRunData } from '../types'

const mockPulse: PulseResponse = {
  status: 'idle',
  running: false,
  stage: '',
  stage_num: 0,
  topic: '',
  started_at: null,
  finished_at: null,
  analytics_running: false,
  queue_depth: 3,
  errors_24h: 0,
  health: 'healthy',
  last_cost_usd: 1.23,
}

const mockDashboard: DashboardResponse = {
  summary: {
    signals: [
      { label: 'Last Run', value: 'Flight 19 — done', type: 'info' },
      { label: 'Best Era', value: 'Cold War', type: 'success' },
      { label: 'Retention', value: '45% avg', type: 'info' },
      { label: 'Top Request', value: 'More conspiracy content', type: 'info' },
      { label: 'System', value: 'All systems nominal', type: 'success' },
    ],
  },
}

const mockHistory: LastRunData[] = [
  {
    topic: 'Flight 19',
    status: 'done',
    started_at: '2026-03-20T10:00:00Z',
    finished_at: '2026-03-20T10:30:00Z',
    elapsed_seconds: 1800,
    cost_usd: 1.23,
    stages_completed: 13,
  },
]

export const handlers = [
  http.get('/api/pulse', () => HttpResponse.json(mockPulse)),

  http.get('/api/dashboard', ({ request }) => {
    const url = new URL(request.url)
    const sections = url.searchParams.get('sections') || 'summary'
    if (sections === 'summary') return HttpResponse.json(mockDashboard)
    return HttpResponse.json({})
  }),

  http.get('/history', () => HttpResponse.json(mockHistory)),

  http.get('/queue', () => HttpResponse.json([])),

  http.post('/trigger', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ ok: true, topic: body.topic })
  }),

  http.post('/kill', () => HttpResponse.json({ ok: true })),

  http.post('/queue/add', () => HttpResponse.json({ ok: true })),

  http.post('/queue/delete', () => HttpResponse.json({ ok: true })),

  http.get('/schedule', () => HttpResponse.json({
    schedule: [
      { day: 'MON', time_utc: '08:00', job: 'TOPIC DISCOVERY' },
      { day: 'DAILY', time_utc: '06:00', job: 'ANALYTICS LOOP' },
    ],
  })),

  http.get('/music', () => HttpResponse.json({ total_tracks: 10, tracks_by_mood: {}, moods: [] })),
  http.get('/trends', () => HttpResponse.json({ trends: [] })),
  http.get('/audit', () => HttpResponse.json({ entries: [], total: 0 })),
]
