import {
  currentView, isRunning, analyticsRunning, activeJobs, liveCostUsd, healthStatus, sseConnected,
} from '../state/store'
import { killPipeline } from '../state/api'
import { toggleSound, isSoundEnabled } from '../utils/sound'
import { showToast } from './Toast'

const VIEWS = [
  { id: 'home', label: 'HOME', key: '1' },
  { id: 'queue', label: 'QUEUE', key: '2' },
  { id: 'intel', label: 'INTEL', key: '3' },
  { id: 'health', label: 'HEALTH', key: '4' },
  { id: 'tuning', label: 'TUNING', key: '5' },
  { id: 'setup', label: 'SETUP', key: '6' },
] as const

function switchView(id: string) {
  if (typeof document !== 'undefined' && 'startViewTransition' in document) {
    (document as any).startViewTransition(() => {
      location.hash = id
      currentView.value = id
    })
  } else {
    location.hash = id
    currentView.value = id
  }
  try {
    localStorage.setItem('obsidian-view', id)
  } catch {
    // no-op
  }
}

export function MobileTabBar() {
  return (
    <nav class="mobile-tab-bar" role="tablist">
      {VIEWS.map(v => (
        <button
          key={v.id}
          role="tab"
          aria-selected={currentView.value === v.id}
          onClick={() => switchView(v.id)}
          class={currentView.value === v.id ? 'active' : ''}
        >
          {v.label}
        </button>
      ))}
    </nav>
  )
}

export function Header() {
  const pulseColor = isRunning.value
    ? 'bg-running'
    : healthStatus.value === 'healthy'
      ? 'bg-success'
      : healthStatus.value === 'degraded'
        ? 'bg-warning'
        : 'bg-error'

  return (
    <header class="border-b border-border px-4 py-3 flex items-center gap-4">
      {/* Brand */}
      <div class="flex items-center gap-3 mr-4">
        <div
          class={`w-2.5 h-2.5 rounded-full ${pulseColor}`}
          style={isRunning.value ? { animation: 'borderPulse 1.5s ease-in-out infinite' } : {}}
        />
        <span class="text-bright font-bold text-sm tracking-[4px]">OBSIDIAN</span>
        <span class="text-dim text-[9px] tracking-[2px] hidden sm:inline">AUTOMATED DOCUMENTARY PIPELINE</span>
        {!sseConnected.value && (
          <span class="text-warning text-[10px] tracking-wider animate-pulse">RECONNECTING</span>
        )}
      </div>

      {/* Nav tabs (hidden on mobile) */}
      <nav role="tablist" class="flex gap-1 desktop-nav">
        {VIEWS.map(v => (
          <button
            key={v.id}
            role="tab"
            aria-selected={currentView.value === v.id}
            onClick={() => switchView(v.id)}
            class={`px-3 py-1.5 text-xs tracking-wider transition-colors rounded
              ${currentView.value === v.id
                ? 'bg-bg-2 text-bright border border-border'
                : 'text-dim hover:text-text'}`}
          >
            {v.label}
          </button>
        ))}
      </nav>

      <div class="flex-1" />

      {/* Live cost during runs */}
      {isRunning.value && liveCostUsd.value !== null && (
        <span class="text-running text-xs font-bold" aria-live="polite">
          ${liveCostUsd.value.toFixed(2)}
        </span>
      )}

      {/* Active background job badges */}
      {Object.keys(activeJobs.value).length > 0 ? (
        <div class="flex gap-1.5">
          {Object.keys(activeJobs.value).map(job => (
            <span key={job} class="text-warning text-[10px] tracking-wider animate-pulse uppercase">
              {job.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      ) : analyticsRunning.value && (
        <span class="text-warning text-xs animate-pulse">ANALYTICS</span>
      )}

      {/* Kill button */}
      {isRunning.value && (
        <button
          onClick={async () => {
            try {
              await killPipeline()
              showToast('Pipeline killed')
            } catch {
              showToast('Failed to kill pipeline', 'error')
            }
          }}
          class="px-2 py-1 text-xs text-error border border-error/30 rounded hover:bg-error/10"
          aria-label="Kill pipeline"
        >
          KILL
        </button>
      )}

      {/* Sound toggle */}
      <button
        onClick={() => {
          const on = toggleSound()
          showToast(on ? 'Sound on' : 'Sound off')
        }}
        class="text-dim hover:text-bright text-xs"
        aria-label="Toggle sound"
      >
        {isSoundEnabled() ? '🔊' : '🔇'}
      </button>
    </header>
  )
}

// Export for keyboard shortcut handler
export { switchView }
