import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TranscribeStatus } from '../api/types'
import { canRecordAudio, getSpeechRecognition } from './speechRecognition'
import type { VoiceEngine } from './useVoiceInput'

// The browser's recognizer has no server limit, but one entry is one short sentence.
const BROWSER_MAX_SECONDS = 30

/**
 * Which engine the mic uses: the browser's own speech recognition when it has one, the server
 * (Whisper) when the browser has none or the shopkeeper prefers it, or none at all (no mic shown).
 */
export function useVoiceEngine(preferServer: boolean) {
  const [status, setStatus] = useState<TranscribeStatus | null>(null)

  useEffect(() => {
    // Not reachable or not set up: same thing for the app, the server option stays hidden.
    api.transcribeStatus().then(setStatus, () => setStatus(null))
  }, [])

  const browser = getSpeechRecognition() !== null
  const server = !!status?.available && canRecordAudio()
  let engine: VoiceEngine = 'none'
  if (server && (preferServer || !browser)) engine = 'server'
  else if (browser) engine = 'browser'

  return {
    engine,
    /** Both are available, so the shopkeeper can choose. */
    canChooseServer: browser && server,
    serverOnly: engine === 'server' && !browser,
    maxSeconds: engine === 'server' && status ? status.max_seconds : BROWSER_MAX_SECONDS,
    /** The server said it has no speech-to-text key (503): stop offering it. */
    disableServer: () => setStatus((current) => current && { ...current, available: false }),
  }
}
