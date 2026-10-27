/**
 * The two ways speech becomes text. Both report through the same handlers, so the mic button
 * doesn't care which one runs:
 *
 *   browser: the Web Speech API (free, instant, shows words while you speak; needs internet
 *            in Chrome, weaker on mixed Banglish)
 *   server:  record with MediaRecorder, send to POST /transcribe (Whisper; better accuracy)
 */
import { ApiError } from '../api/client'
import { getSpeechRecognition } from './speechRecognition'

export type VoiceErrorCode =
  | 'permission' // microphone access denied
  | 'insecure' // the page isn't on https or localhost, so browsers block the microphone
  | 'no-speech' // nothing was heard
  | 'no-mic' // no microphone found / it can't be used
  | 'network' // no internet, or the speech service can't be reached
  | 'language' // the browser can't recognize the chosen language
  | 'server-off' // the backend has no speech-to-text key (503)
  | 'too-long' // the server refused the recording as too big or long (413)
  | 'failed' // anything else

export interface VoiceHandlers {
  /** The microphone is on. */
  onListening(): void
  /** Words so far, while still listening (browser only). */
  onInterim(text: string): void
  /** Listening stopped; the final text is on its way. */
  onProcessing(): void
  /** The final text. Empty when nothing was understood. */
  onResult(text: string): void
  onError(code: VoiceErrorCode): void
}

export interface VoiceSession {
  /** Stop listening and deliver what was said. */
  stop(): void
  /** Stop and throw it away; no more handler calls. */
  abort(): void
}

const tidy = (text: string) => text.replace(/\s+/g, ' ').trim()

const BROWSER_ERRORS: Record<string, VoiceErrorCode> = {
  'not-allowed': 'permission',
  'service-not-allowed': 'permission',
  'no-speech': 'no-speech',
  'audio-capture': 'no-mic',
  network: 'network',
  'language-not-supported': 'language',
}

export function startBrowserSession(language: string, handlers: VoiceHandlers): VoiceSession {
  const Recognition = getSpeechRecognition()
  if (!Recognition) throw new Error('Speech recognition is not available')
  const recognition = new Recognition()
  recognition.lang = language
  // Keep listening through short pauses ("rahim... 120 taka baki") until the button is released.
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 1

  let heard = ''
  let done = false

  recognition.onstart = () => handlers.onListening()
  recognition.onresult = (event) => {
    // Rebuild from every result each time: interim results get replaced as words firm up.
    let text = ''
    for (let i = 0; i < event.results.length; i++) text += ` ${event.results[i][0]?.transcript ?? ''}`
    heard = tidy(text)
    if (heard) handlers.onInterim(heard)
  }
  recognition.onerror = (event) => {
    if (done) return
    done = true
    if (event.error === 'aborted') return
    const code = BROWSER_ERRORS[event.error] ?? 'failed'
    handlers.onError(code === 'permission' && globalThis.isSecureContext === false ? 'insecure' : code)
  }
  recognition.onend = () => {
    if (done) return
    done = true
    handlers.onResult(heard)
  }

  try {
    recognition.start()
  } catch {
    done = true
    handlers.onError('failed')
  }

  return {
    stop() {
      if (done) return
      handlers.onProcessing()
      recognition.stop()
    },
    abort() {
      done = true
      recognition.abort()
    },
  }
}

// Speech at 32 kbit/s Opus is clear and keeps 30 s near 120 KB on a slow connection.
const AUDIO_BITS_PER_SECOND = 32_000
// Shorter than this is a tap, not speech.
const MIN_RECORDING_MS = 500
const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

function pickMimeType(): string | undefined {
  return MIME_TYPES.find((type) => MediaRecorder.isTypeSupported?.(type))
}

function micErrorCode(error: unknown): VoiceErrorCode {
  const name = error instanceof Error || error instanceof DOMException ? error.name : ''
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'permission'
  if (name === 'NotFoundError' || name === 'NotReadableError' || name === 'OverconstrainedError') return 'no-mic'
  return 'failed'
}

export function serverErrorCode(error: unknown): VoiceErrorCode {
  if (!(error instanceof ApiError) || error.kind === 'network') return 'network'
  if (error.status === 503) return 'server-off'
  if (error.status === 413) return 'too-long'
  return 'failed'
}

export function startServerSession(
  language: string,
  transcribe: (audio: Blob, language: string) => Promise<string>,
  handlers: VoiceHandlers,
): VoiceSession {
  let recorder: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let startedAt = 0
  let stopRequested = false
  let done = false
  const chunks: Blob[] = []

  const release = () => stream?.getTracks().forEach((track) => track.stop())

  navigator.mediaDevices.getUserMedia({ audio: true }).then(
    (micStream) => {
      stream = micStream
      if (done) return release()
      const mimeType = pickMimeType()
      try {
        recorder = new MediaRecorder(micStream, { mimeType, audioBitsPerSecond: AUDIO_BITS_PER_SECOND })
      } catch {
        done = true
        release()
        return handlers.onError('failed')
      }
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data)
      }
      recorder.onstop = async () => {
        release()
        if (done) return
        const audio = new Blob(chunks, { type: recorder?.mimeType || mimeType || 'audio/webm' })
        if (audio.size === 0 || Date.now() - startedAt < MIN_RECORDING_MS) {
          done = true
          return handlers.onError('no-speech')
        }
        try {
          const text = await transcribe(audio, language)
          if (!done) handlers.onResult(tidy(text))
        } catch (error) {
          if (!done) handlers.onError(serverErrorCode(error))
        }
        done = true
      }
      recorder.start()
      startedAt = Date.now()
      handlers.onListening()
      // Released while the browser was still asking for the microphone.
      if (stopRequested) recorder.stop()
    },
    (error) => {
      if (done) return
      done = true
      handlers.onError(micErrorCode(error))
    },
  )

  return {
    stop() {
      if (done || stopRequested) return
      stopRequested = true
      handlers.onProcessing()
      if (recorder?.state === 'recording') recorder.stop()
    },
    abort() {
      done = true
      if (recorder?.state === 'recording') recorder.stop()
      else release()
    },
  }
}
