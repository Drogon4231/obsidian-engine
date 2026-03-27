import type { VNode } from 'preact'

export function renderSpark(
  values: number[],
  width: number,
  height: number,
  color = 'var(--color-running)'
): VNode[] {
  if (values.length < 2) return []
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1

  const points = values.map((v, i) => ({
    x: (i / (values.length - 1)) * width,
    y: height - ((v - min) / range) * height,
  }))

  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

  return [
    <path key="line" d={d} fill="none" stroke={color} stroke-width={1.5} opacity={0.6} />,
  ]
}
