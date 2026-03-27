import { signal } from '@preact/signals'

interface ToastItem {
  id: number
  message: string
  type: 'info' | 'error'
}

const toasts = signal<ToastItem[]>([])
let nextId = 0

export function showToast(message: string, type: 'info' | 'error' = 'info') {
  const id = nextId++
  // Max 3 visible — remove oldest if needed
  const current = toasts.value.length >= 3
    ? toasts.value.slice(1)
    : toasts.value
  toasts.value = [...current, { id, message, type }]

  if (type === 'info') {
    setTimeout(() => dismissToast(id), 4000)
  }
}

function dismissToast(id: number) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

export function ToastContainer() {
  return (
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2" style={{ maxWidth: '360px' }}>
      {toasts.value.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={() => dismissToast(t.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const bg = toast.type === 'error' ? 'bg-error/90' : 'bg-bg-2/95 border border-border'
  const text = toast.type === 'error' ? 'text-white' : 'text-text'

  return (
    <div role={toast.type === 'error' ? 'alert' : 'status'} class={`${bg} ${text} px-4 py-3 rounded text-sm flex items-center gap-2`}>
      <span class="flex-1">{toast.message}</span>
      <button
        onClick={onDismiss}
        class="text-dim hover:text-bright ml-2"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}
