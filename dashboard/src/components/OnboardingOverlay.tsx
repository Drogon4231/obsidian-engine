import { useState, useEffect } from 'preact/hooks'

const STEPS = [
  {
    title: 'Welcome to The Obsidian Archive',
    desc: 'Automated dark history documentaries — 13 AI agents, one pipeline, zero manual work.',
  },
  {
    title: 'Queue',
    desc: 'Browse and manage topics. Score-ranked by trend strength, audience demand, and era gaps.',
  },
  {
    title: 'Real-Time Pipeline',
    desc: 'Watch 13 AI agents research, write, verify, generate media, and render your video live.',
  },
  {
    title: 'YouTube-Ready Output',
    desc: 'Get a fully rendered documentary with SEO metadata, analytics, and automated upload.',
  },
]

export function OnboardingOverlay() {
  const [step, setStep] = useState(0)
  const [show, setShow] = useState(false)

  useEffect(() => {
    try {
      if (!localStorage.getItem('obsidian-onboarded')) {
        setShow(true)
      }
    } catch {
      // no localStorage
    }
  }, [])

  if (!show) return null

  const dismiss = () => {
    setShow(false)
    try { localStorage.setItem('obsidian-onboarded', 'true') } catch {}
  }

  const current = STEPS[step]!
  const isLast = step === STEPS.length - 1

  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div class="w-[400px] max-w-[90vw] backdrop-blur-md bg-bg-1/95 border border-border rounded-lg p-6">
        <div class="text-[10px] text-dim tracking-wider mb-1">
          {step + 1} / {STEPS.length}
        </div>
        <div class="text-bright font-bold text-sm mb-2">{current.title}</div>
        <div class="text-text text-xs leading-relaxed mb-6">{current.desc}</div>
        <div class="flex justify-between items-center">
          <button
            onClick={dismiss}
            class="text-dim text-xs hover:text-text"
          >
            Skip
          </button>
          <button
            onClick={() => isLast ? dismiss() : setStep(s => s + 1)}
            class="px-4 py-1.5 text-xs font-bold bg-running/20 text-running border border-running/30 rounded hover:bg-running/30"
          >
            {isLast ? 'Got it' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  )
}
