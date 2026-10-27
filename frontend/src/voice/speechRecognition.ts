/**
 * The bits of the Web Speech API the app uses. TypeScript's DOM types don't include it yet,
 * and Chrome/Edge/Samsung Internet still only ship the `webkit`-prefixed constructor.
 */

export interface SpeechRecognitionAlternativeLike {
  transcript: string
}

export interface SpeechRecognitionResultLike {
  readonly isFinal: boolean
  readonly length: number
  [index: number]: SpeechRecognitionAlternativeLike
}

export interface SpeechRecognitionEventLike {
  readonly resultIndex: number
  readonly results: { readonly length: number; [index: number]: SpeechRecognitionResultLike }
}

export interface SpeechRecognitionErrorEventLike {
  /** 'not-allowed', 'service-not-allowed', 'no-speech', 'network', 'audio-capture', 'aborted'... */
  readonly error: string
}

export interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike

/** The browser's speech recognition, or null (Firefox, and Safari without Siri enabled). */
export function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  const w = globalThis as {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

/** Whether audio can be recorded and sent to the server (MediaRecorder + microphone access). */
export function canRecordAudio(): boolean {
  return (
    typeof MediaRecorder !== 'undefined' && typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
  )
}
