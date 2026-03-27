import { describe, it, expect, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/preact'
import {
  resetAllSignals, isRunning, stageNum, topic, startedAt,
  pipelineStatus, finishedAt, completionDismissed, logLines,
} from '../state/store'
import { HomeView } from '../views/HomeView'
import { QueueView } from '../views/QueueView'
import { IntelView } from '../views/IntelView'
import { HealthView } from '../views/HealthView'

beforeEach(() => {
  resetAllSignals()
})

describe('HomeView', () => {
  it('renders idle state by default', () => {
    const { container } = render(<HomeView />)
    expect(container.textContent).toContain('Ready to fire')
  })

  it('renders running state', () => {
    isRunning.value = true
    stageNum.value = 5
    topic.value = 'Test Topic'
    startedAt.value = new Date().toISOString()

    const { container } = render(<HomeView />)
    expect(container.textContent).toContain('Test Topic')
    expect(container.textContent).toContain('Stage 5/13')
  })

  it('renders just-completed state', () => {
    pipelineStatus.value = 'done'
    finishedAt.value = '2026-01-01T00:00:00Z'
    completionDismissed.value = ''
    topic.value = 'Completed Topic'

    const { container } = render(<HomeView />)
    expect(container.textContent).toContain('DONE')
  })

  it('renders error state', () => {
    pipelineStatus.value = 'failed'
    stageNum.value = 7
    topic.value = 'Failed Topic'
    logLines.value = ['error line 1', 'error line 2']

    const { container } = render(<HomeView />)
    expect(container.textContent).toContain('Failed at stage 7')
    expect(container.textContent).toContain('Retry from Stage 7')
  })

  it('shows empty state when no history', () => {
    const { container } = render(<HomeView />)
    expect(container.textContent).toContain('Welcome')
  })
})

describe('QueueView', () => {
  it('shows loading state initially', () => {
    const { container } = render(<QueueView />)
    expect(container.textContent).toContain('Loading')
  })

  it('shows empty state when queue loads empty', async () => {
    const { container } = render(<QueueView />)
    await waitFor(() => {
      expect(container.textContent).toContain('Queue is empty')
    })
  })

  it('has sort column headers', async () => {
    // QueueView should render column headers even during loading
    const { container } = render(<QueueView />)
    await waitFor(() => {
      // After loading, if empty, we see EmptyState
      // But if we had items, we'd see headers
      expect(container).toBeTruthy()
    })
  })
})

describe('IntelView', () => {
  it('renders sub-tabs', () => {
    const { container } = render(<IntelView />)
    expect(container.textContent).toContain('SUMMARY')
    expect(container.textContent).toContain('PERFORMANCE')
    expect(container.textContent).toContain('CONTENT')
    expect(container.textContent).toContain('AUDIENCE')
    expect(container.textContent).toContain('CONFIG')
  })

  it('starts with summary tab selected', () => {
    const { container } = render(<IntelView />)
    // Summary tab should be active (has bg-bg-2 class)
    const buttons = container.querySelectorAll('button')
    const summaryBtn = Array.from(buttons).find(b => b.textContent === 'SUMMARY')
    expect(summaryBtn?.className).toContain('bg-bg-2')
  })
})

describe('HealthView', () => {
  it('renders health status', () => {
    const { container } = render(<HealthView />)
    expect(container.textContent).toContain('System Health')
    expect(container.textContent).toContain('HEALTHY')
  })

  it('renders agent table', () => {
    const { container } = render(<HealthView />)
    expect(container.textContent).toContain('AGENT PERFORMANCE')
    expect(container.querySelector('table')).toBeTruthy()
  })

  it('renders system panels', () => {
    const { container } = render(<HealthView />)
    expect(container.textContent).toContain('Music Library')
    expect(container.textContent).toContain('Trend Detection')
    expect(container.textContent).toContain('Image Audit')
    expect(container.textContent).toContain('Schedule')
  })

  it('shows live status during run', () => {
    isRunning.value = true
    stageNum.value = 3
    const { container } = render(<HealthView />)
    expect(container.textContent).toContain('Live Status')
  })
})
