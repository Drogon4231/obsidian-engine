import { useRef, useState, useEffect } from 'preact/hooks'
import { quickTriggerOpen } from '../state/store'
import { triggerPipeline } from '../state/api'
import { showToast } from './Toast'

export function QuickTrigger() {
  if (!quickTriggerOpen.value) return null

  const inputRef = useRef<HTMLInputElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState(false)
  const prevFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    prevFocusRef.current = document.activeElement as HTMLElement
    inputRef.current?.focus()
  }, [])

  // Focus trap + escape + restore
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        prevFocusRef.current?.focus()
        quickTriggerOpen.value = false
        return
      }
      if (e.key === 'Tab' && overlayRef.current) {
        const focusable = overlayRef.current.querySelectorAll<HTMLElement>(
          'button, input, [tabindex], a[href], select, textarea'
        )
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
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const close = () => {
    prevFocusRef.current?.focus()
    quickTriggerOpen.value = false
  }

  const fire = async () => {
    if (loading || !value.trim()) return
    setLoading(true)
    try {
      await triggerPipeline(value.trim())
      setFlash(true)
      setTimeout(() => {
        close()
        showToast(`Fired: ${value.trim()}`)
        setFlash(false)
      }, 500)
    } catch (err: any) {
      if (err?.message?.includes('409')) {
        showToast('Pipeline already running', 'error')
      } else {
        showToast('Failed to trigger pipeline', 'error')
      }
      setLoading(false)
    }
  }

  return (
    <div
      ref={overlayRef}
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <div class={`w-[420px] max-w-[90vw] p-6 bg-bg-1 border rounded
        ${flash ? 'border-success' : 'border-border'} transition-colors`}>
        <div class="text-bright text-sm font-bold mb-3 tracking-wider">QUICK FIRE</div>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onInput={(e) => setValue((e.target as HTMLInputElement).value)}
          onKeyDown={(e) => { if (e.key === 'Enter') fire() }}
          disabled={loading}
          placeholder="Enter topic..."
          class="w-full bg-bg-2 border border-border text-bright px-3 py-2 rounded text-sm
                 font-mono outline-none focus:border-running disabled:opacity-50"
        />
        <div class="flex justify-end gap-2 mt-3">
          <button
            onClick={close}
            class="text-dim text-xs hover:text-text"
          >
            Cancel
          </button>
          <button
            onClick={fire}
            disabled={loading || !value.trim()}
            class="px-3 py-1.5 text-xs font-bold bg-running/20 text-running border border-running/30
                   rounded hover:bg-running/30 disabled:opacity-50"
          >
            {loading ? 'Firing...' : 'FIRE'}
          </button>
        </div>
      </div>
    </div>
  )
}
