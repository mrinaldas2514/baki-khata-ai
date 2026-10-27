import { useEffect, useRef, useState } from 'react'
import {
  type VoiceErrorCode,
  type VoiceHandlers,
  type VoiceSession,
  startBrowserSession,
  startServerSession,
} from './engines'

export type VoiceEngine = 'browser' | 'server' | 'none'

/**
 *   idle --start--> listening --stop--> processing --text--> idle
 *                       |                    |
 *                       +------error---------+--> error --start--> listening
 */
export type VoiceState = 'idle' | 'listening' | 'processing' | 'error'

interface Options {
  engine: VoiceEngine
  language: string
  /** Recording stops by itself after this long. */
  maxSeconds: number
  transcribe: (audio: Blob, language: string) => Promise<string>
  /** Words so far, to show in the text box while speaking. */
  onInterim: (text: string) => void
  /** The final, non-empty text. */
  onText: (text: string) => void
  onError?: (code: VoiceErrorCode) => void
}

export function useVoiceInput(options: Options) {
  const [state, setState] = useState<VoiceState>('idle')
  const [error, setError] = useState<VoiceErrorCode | null>(null)
  const session = useRef<VoiceSession | null>(null)
  const run = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  // Handlers fire long after render; always call the latest callbacks.
  const latest = useRef(options)
  useEffect(() => {
    latest.current = options
  })

  useEffect(
    () => () => {
      clearTimeout(timer.current)
      session.current?.abort()
    },
    [],
  )

  function start() {
    const { engine, language, maxSeconds, transcribe } = latest.current
    if (engine === 'none' || session.current) return
    const mine = ++run.current
    const isCurrent = () => mine === run.current

    function finish() {
      clearTimeout(timer.current)
      session.current = null
      run.current++
    }

    function fail(code: VoiceErrorCode) {
      finish()
      setError(code)
      setState('error')
      latest.current.onError?.(code)
    }

    const handlers: VoiceHandlers = {
      onListening() {
        if (!isCurrent()) return
        clearTimeout(timer.current)
        timer.current = setTimeout(() => session.current?.stop(), maxSeconds * 1000)
      },
      onInterim(text) {
        if (isCurrent()) latest.current.onInterim(text)
      },
      onProcessing() {
        if (!isCurrent()) return
        clearTimeout(timer.current)
        setState('processing')
      },
      onResult(text) {
        if (!isCurrent()) return
        if (!text) return fail('no-speech')
        finish()
        setState('idle')
        latest.current.onText(text)
      },
      onError(code) {
        if (isCurrent()) fail(code)
      },
    }

    setError(null)
    setState('listening')
    const started =
      engine === 'browser'
        ? startBrowserSession(language, handlers)
        : startServerSession(language, transcribe, handlers)
    // An engine can fail while starting, before `started` is returned.
    if (isCurrent()) session.current = started
  }

  function stop() {
    session.current?.stop()
  }

  return { state, error, start, stop }
}
