import { useMemo, useRef, useCallback } from 'preact/hooks'
import { computed } from '@preact/signals'
import type { ParamBound } from '../../types'
import { localEdits, setLocalEdit, approveOverride, revertOverride, getActiveValue, hasOverride, savingParams } from '../../state/tuning'
import { formatParamValue, PARAM_BY_KEY } from '../../data/params'

interface Props {
  param: ParamBound
}

export function ParamSlider({ param }: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const localValue = useMemo(() => computed(() => localEdits.value[param.key] ?? null), [param.key])
  const isSaving = useMemo(() => computed(() => !!savingParams.value[param.key]), [param.key])

  const activeValue = getActiveValue(param.key, param.default)
  const displayValue = localValue.value ?? activeValue
  const isModified = localValue.value !== null && Math.abs(localValue.value - activeValue) > param.step * 0.5
  const isOverridden = hasOverride(param.key)

  // Brand drift warning
  let brandDrift: number | null = null
  if (param.brandRef && param.brandThreshold) {
    const refDefault = PARAM_BY_KEY[param.brandRef]?.default
    if (refDefault != null) {
      brandDrift = Math.abs(displayValue - refDefault)
      if (brandDrift <= param.brandThreshold) brandDrift = null
    }
  }

  // Significant change warning (>50% of param range)
  const range = param.max - param.min
  const changePct = Math.abs(displayValue - param.default) / range
  const isSignificantChange = changePct > 0.5

  // Percentage for positioning
  const valueToPct = (v: number) => ((v - param.min) / range) * 100
  const thumbPct = valueToPct(displayValue)
  const defaultPct = valueToPct(param.default)

  const snapToStep = useCallback((raw: number) => {
    const snapped = Math.round((raw - param.min) / param.step) * param.step + param.min
    return Math.max(param.min, Math.min(param.max, parseFloat(snapped.toFixed(6))))
  }, [param.min, param.max, param.step])

  const handlePointerDown = useCallback((e: PointerEvent) => {
    const track = trackRef.current
    if (!track) return
    ;(e.target as Element).setPointerCapture(e.pointerId)
    const rect = track.getBoundingClientRect()
    const update = (clientX: number) => {
      const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
      const raw = param.min + pct * range
      setLocalEdit(param.key, snapToStep(raw))
    }
    update(e.clientX)
    const onMove = (ev: PointerEvent) => update(ev.clientX)
    const onUp = (ev: PointerEvent) => {
      ;(ev.target as Element).releasePointerCapture(ev.pointerId)
      track.removeEventListener('pointermove', onMove)
      track.removeEventListener('pointerup', onUp)
    }
    track.addEventListener('pointermove', onMove)
    track.addEventListener('pointerup', onUp)
  }, [param.key, param.min, range, snapToStep])

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    let newVal = displayValue
    switch (e.key) {
      case 'ArrowRight': case 'ArrowUp': newVal += param.step; break
      case 'ArrowLeft': case 'ArrowDown': newVal -= param.step; break
      case 'PageUp': newVal += param.step * 10; break
      case 'PageDown': newVal -= param.step * 10; break
      case 'Home': newVal = param.min; break
      case 'End': newVal = param.max; break
      default: return
    }
    e.preventDefault()
    setLocalEdit(param.key, snapToStep(newVal))
  }, [displayValue, param.key, param.min, param.max, param.step, snapToStep])

  const handleNumberInput = useCallback((e: Event) => {
    const v = parseFloat((e.target as HTMLInputElement).value)
    if (Number.isFinite(v)) {
      setLocalEdit(param.key, snapToStep(v))
    }
  }, [param.key, snapToStep])

  return (
    <div class="space-y-1.5">
      {/* Row 1: Label + Value */}
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <span class="text-xs text-bright font-medium truncate">{param.label}</span>
          {isOverridden && (
            <span class="text-[8px] text-running bg-running/10 border border-running/20 rounded px-1">OVERRIDE</span>
          )}
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <input
            type="number"
            class="w-16 bg-bg-2 border border-border rounded px-1.5 py-0.5 text-xs text-bright text-right tabular-nums focus:border-running/50 focus:outline-none"
            min={param.min}
            max={param.max}
            step={param.step}
            value={displayValue.toFixed(2)}
            onInput={handleNumberInput}
          />
          <span class="text-[9px] text-dim w-3">{param.unit ?? ''}</span>
        </div>
      </div>

      {/* Row 2: Description */}
      <div class="text-[10px] text-dim leading-tight">{param.description}</div>

      {/* Row 3: Slider track */}
      <div
        ref={trackRef}
        class="relative h-8 flex items-center cursor-pointer touch-none select-none"
        role="slider"
        tabIndex={0}
        aria-valuemin={param.min}
        aria-valuemax={param.max}
        aria-valuenow={displayValue}
        aria-label={param.label}
        onPointerDown={handlePointerDown}
        onKeyDown={handleKeyDown}
      >
        {/* Track background */}
        <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 bg-bg-2 rounded-full" />
        {/* Active fill */}
        <div
          class="absolute top-1/2 -translate-y-1/2 h-1.5 bg-running/60 rounded-full left-0"
          style={{ width: `${thumbPct}%` }}
        />
        {/* Default marker */}
        <div
          class="absolute top-1/2 -translate-y-1/2 w-1 h-3.5 bg-dim/50 rounded-sm"
          style={{ left: `${defaultPct}%`, transform: 'translate(-50%, -50%)' }}
          title={`Default: ${formatParamValue(param.default, param)}`}
        />
        {/* Thumb */}
        <div
          class="absolute top-1/2 w-4 h-4 rounded-full bg-running border-2 border-bg-1 shadow-[0_0_6px_rgba(59,130,246,0.5)] hover:shadow-[0_0_10px_rgba(59,130,246,0.7)] transition-shadow duration-200"
          style={{ left: `${thumbPct}%`, transform: 'translate(-50%, -50%)' }}
        />
        {/* Min/Max labels */}
        <span class="absolute -bottom-0.5 left-0 text-[8px] text-dim">{formatParamValue(param.min, param)}</span>
        <span class="absolute -bottom-0.5 right-0 text-[8px] text-dim">{formatParamValue(param.max, param)}</span>
      </div>

      {/* Row 4: Actions + Warnings */}
      <div class="flex items-center gap-2 flex-wrap min-h-[20px]">
        {isModified && (
          <button
            onClick={() => approveOverride(param.key, displayValue)}
            disabled={isSaving.value}
            class="px-2 py-0.5 text-[10px] font-bold text-success border border-success/30 rounded hover:bg-success/10 disabled:opacity-50"
          >
            {isSaving.value ? '...' : 'SAVE'}
          </button>
        )}
        {isOverridden && (
          <button
            onClick={() => revertOverride(param.key)}
            disabled={isSaving.value}
            class="px-2 py-0.5 text-[10px] font-bold text-warning border border-warning/30 rounded hover:bg-warning/10 disabled:opacity-50"
          >
            REVERT
          </button>
        )}
        {brandDrift != null && (
          <span class="text-[9px] text-warning bg-warning/10 border border-warning/30 rounded px-1.5 py-0.5">
            BRAND DRIFT {brandDrift.toFixed(2)}
          </span>
        )}
        {isSignificantChange && (
          <span class="text-[9px] text-warning">Significant change from default</span>
        )}
      </div>
    </div>
  )
}
