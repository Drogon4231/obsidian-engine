import { signal } from '@preact/signals'
import { useEffect } from 'preact/hooks'
import type { SetupStatus, SetupKeyStatus } from '../types'
import { fetchSetupStatus, validateSetupKey, saveSetupConfig } from '../state/api'
import { showToast } from '../components/Toast'

// ── Local state ──────────────────────────────────────────────────────────────

const setupStep = signal(0)
const setupData = signal<SetupStatus | null>(null)
const loading = signal(true)
const saving = signal(false)

// Key values being edited (not yet saved)
const keyDraft = signal<Record<string, string>>({})
const keyValidation = signal<Record<string, 'idle' | 'checking' | 'valid' | 'invalid'>>({})

// Profile + provider selections
const selectedProfile = signal('')
const selectedProviders = signal<Record<string, string>>({})

const STEPS = ['Welcome', 'API Keys', 'Profile', 'Providers', 'Review']

const CATEGORY_ORDER = ['llm', 'tts', 'images', 'footage', 'music', 'database', 'notifications']
const CATEGORY_LABELS: Record<string, string> = {
  llm: 'AI Text Generation',
  tts: 'Text-to-Speech',
  images: 'Image Generation',
  footage: 'Stock Footage',
  music: 'Background Music',
  database: 'Database',
  notifications: 'Notifications',
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Anthropic (Claude)',
  openai: 'OpenAI (GPT)',
  elevenlabs: 'ElevenLabs',
  fal: 'fal.ai (Recraft / Flux)',
  pexels: 'Pexels (Free)',
  local: 'Save to Disk',
  epidemic_sound: 'Epidemic Sound',
  local_music: 'Local Library (Kevin MacLeod)',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function groupKeys(keys: SetupKeyStatus[]): Map<string, SetupKeyStatus[]> {
  const grouped = new Map<string, SetupKeyStatus[]>()
  for (const cat of CATEGORY_ORDER) {
    const items = keys.filter(k => k.category === cat)
    if (items.length > 0) grouped.set(cat, items)
  }
  return grouped
}

async function handleValidate(key: string) {
  const val = keyDraft.value[key]
  if (!val?.trim()) return

  keyValidation.value = { ...keyValidation.value, [key]: 'checking' }
  try {
    const result = await validateSetupKey(key, val)
    keyValidation.value = {
      ...keyValidation.value,
      [key]: result.valid ? 'valid' : 'invalid',
    }
    if (!result.valid && result.error) {
      showToast(result.error, 'error')
    }
  } catch {
    keyValidation.value = { ...keyValidation.value, [key]: 'invalid' }
  }
}

async function handleSave() {
  saving.value = true
  try {
    // Collect non-empty keys
    const keysToSave: Record<string, string> = {}
    for (const [k, v] of Object.entries(keyDraft.value)) {
      if (v?.trim()) keysToSave[k] = v.trim()
    }

    const result = await saveSetupConfig({
      keys: Object.keys(keysToSave).length > 0 ? keysToSave : undefined,
      profile: selectedProfile.value || undefined,
      providers: Object.keys(selectedProviders.value).length > 0
        ? selectedProviders.value : undefined,
    })

    if (result.success) {
      showToast('Configuration saved!')
      // Refresh status
      const status = await fetchSetupStatus()
      setupData.value = status
    } else {
      showToast(result.errors.join(', '), 'error')
    }
  } catch (e) {
    showToast('Failed to save configuration', 'error')
  } finally {
    saving.value = false
  }
}

// ── Step Components ──────────────────────────────────────────────────────────

function WelcomeStep() {
  return (
    <div class="space-y-6">
      <div class="text-center space-y-4">
        <h2 class="text-2xl font-bold text-bright">Welcome to Obsidian Engine</h2>
        <p class="text-text text-base max-w-xl mx-auto leading-relaxed">
          This wizard will help you configure everything needed to generate
          AI-powered videos. It takes about 5 minutes.
        </p>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl mx-auto mt-8">
        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-sm font-bold mb-1">Step 1</div>
          <div class="text-bright text-sm">API Keys</div>
          <div class="text-dim text-xs mt-1">Connect your AI services</div>
        </div>
        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-sm font-bold mb-1">Step 2</div>
          <div class="text-bright text-sm">Content Profile</div>
          <div class="text-dim text-xs mt-1">Choose your video style</div>
        </div>
        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-sm font-bold mb-1">Step 3</div>
          <div class="text-bright text-sm">Providers</div>
          <div class="text-dim text-xs mt-1">Select your service backends</div>
        </div>
        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-sm font-bold mb-1">Step 4</div>
          <div class="text-bright text-sm">Review & Save</div>
          <div class="text-dim text-xs mt-1">Verify and launch</div>
        </div>
      </div>

      {setupData.value?.setup_complete && (
        <div class="bg-success/10 border border-success/30 rounded-lg p-4 max-w-xl mx-auto mt-6 text-center">
          <span class="text-success text-sm font-bold">
            Setup is already complete! You can review or update your configuration.
          </span>
        </div>
      )}
    </div>
  )
}

function ApiKeysStep() {
  const data = setupData.value
  if (!data) return null

  const grouped = groupKeys(data.keys)

  return (
    <div class="space-y-6 max-w-2xl mx-auto">
      <div class="text-center mb-4">
        <h2 class="text-xl font-bold text-bright">API Keys</h2>
        <p class="text-dim text-sm mt-1">
          Enter your API keys below. Required keys are marked with a star.
        </p>
      </div>

      {Array.from(grouped.entries()).map(([category, keys]) => (
        <div key={category} class="space-y-3">
          <h3 class="text-sm font-bold text-accent tracking-wider uppercase">
            {CATEGORY_LABELS[category] || category}
            {keys.every(k => !k.required) && (
              <span class="text-dim font-normal ml-2">(optional)</span>
            )}
          </h3>

          {keys.map(keyInfo => {
            const status = keyValidation.value[keyInfo.key] || 'idle'
            const isConfigured = keyInfo.configured && !keyDraft.value[keyInfo.key]
            const borderColor =
              status === 'valid' || isConfigured ? 'border-success/50' :
              status === 'invalid' ? 'border-error/50' :
              status === 'checking' ? 'border-warning/50' :
              'border-border'

            return (
              <div key={keyInfo.key} class="space-y-1">
                <label class="flex items-center gap-2 text-sm text-text">
                  <span>{keyInfo.label}</span>
                  {keyInfo.required && <span class="text-warning text-xs">*</span>}
                  {isConfigured && (
                    <span class="text-success text-xs font-bold">CONFIGURED</span>
                  )}
                  <a
                    href={keyInfo.help}
                    target="_blank"
                    rel="noopener"
                    class="text-accent text-xs hover:underline ml-auto"
                  >
                    Get key
                  </a>
                </label>
                <div class="flex gap-2">
                  <input
                    type="password"
                    placeholder={isConfigured ? '(already set — enter new value to replace)' : `Enter ${keyInfo.label} key`}
                    value={keyDraft.value[keyInfo.key] || ''}
                    onInput={(e) => {
                      keyDraft.value = {
                        ...keyDraft.value,
                        [keyInfo.key]: (e.target as HTMLInputElement).value,
                      }
                      // Reset validation on change
                      if (keyValidation.value[keyInfo.key]) {
                        keyValidation.value = {
                          ...keyValidation.value,
                          [keyInfo.key]: 'idle',
                        }
                      }
                    }}
                    class={`flex-1 bg-bg-1 border ${borderColor} rounded px-3 py-2 text-sm text-text
                      focus:outline-none focus:border-accent transition-colors font-mono`}
                  />
                  <button
                    onClick={() => handleValidate(keyInfo.key)}
                    disabled={!keyDraft.value[keyInfo.key]?.trim() || status === 'checking'}
                    class="px-3 py-2 text-xs bg-bg-2 border border-border rounded
                      hover:border-accent disabled:opacity-30 disabled:cursor-not-allowed
                      transition-colors text-text"
                  >
                    {status === 'checking' ? 'Checking...' :
                     status === 'valid' ? 'Valid' :
                     status === 'invalid' ? 'Retry' : 'Test'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

function ProfileStep() {
  const data = setupData.value
  if (!data) return null

  return (
    <div class="space-y-6 max-w-2xl mx-auto">
      <div class="text-center mb-4">
        <h2 class="text-xl font-bold text-bright">Content Profile</h2>
        <p class="text-dim text-sm mt-1">
          Profiles control the tone, structure, and visual style of your videos.
        </p>
      </div>

      <div class="grid gap-3">
        {data.available_profiles.map(p => {
          const active = (selectedProfile.value || data.profile) === p.name
          return (
            <button
              key={p.name}
              onClick={() => { selectedProfile.value = p.name }}
              class={`text-left p-4 rounded-lg border transition-all ${
                active
                  ? 'border-accent bg-accent/10 ring-1 ring-accent/30'
                  : 'border-border bg-bg-2 hover:border-dim'
              }`}
            >
              <div class="flex items-center gap-3">
                <div class={`w-3 h-3 rounded-full border-2 ${
                  active ? 'border-accent bg-accent' : 'border-dim'
                }`} />
                <div>
                  <div class="text-bright font-bold text-sm capitalize">{p.name.replace(/_/g, ' ')}</div>
                  {p.description && (
                    <div class="text-dim text-xs mt-0.5">{p.description}</div>
                  )}
                </div>
                {active && data.profile === p.name && (
                  <span class="ml-auto text-accent text-xs">current</span>
                )}
              </div>
            </button>
          )
        })}
      </div>

      <div class="bg-bg-2 border border-border rounded-lg p-4 mt-4">
        <div class="text-dim text-xs">
          You can create custom profiles by adding a YAML file to the <code class="text-accent">profiles/</code> directory.
          See <code class="text-accent">profiles/_template.yaml</code> for the format.
        </div>
      </div>
    </div>
  )
}

function ProvidersStep() {
  const data = setupData.value
  if (!data) return null

  const providerTypes = ['llm', 'tts', 'images', 'footage', 'upload'] as const
  const providerDescriptions: Record<string, string> = {
    llm: 'AI model for script writing, research, and analysis',
    tts: 'Voice synthesis for narration',
    images: 'AI-generated images for visual scenes',
    footage: 'Stock video clips for b-roll',
    upload: 'Where to publish the final video',
  }

  return (
    <div class="space-y-6 max-w-2xl mx-auto">
      <div class="text-center mb-4">
        <h2 class="text-xl font-bold text-bright">Service Providers</h2>
        <p class="text-dim text-sm mt-1">
          Choose which service to use for each capability. Defaults work great for most users.
        </p>
      </div>

      <div class="space-y-4">
        {providerTypes.map(ptype => {
          const options = data.available_providers[ptype] || []
          const current = selectedProviders.value[ptype] || data.providers[ptype] || ''

          return (
            <div key={ptype} class="bg-bg-2 border border-border rounded-lg p-4">
              <div class="flex items-center justify-between mb-2">
                <div>
                  <div class="text-bright text-sm font-bold capitalize">{ptype === 'llm' ? 'LLM' : ptype}</div>
                  <div class="text-dim text-xs">{providerDescriptions[ptype]}</div>
                </div>
              </div>
              <div class="flex gap-2 flex-wrap">
                {options.map(opt => {
                  const active = current === opt
                  return (
                    <button
                      key={opt}
                      onClick={() => {
                        selectedProviders.value = {
                          ...selectedProviders.value,
                          [ptype]: opt,
                        }
                      }}
                      class={`px-3 py-1.5 text-xs rounded border transition-all ${
                        active
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-border text-dim hover:text-text hover:border-dim'
                      }`}
                    >
                      {PROVIDER_LABELS[opt] || opt}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ReviewStep() {
  const data = setupData.value
  if (!data) return null

  const missingRequired = data.keys.filter(k => k.required && !k.configured && !keyDraft.value[k.key]?.trim())
  const profile = selectedProfile.value || data.profile

  return (
    <div class="space-y-6 max-w-2xl mx-auto">
      <div class="text-center mb-4">
        <h2 class="text-xl font-bold text-bright">Review Configuration</h2>
        <p class="text-dim text-sm mt-1">
          Verify your settings and save.
        </p>
      </div>

      {missingRequired.length > 0 && (
        <div class="bg-error/10 border border-error/30 rounded-lg p-4">
          <div class="text-error text-sm font-bold mb-1">Missing Required Keys</div>
          <ul class="text-error/80 text-xs space-y-1">
            {missingRequired.map(k => (
              <li key={k.key}>
                {k.label} —{' '}
                <a href={k.help} target="_blank" rel="noopener" class="underline">
                  Get key
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div class="space-y-3">
        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-xs font-bold mb-2 tracking-wider">API KEYS</div>
          <div class="space-y-1">
            {data.keys.map(k => {
              const hasNew = !!keyDraft.value[k.key]?.trim()
              return (
                <div key={k.key} class="flex items-center justify-between text-xs">
                  <span class="text-text">{k.label}</span>
                  <span class={
                    hasNew ? 'text-warning' :
                    k.configured ? 'text-success' :
                    k.required ? 'text-error' : 'text-dim'
                  }>
                    {hasNew ? 'NEW' : k.configured ? 'SET' : k.required ? 'MISSING' : 'NOT SET'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-xs font-bold mb-2 tracking-wider">PROFILE</div>
          <div class="text-bright text-sm capitalize">{profile.replace(/_/g, ' ')}</div>
        </div>

        <div class="bg-bg-2 border border-border rounded-lg p-4">
          <div class="text-accent text-xs font-bold mb-2 tracking-wider">PROVIDERS</div>
          <div class="space-y-1">
            {['llm', 'tts', 'images', 'footage', 'upload'].map(ptype => {
              const provider = selectedProviders.value[ptype] || data.providers[ptype] || '(default)'
              return (
                <div key={ptype} class="flex items-center justify-between text-xs">
                  <span class="text-text capitalize">{ptype === 'llm' ? 'LLM' : ptype}</span>
                  <span class="text-bright">{PROVIDER_LABELS[provider] || provider}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving.value}
        class="w-full py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-bold
          text-sm tracking-wider rounded-lg hover:from-purple-500 hover:to-indigo-500
          disabled:opacity-50 transition-all"
      >
        {saving.value ? 'SAVING...' : 'SAVE CONFIGURATION'}
      </button>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

export function SetupView() {
  useEffect(() => {
    loading.value = true
    fetchSetupStatus()
      .then(data => {
        setupData.value = data
        selectedProfile.value = data.profile
        selectedProviders.value = { ...data.providers }
      })
      .catch(() => showToast('Failed to load setup status', 'error'))
      .finally(() => { loading.value = false })
  }, [])

  if (loading.value) {
    return (
      <div class="flex-1 flex items-center justify-center">
        <div class="text-dim text-sm animate-pulse">Loading setup...</div>
      </div>
    )
  }

  const step = setupStep.value

  return (
    <div class="flex-1 flex flex-col p-4 sm:p-6 max-w-4xl mx-auto w-full">
      {/* Step indicator */}
      <div class="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
        {STEPS.map((label, i) => (
          <div key={i} class="flex items-center">
            <button
              onClick={() => { setupStep.value = i }}
              class={`flex items-center gap-2 px-3 py-1.5 rounded text-xs whitespace-nowrap transition-all ${
                i === step
                  ? 'bg-accent/10 text-accent border border-accent/30'
                  : i < step
                    ? 'text-success hover:text-bright'
                    : 'text-dim hover:text-text'
              }`}
            >
              <span class={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                i === step
                  ? 'bg-accent text-black'
                  : i < step
                    ? 'bg-success/20 text-success'
                    : 'bg-bg-2 text-dim'
              }`}>
                {i < step ? '\u2713' : i + 1}
              </span>
              <span class="hidden sm:inline">{label}</span>
            </button>
            {i < STEPS.length - 1 && (
              <div class={`w-6 h-px mx-1 ${i < step ? 'bg-success/30' : 'bg-border'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div class="flex-1">
        {step === 0 && <WelcomeStep />}
        {step === 1 && <ApiKeysStep />}
        {step === 2 && <ProfileStep />}
        {step === 3 && <ProvidersStep />}
        {step === 4 && <ReviewStep />}
      </div>

      {/* Navigation */}
      <div class="flex justify-between mt-8 pt-4 border-t border-border">
        <button
          onClick={() => { setupStep.value = Math.max(0, step - 1) }}
          disabled={step === 0}
          class="px-4 py-2 text-sm text-dim hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Back
        </button>
        {step < STEPS.length - 1 ? (
          <button
            onClick={() => { setupStep.value = step + 1 }}
            class="px-6 py-2 text-sm bg-bg-2 border border-border rounded
              hover:border-accent text-bright transition-colors"
          >
            Next
          </button>
        ) : null}
      </div>
    </div>
  )
}
