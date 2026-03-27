import { useEffect } from 'preact/hooks'
import { currentView, quickTriggerOpen, logPanelOpen, slideAgent, shortcutHelpOpen } from './state/store'
import { connectSSE } from './state/sse'
import { startPulsePolling } from './state/api'
import { Header, MobileTabBar, switchView } from './components/Header'
import { ToastContainer } from './components/Toast'
import { ProgressBar } from './components/ProgressBar'
import { QuickTrigger } from './components/QuickTrigger'
import { SlidePanel } from './components/SlidePanel'
import { OnboardingOverlay } from './components/OnboardingOverlay'
import { ShortcutHelp } from './components/ShortcutHelp'
import { HomeView } from './views/HomeView'
import { QueueView } from './views/QueueView'
import { IntelView } from './views/IntelView'
import { HealthView } from './views/HealthView'
import { TuningView } from './views/TuningView'
import { SetupView } from './views/SetupView'
import { ErrorBoundary } from './components/ErrorBoundary'
import { toggleSound } from './utils/sound'
import { showToast } from './components/Toast'

const parseHash = () =>
  typeof location !== 'undefined' ? (location.hash.replace('#', '') || null) : null

export function App() {
  // Boot SSE + pulse polling
  useEffect(() => {
    connectSSE()
    startPulsePolling()
  }, [])

  // Hashchange listener — syncs browser back/forward
  useEffect(() => {
    const handler = () => {
      const newHash = parseHash() || 'home'
      if (currentView.value !== newHash) {
        currentView.value = newHash
      }
    }
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Suppress in inputs/textareas/contenteditable
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return
      // Don't intercept modified keys (Ctrl+1, Cmd+1, etc.)
      if (e.metaKey || e.ctrlKey || e.altKey) return

      switch (e.key) {
        case '1': switchView('home'); break
        case '2': switchView('queue'); break
        case '3': switchView('intel'); break
        case '4': switchView('health'); break
        case '5': switchView('tuning'); break
        case '6': switchView('setup'); break
        case 't':
        case 'T':
          quickTriggerOpen.value = true
          break
        case 'l':
        case 'L':
          logPanelOpen.value = !logPanelOpen.value
          break
        case 's':
        case 'S': {
          const on = toggleSound()
          showToast(on ? 'Sound on' : 'Sound off')
          break
        }
        case '?':
          shortcutHelpOpen.value = !shortcutHelpOpen.value
          break
        case 'Escape':
          if (shortcutHelpOpen.value) shortcutHelpOpen.value = false
          else if (quickTriggerOpen.value) quickTriggerOpen.value = false
          else if (slideAgent.value != null) slideAgent.value = null
          break
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const view = currentView.value

  return (
    <div class="min-h-screen flex flex-col">
      <Header />
      <main id="main" role="tabpanel" class="flex-1 flex flex-col">
        <ErrorBoundary>
          {view === 'home' && <HomeView />}
          {view === 'queue' && <QueueView />}
          {view === 'intel' && <IntelView />}
          {view === 'health' && <HealthView />}
          {view === 'tuning' && <TuningView />}
          {view === 'setup' && <SetupView />}
        </ErrorBoundary>
      </main>
      <ProgressBar />
      <QuickTrigger />
      <SlidePanel />
      <MobileTabBar />
      <ToastContainer />
      <OnboardingOverlay />
      <ShortcutHelp />
    </div>
  )
}
