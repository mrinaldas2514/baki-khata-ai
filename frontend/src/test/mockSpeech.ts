import { act } from '@testing-library/react'
import { vi } from 'vitest'
import type {
  SpeechRecognitionErrorEventLike,
  SpeechRecognitionEventLike,
  SpeechRecognitionLike,
} from '../voice/speechRecognition'

/**
 * A stand-in for the browser's (webkit)SpeechRecognition. Tests drive it by hand:
 * `listen()` (audio started), `say(text)`, `fail('not-allowed')`, `end()`.
 */
export class FakeSpeechRecognition implements SpeechRecognitionLike {
  static instances: FakeSpeechRecognition[] = []

  lang = ''
  continuous = false
  interimResults = false
  maxAlternatives = 1
  onstart: (() => void) | null = null
  onresult: ((event: SpeechRecognitionEventLike) => void) | null = null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null = null
  onend: (() => void) | null = null
  started = false
  stopped = false
  aborted = false

  constructor() {
    FakeSpeechRecognition.instances.push(this)
  }

  start() {
    this.started = true
  }

  stop() {
    this.stopped = true
  }

  abort() {
    this.aborted = true
  }

  listen() {
    act(() => this.onstart?.())
  }

  /** Words heard so far; `final` marks them as settled. */
  say(text: string, final = true) {
    const result = Object.assign([{ transcript: text }], { isFinal: final })
    act(() => this.onresult?.({ resultIndex: 0, results: [result] }))
  }

  fail(error: string) {
    act(() => {
      this.onerror?.({ error })
      this.onend?.()
    })
  }

  end() {
    act(() => this.onend?.())
  }
}

export function installSpeechRecognition() {
  FakeSpeechRecognition.instances = []
  vi.stubGlobal('webkitSpeechRecognition', FakeSpeechRecognition)
  return () => FakeSpeechRecognition.instances.at(-1)!
}

/** A stand-in for MediaRecorder: stop() hands over one chunk of "audio". */
export class FakeMediaRecorder {
  static isTypeSupported = (type: string) => type.startsWith('audio/webm')

  state: 'inactive' | 'recording' = 'inactive'
  mimeType: string
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null

  constructor(_stream: MediaStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? 'audio/webm'
  }

  start() {
    this.state = 'recording'
  }

  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['fake audio'], { type: this.mimeType }) })
    this.onstop?.()
  }
}

/** Install MediaRecorder and a microphone. `getUserMedia` decides whether access is granted. */
export function installRecorder(getUserMedia: () => Promise<unknown>) {
  const track = { stop: vi.fn() }
  const mic = vi.fn(async () => {
    await getUserMedia()
    return { getTracks: () => [track] }
  })
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: mic } })
  return { getUserMedia: mic, track }
}

export function uninstallRecorder() {
  Reflect.deleteProperty(navigator, 'mediaDevices')
}

export const grantMic = () => Promise.resolve()
export const denyMic = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError'))

/** Date.now() that tests can move forward, to tell a hold from a tap. */
export function controllableClock() {
  const realNow = Date.now.bind(Date)
  let offset = 0
  vi.spyOn(Date, 'now').mockImplementation(() => realNow() + offset)
  return (ms: number) => {
    offset += ms
  }
}
