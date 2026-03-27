import { useRef, useState, useEffect } from 'preact/hooks'
import type { VNode } from 'preact'

interface TooltipData {
  x: number
  y: number
  label: string
  value: string
}

interface ChartProps {
  renderer: (width: number, height: number, onHover: (d: TooltipData | null) => void) => VNode[]
  height?: number
  class?: string
  ariaLabel?: string
}

export function Chart({ renderer, height = 200, class: cls = '', ariaLabel }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dims, setDims] = useState({ width: 0, height })
  const [tooltip, setTooltip] = useState<TooltipData | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    let timer: ReturnType<typeof setTimeout>
    const ro = new ResizeObserver((entries) => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        const entry = entries[0]
        if (entry) {
          setDims({ width: entry.contentRect.width, height })
        }
      }, 150)
    })
    ro.observe(el)
    return () => { clearTimeout(timer); ro.disconnect() }
  }, [height])

  return (
    <div ref={containerRef} class={`relative ${cls}`} style={{ minHeight: `${height}px` }}>
      {dims.width > 0 && (
        <svg width={dims.width} height={dims.height} class="overflow-visible"
          {...(ariaLabel ? { role: 'img', 'aria-label': ariaLabel } : {})}>
          {renderer(dims.width, dims.height, setTooltip)}
        </svg>
      )}
      {tooltip && (
        <div
          class="absolute z-10 bg-bg-2 border border-border rounded px-2 py-1 text-[11px] text-bright pointer-events-none"
          style={{
            left: `${Math.min(tooltip.x, dims.width - 120)}px`,
            top: `${Math.max(tooltip.y - 40, 0)}px`,
          }}
        >
          <div class="text-dim">{tooltip.label}</div>
          <div class="font-bold">{tooltip.value}</div>
        </div>
      )}
    </div>
  )
}
