import { useRef } from 'react'

/** Sent with a save: how long the entry took. Only the number is kept (backend: EntryTiming). */
export interface EntryTiming {
  duration_ms: number
  input: 'typed' | 'voice'
}

// Longer than this the phone was put down halfway; the backend ignores it too.
const MAX_MS = 60 * 60 * 1000

/**
 * Measures one entry on the Hisab screen: from the first keystroke or mic press until it's saved.
 * Clearing the box starts over; a failed save keeps counting (the shopkeeper is still at it).
 */
export function useEntryTimer() {
  const started = useRef<{ at: number; voice: boolean } | null>(null)

  return {
    /** The shopkeeper typed: start, or (box emptied) start over. */
    typed(text: string) {
      if (!text.trim()) started.current = null
      else started.current ??= { at: performance.now(), voice: false }
    },
    /** The mic was pressed: start, and count the entry as spoken. */
    micPressed() {
      if (started.current) started.current.voice = true
      else started.current = { at: performance.now(), voice: true }
    },
    /** For the save request (undefined if nothing was measured). */
    current(): EntryTiming | undefined {
      if (!started.current) return undefined
      const duration = Math.round(performance.now() - started.current.at)
      if (duration <= 0 || duration > MAX_MS) return undefined
      return { duration_ms: duration, input: started.current.voice ? 'voice' : 'typed' }
    },
    /** Saved: the next entry starts from zero. */
    reset() {
      started.current = null
    },
  }
}

/** "8.4" under 10 seconds, "12" above. */
export function formatSeconds(seconds: number): string {
  return seconds < 10 ? seconds.toFixed(1) : String(Math.round(seconds))
}
