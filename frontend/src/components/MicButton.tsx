import { type PointerEvent, useRef } from 'react'
import { strings } from '../strings'
import type { VoiceState } from '../voice/useVoiceInput'

// Held at least this long = push-to-talk (stops on release). Shorter = a tap that toggles.
export const HOLD_MS = 350
// A click this soon after a pointer press is that press's own click, not a keyboard one.
const CLICK_AFTER_POINTER_MS = 800

interface Props {
  state: VoiceState
  onStart: () => void
  onStop: () => void
  disabled?: boolean
}

const STYLES: Record<VoiceState, string> = {
  idle: 'bg-white text-emerald-800 border-emerald-700',
  listening: 'bg-red-600 text-white border-red-700',
  processing: 'bg-stone-200 text-stone-700 border-stone-300',
  error: 'bg-amber-50 text-amber-900 border-amber-500',
}

const LABELS: Record<VoiceState, string> = {
  idle: strings.voice.micIdle,
  listening: strings.voice.micListening,
  processing: strings.voice.micProcessing,
  error: strings.voice.micRetry,
}

const TEXT: Record<VoiceState, string> = {
  idle: strings.voice.buttonIdle,
  listening: strings.voice.buttonListening,
  processing: strings.voice.buttonProcessing,
  error: strings.voice.buttonIdle,
}

/**
 * The big mic button. Hold to talk and release to stop, or tap once to start and again to stop
 * (keyboard and screen readers: Enter/Space toggles the same way).
 */
export function MicButton({ state, onStart, onStop, disabled = false }: Props) {
  const pressedAt = useRef<number | null>(null)
  const lastPointerAt = useRef(0)
  const listening = state === 'listening'

  function toggle() {
    if (listening) onStop()
    else if (state !== 'processing') onStart()
  }

  function handlePointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0 || disabled) return
    lastPointerAt.current = Date.now()
    // Keep receiving pointerup even if the finger slides off the button.
    event.currentTarget.setPointerCapture?.(event.pointerId)
    if (listening) {
      // Second tap of tap-to-start/tap-to-stop.
      pressedAt.current = null
      onStop()
    } else if (state !== 'processing') {
      pressedAt.current = Date.now()
      onStart()
    }
  }

  function handlePointerUp() {
    lastPointerAt.current = Date.now()
    const at = pressedAt.current
    pressedAt.current = null
    // A long press was push-to-talk: releasing stops. A short tap keeps listening.
    if (at !== null && Date.now() - at >= HOLD_MS) onStop()
  }

  return (
    <button
      type="button"
      data-state={state}
      aria-label={LABELS[state]}
      aria-pressed={listening}
      aria-busy={state === 'processing'}
      disabled={disabled || state === 'processing'}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onClick={() => {
        if (Date.now() - lastPointerAt.current > CLICK_AFTER_POINTER_MS) toggle()
      }}
      // Long-press on a phone would otherwise open a menu or select text.
      onContextMenu={(event) => event.preventDefault()}
      className={`relative flex min-h-14 min-w-24 touch-none flex-col items-center justify-center gap-0.5 rounded-2xl border-2 px-3 text-base font-semibold transition-colors select-none [-webkit-touch-callout:none] disabled:cursor-not-allowed ${STYLES[state]}`}
    >
      {listening && (
        <span className="pointer-events-none absolute inset-0 animate-ping rounded-2xl bg-red-500/40" aria-hidden />
      )}
      {state === 'processing' ? (
        <span className="size-6 animate-spin rounded-full border-4 border-stone-300 border-t-stone-700" aria-hidden />
      ) : (
        <MicIcon />
      )}
      <span className="relative" aria-hidden>
        {TEXT[state]}
      </span>
    </button>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="relative size-7" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
      <rect x="9" y="2" width="6" height="12" rx="3" fill="currentColor" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v4M8 22h8" strokeLinecap="round" />
    </svg>
  )
}
