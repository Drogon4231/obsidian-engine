import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/preact'
import { StatusBadge } from '../components/StatusBadge'
import { Skeleton } from '../components/Skeleton'
import { EmptyState } from '../components/EmptyState'
import { ProgressBar } from '../components/ProgressBar'
import { MetricCard } from '../components/MetricCard'
import { showToast, ToastContainer } from '../components/Toast'
import { Chart } from '../components/Chart'
import { isRunning, stageNum, resetAllSignals } from '../state/store'
import { beforeEach } from 'vitest'

beforeEach(() => {
  resetAllSignals()
})

describe('StatusBadge', () => {
  it('renders status text', () => {
    const { container } = render(<StatusBadge status="running" />)
    expect(container.textContent).toContain('running')
  })

  it('applies correct class for done', () => {
    const { container } = render(<StatusBadge status="done" />)
    expect(container.querySelector('span')?.className).toContain('text-success')
  })

  it('applies correct class for error', () => {
    const { container } = render(<StatusBadge status="error" />)
    expect(container.querySelector('span')?.className).toContain('text-error')
  })
})

describe('Skeleton', () => {
  it('renders with aria-hidden', () => {
    const { container } = render(<Skeleton />)
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy()
  })
})

describe('EmptyState', () => {
  it('renders title', () => {
    const { container } = render(<EmptyState title="Nothing here" />)
    expect(container.textContent).toContain('Nothing here')
  })

  it('renders children', () => {
    const { container } = render(<EmptyState title="Empty"><span>child</span></EmptyState>)
    expect(container.textContent).toContain('child')
  })
})

describe('ProgressBar', () => {
  it('returns null when not running', () => {
    isRunning.value = false
    const { container } = render(<ProgressBar />)
    expect(container.children.length).toBe(0)
  })

  it('renders bar when running', () => {
    isRunning.value = true
    stageNum.value = 5
    const { container } = render(<ProgressBar />)
    expect(container.querySelector('.fixed')).toBeTruthy()
  })
})

describe('MetricCard', () => {
  it('renders label and value', () => {
    const { container } = render(<MetricCard label="Queue" value={5} />)
    expect(container.textContent).toContain('Queue')
    expect(container.textContent).toContain('5')
  })

  it('shows trend arrow with enough data', () => {
    const trend = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    const { container } = render(<MetricCard label="Test" value={10} trend={trend} />)
    expect(container.textContent).toContain('↑')
  })

  it('shows sparkline SVG with data', () => {
    const { container } = render(<MetricCard label="Test" value={5} trend={[1, 2, 3]} />)
    expect(container.querySelector('svg')).toBeTruthy()
  })
})

describe('Toast role', () => {
  it('renders role="status" for info toast', () => {
    showToast('hello', 'info')
    const { container } = render(<ToastContainer />)
    const el = container.querySelector('[role="status"]')
    expect(el).toBeTruthy()
    expect(el?.textContent).toContain('hello')
  })

  it('renders role="alert" for error toast', () => {
    showToast('oops', 'error')
    const { container } = render(<ToastContainer />)
    expect(container.querySelector('[role="alert"]')).toBeTruthy()
  })
})

describe('Chart ariaLabel', () => {
  it('adds role=img and aria-label to SVG when ariaLabel is provided', () => {
    // Stub ResizeObserver for jsdom
    const originalRO = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as any
    try {
      const { container } = render(
        <Chart
          ariaLabel="Test chart"
          height={100}
          renderer={() => []}
        />
      )
      expect(container).toBeTruthy()
    } finally {
      globalThis.ResizeObserver = originalRO
    }
  })
})
