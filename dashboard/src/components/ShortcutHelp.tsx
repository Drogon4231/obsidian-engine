import { shortcutHelpOpen } from '../state/store'

const SHORTCUTS = [
  { key: '1', desc: 'Home view' },
  { key: '2', desc: 'Queue view' },
  { key: '3', desc: 'Intel view' },
  { key: '4', desc: 'Health view' },
  { key: '5', desc: 'Tuning view' },
  { key: 'T', desc: 'Quick-fire topic' },
  { key: 'L', desc: 'Toggle log panel' },
  { key: 'S', desc: 'Toggle sound' },
  { key: '?', desc: 'This help overlay' },
  { key: 'Esc', desc: 'Close overlay / panel' },
]

export function ShortcutHelp() {
  if (!shortcutHelpOpen.value) return null

  return (
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={(e) => {
        if (e.target === e.currentTarget) shortcutHelpOpen.value = false
      }}
    >
      <div class="w-[340px] max-w-[90vw] backdrop-blur-md bg-bg-1/95 border border-border rounded-lg p-5">
        <div class="text-bright font-bold text-sm mb-4 tracking-wider">KEYBOARD SHORTCUTS</div>
        <div class="space-y-2">
          {SHORTCUTS.map(s => (
            <div key={s.key} class="flex items-center gap-3 text-xs">
              <kbd class="bg-bg-2 border border-border rounded px-2 py-0.5 text-bright font-mono min-w-[32px] text-center">
                {s.key}
              </kbd>
              <span class="text-text">{s.desc}</span>
            </div>
          ))}
        </div>
        <button
          onClick={() => { shortcutHelpOpen.value = false }}
          class="mt-4 text-dim text-xs hover:text-text"
        >
          Close
        </button>
      </div>
    </div>
  )
}
