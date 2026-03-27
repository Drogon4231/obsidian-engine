import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/preact'
import { renderBars } from '../components/renderers/BarRenderer'
import { renderHBars } from '../components/renderers/HBarRenderer'
import { renderLine } from '../components/renderers/LineRenderer'
import { renderSpark } from '../components/renderers/SparkRenderer'
import { renderStacked } from '../components/renderers/StackedRenderer'

const noop = () => {}

describe('BarRenderer', () => {
  it('returns empty array for empty data', () => {
    expect(renderBars([], 400, 200, noop)).toEqual([])
  })

  it('returns VNodes for valid data', () => {
    const result = renderBars(
      [{ label: 'A', value: 10 }, { label: 'B', value: 20 }],
      400, 200, noop
    )
    expect(result.length).toBeGreaterThan(0)
  })

  it('renders inside SVG correctly', () => {
    const { container } = render(
      <svg>
        {renderBars(
          [{ label: 'A', value: 10 }, { label: 'B', value: 5 }],
          400, 200, noop
        )}
      </svg>
    )
    expect(container.querySelectorAll('rect').length).toBeGreaterThan(0)
  })
})

describe('HBarRenderer', () => {
  it('returns empty array for empty data', () => {
    expect(renderHBars([], 400, 200, noop)).toEqual([])
  })

  it('renders horizontal bars', () => {
    const { container } = render(
      <svg>
        {renderHBars(
          [{ label: 'Tag1', value: 30 }, { label: 'Tag2', value: 15 }],
          400, 200, noop
        )}
      </svg>
    )
    expect(container.querySelectorAll('rect').length).toBe(2)
  })
})

describe('LineRenderer', () => {
  it('returns empty array for single point', () => {
    expect(renderLine([{ label: 'A', value: 10 }], 400, 200, noop)).toEqual([])
  })

  it('renders line + area + dots', () => {
    const { container } = render(
      <svg>
        {renderLine(
          [{ label: 'Jan', value: 10 }, { label: 'Feb', value: 20 }, { label: 'Mar', value: 15 }],
          400, 200, noop
        )}
      </svg>
    )
    expect(container.querySelectorAll('path').length).toBeGreaterThanOrEqual(2) // line + area
    expect(container.querySelectorAll('circle').length).toBe(3)
  })
})

describe('SparkRenderer', () => {
  it('returns empty array for single value', () => {
    expect(renderSpark([5], 80, 16)).toEqual([])
  })

  it('renders path for multiple values', () => {
    const { container } = render(
      <svg>{renderSpark([1, 3, 2, 5, 4], 80, 16)}</svg>
    )
    expect(container.querySelector('path')).toBeTruthy()
  })
})

describe('StackedRenderer', () => {
  it('returns empty array for empty data', () => {
    expect(renderStacked([], 400, 200, noop)).toEqual([])
  })

  it('renders stacked segments', () => {
    const { container } = render(
      <svg>
        {renderStacked(
          [{
            label: 'Q1',
            segments: [
              { key: 'A', value: 10, color: 'red' },
              { key: 'B', value: 20, color: 'blue' },
            ],
          }],
          400, 200, noop
        )}
      </svg>
    )
    expect(container.querySelectorAll('rect').length).toBe(2)
  })
})
