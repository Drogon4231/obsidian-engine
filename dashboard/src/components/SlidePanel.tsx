import { useEffect, useRef } from 'preact/hooks'
import { slideAgent } from '../state/store'
import { AGENTS, AGENT_COLORS } from '../data/agents'

export function SlidePanel() {
  const num = slideAgent.value
  const panelRef = useRef<HTMLDivElement>(null)

  // Focus trap + Escape close
  useEffect(() => {
    if (num == null) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        slideAgent.value = null
      }
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>('button, [tabindex], a[href], input, select, textarea')
        if (focusable.length === 0) return
        const first = focusable[0]!
        const last = focusable[focusable.length - 1]!
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handler)
    panelRef.current?.querySelector<HTMLElement>('button')?.focus()
    return () => document.removeEventListener('keydown', handler)
  }, [num])

  if (num == null) return null

  const agent = AGENTS.find(a => a.num === num)
  if (!agent) return null

  const color = AGENT_COLORS[agent.num] ?? 'var(--color-running)'
  const isWriting = agent.num <= 4
  const isMedia = agent.num >= 7 && agent.num <= 10
  const isDelivery = agent.num >= 11

  return (
    <div class="fixed inset-0 z-40 flex justify-end" onClick={() => { slideAgent.value = null }}>
      <div class="absolute inset-0 bg-black/40" />
      <div
        ref={panelRef}
        class="relative w-80 bg-bg-1 border-l border-border h-full overflow-y-auto p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => { slideAgent.value = null }}
          class="absolute top-3 right-3 text-dim hover:text-bright"
          aria-label="Close panel"
        >
          ×
        </button>

        {/* Agent header */}
        <div class="mb-4">
          <div class="text-[10px] text-dim tracking-wider">STAGE {agent.num}</div>
          <div class="text-xl font-bold" style={{ color }}>{agent.codename}</div>
          <div class="text-sm text-text mt-1">{agent.name}</div>
        </div>

        {/* Type badge */}
        <div class="flex gap-2 mb-4">
          <span class={`text-[10px] px-2 py-0.5 rounded border ${
            isWriting ? 'border-cyan-500/30 text-cyan-400' :
            isMedia ? 'border-purple-500/30 text-purple-400' :
            isDelivery ? 'border-green-500/30 text-green-400' :
            'border-warning/30 text-warning'
          }`}>
            {isWriting ? 'WRITING' : isMedia ? 'MEDIA' : isDelivery ? 'DELIVERY' : 'VERIFY'}
          </span>
          {(agent.num === 8 || agent.num === 9) && (
            <span class="text-[10px] px-2 py-0.5 rounded border border-running/30 text-running">PARALLEL</span>
          )}
        </div>

        {/* Preview hint based on stage type */}
        <div class="backdrop-blur-sm bg-bg-2 border border-border rounded p-3 text-xs text-dim">
          {isWriting && <div>Text stage — generates script, research, or analysis content</div>}
          {agent.num === 5 && <div>Verification — validates scoring config and content quality</div>}
          {agent.num === 6 && <div>Planning — determines visual and narrative structure</div>}
          {isMedia && <div>Media stage — produces audio, images, or video assets</div>}
          {isDelivery && <div>Delivery — renders, uploads, or finalizes output</div>}
        </div>
      </div>
    </div>
  )
}
