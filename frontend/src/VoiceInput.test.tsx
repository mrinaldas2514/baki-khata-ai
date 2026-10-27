/**
 * Voice input with the speech APIs mocked: the mic button's states, push-to-talk and
 * tap-to-talk, the transcript landing in the box, permission and no-speech errors, and the
 * server (Whisper) fallback when the browser has no speech recognition.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { HOLD_MS } from './components/MicButton'
import { strings } from './strings'
import { PARSE, RECENT, TRANSCRIBE, TRANSCRIBE_STATUS, mockApi, preview } from './test/mockApi'
import {
  FakeSpeechRecognition,
  controllableClock,
  denyMic,
  grantMic,
  installRecorder,
  installSpeechRecognition,
  uninstallRecorder,
} from './test/mockSpeech'

const SERVER_ON = { body: { available: true, max_seconds: 30, max_bytes: 1_000_000 } }
const SERVER_OFF = { body: { available: false, max_seconds: 30, max_bytes: 1_000_000 } }
const SENTENCE = 'rahim bhai 2 kg chal 120 taka baki'

beforeEach(() => {
  try {
    localStorage.clear()
  } catch {
    // ignore
  }
})

afterEach(() => uninstallRecorder())

const box = () => screen.getByLabelText(strings.entryLabel)
const mic = () => screen.getByRole('button', { name: /Bole likhun|Shunchi|Lekha hocche|Abar bolun/ })

async function press(user: ReturnType<typeof userEvent.setup>, target = mic()) {
  await user.pointer({ keys: '[MouseLeft>]', target })
}

async function release(user: ReturnType<typeof userEvent.setup>, target = mic()) {
  await user.pointer({ keys: '[/MouseLeft]', target })
}

async function tap(user: ReturnType<typeof userEvent.setup>) {
  // The same element for both halves: the button can disappear in between (server 503).
  const target = mic()
  await press(user, target)
  await release(user, target)
}

function renderApp() {
  const user = userEvent.setup()
  render(<App />)
  return user
}

describe('with browser speech recognition', () => {
  let recognition: () => FakeSpeechRecognition

  beforeEach(() => {
    recognition = installSpeechRecognition()
  })

  it('hold to talk: idle -> listening -> processing -> transcript in the box, not submitted', async () => {
    const api = mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const advance = controllableClock()
    const user = renderApp()

    expect(mic()).toHaveAttribute('data-state', 'idle')
    expect(mic()).toHaveAccessibleName(strings.voice.micIdle)
    expect(screen.getByText(strings.voice.holdHint)).toBeInTheDocument()

    await press(user)
    const rec = recognition()
    expect(rec.started).toBe(true)
    expect(rec.lang).toBe('bn-BD')
    expect(rec.continuous).toBe(true)
    expect(mic()).toHaveAttribute('data-state', 'listening')
    expect(mic()).toHaveAttribute('aria-pressed', 'true')
    expect(mic().querySelector('.animate-ping')).not.toBeNull() // pulsing
    rec.listen()
    rec.say('rahim bhai 2 kg', false)
    expect(box()).toHaveValue('rahim bhai 2 kg') // words show up while speaking
    expect(box()).toBeDisabled()

    advance(HOLD_MS + 100)
    await release(user)
    expect(rec.stopped).toBe(true)
    expect(mic()).toHaveAttribute('data-state', 'processing')
    expect(mic()).toBeDisabled()

    rec.say(SENTENCE)
    rec.end()
    expect(mic()).toHaveAttribute('data-state', 'idle')
    expect(box()).toHaveValue(SENTENCE)
    expect(box()).toBeEnabled()
    expect(screen.getByText(strings.voice.checkTranscript)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: strings.submit })).toBeEnabled()
    expect(api.bodiesOf(PARSE)).toEqual([]) // the shopkeeper checks it first
  })

  it('the transcript can be fixed, then goes through the normal parse flow', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [TRANSCRIBE_STATUS]: SERVER_OFF,
      [PARSE]: { body: preview({ raw_text: 'rahim bhai 2 kg chal 150 taka baki' }) },
    })
    const user = renderApp()

    await tap(user)
    recognition().say('rahim bhai 2 kg chal 120 taka baki')
    await tap(user)
    recognition().end()

    await user.clear(box())
    await user.type(box(), 'rahim bhai 2 kg chal 150 taka baki')
    await user.click(screen.getByRole('button', { name: strings.submit }))

    expect(await screen.findByRole('region', { name: strings.confirmTitle })).toBeInTheDocument()
    expect(api.bodiesOf(PARSE)).toEqual([{ text: 'rahim bhai 2 kg chal 150 taka baki' }])
  })

  it('tap to start keeps listening after release; a second tap stops', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const user = renderApp()

    await tap(user)
    const rec = recognition()
    expect(rec.stopped).toBe(false)
    expect(mic()).toHaveAttribute('data-state', 'listening')
    expect(screen.getByRole('status')).toHaveTextContent(strings.voice.listeningHint)

    await tap(user)
    expect(rec.stopped).toBe(true)
    expect(mic()).toHaveAttribute('data-state', 'processing')
    expect(FakeSpeechRecognition.instances).toHaveLength(1)
  })

  it('works from the keyboard: Enter starts and stops', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const user = renderApp()

    mic().focus()
    await user.keyboard('{Enter}')
    expect(mic()).toHaveAttribute('data-state', 'listening')
    recognition().say(SENTENCE)
    await user.keyboard('{Enter}')
    expect(recognition().stopped).toBe(true)
    recognition().end()
    expect(box()).toHaveValue(SENTENCE)
  })

  it('microphone permission denied: friendly message, error state, typing still works', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const user = renderApp()
    await user.type(box(), 'salma')

    await tap(user)
    recognition().fail('not-allowed')

    expect(mic()).toHaveAttribute('data-state', 'error')
    expect(mic()).toHaveAccessibleName(strings.voice.micRetry)
    expect(screen.getByRole('alert')).toHaveTextContent(strings.errors.micPermission)
    expect(box()).toBeEnabled()
    expect(box()).toHaveValue('salma')

    // Trying again starts a fresh recognizer and clears the message.
    await tap(user)
    expect(FakeSpeechRecognition.instances).toHaveLength(2)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('explains that the mic needs https when the page is on plain http', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    vi.stubGlobal('isSecureContext', false)
    const user = renderApp()
    await tap(user)
    recognition().fail('not-allowed')
    expect(screen.getByRole('alert')).toHaveTextContent(strings.errors.micInsecure)
  })

  it.each([
    ['no-speech', strings.errors.micNoSpeech],
    ['network', strings.errors.micNetwork],
    ['audio-capture', strings.errors.micNotFound],
  ])('shows a friendly message for the %s error', async (error, message) => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const user = renderApp()
    await tap(user)
    recognition().fail(error)
    expect(screen.getByRole('alert')).toHaveTextContent(message)
  })

  it('ending without any words counts as no speech', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const user = renderApp()
    await tap(user)
    await tap(user)
    recognition().end()
    expect(mic()).toHaveAttribute('data-state', 'error')
    expect(screen.getByRole('alert')).toHaveTextContent(strings.errors.micNoSpeech)
  })

  it('auto-submit sends the transcript straight to the confirmation card', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [TRANSCRIBE_STATUS]: SERVER_OFF,
      [PARSE]: { body: preview({ raw_text: SENTENCE }) },
    })
    const user = renderApp()
    await user.click(screen.getByText(strings.voice.settingsTitle(strings.voice.languages['bn-BD'])))
    await user.click(screen.getByLabelText(strings.voice.autoSubmit))

    await tap(user)
    recognition().say(SENTENCE)
    await tap(user)
    recognition().end()

    expect(await screen.findByRole('region', { name: strings.confirmTitle })).toBeInTheDocument()
    expect(api.bodiesOf(PARSE)).toEqual([{ text: SENTENCE }])
  })

  it('remembers the chosen language', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const user = renderApp()
    await user.selectOptions(screen.getByLabelText(strings.voice.languageLabel), 'en-IN')
    await tap(user)
    expect(recognition().lang).toBe('en-IN')

    expect(JSON.parse(localStorage.getItem('baki-khata.voice')!)).toMatchObject({ language: 'en-IN' })
  })

  it('reads the saved language', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    localStorage.setItem('baki-khata.voice', JSON.stringify({ language: 'bn-IN' }))
    const first = renderApp()
    await tap(first)
    expect(recognition().lang).toBe('bn-IN')
  })

  it('works when localStorage throws (private mode)', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    const blocked = () => {
      throw new DOMException('blocked', 'SecurityError')
    }
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(blocked)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(blocked)
    const user = renderApp()
    await user.selectOptions(screen.getByLabelText(strings.voice.languageLabel), 'en-IN')
    await tap(user)
    expect(recognition().lang).toBe('en-IN')
  })

  it('hides the server choice when the server has no speech-to-text key', async () => {
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    renderApp()
    await waitFor(() => expect(mic()).toBeInTheDocument())
    expect(screen.queryByLabelText(strings.voice.preferServer)).not.toBeInTheDocument()
  })
})

describe('server fallback (no browser speech recognition)', () => {
  it('records, uploads to /transcribe and fills the box', async () => {
    const recorder = installRecorder(grantMic)
    const api = mockApi({
      [RECENT]: { body: [] },
      [TRANSCRIBE_STATUS]: SERVER_ON,
      [TRANSCRIBE]: { body: { text: `  ${SENTENCE} ` } },
    })
    const advance = controllableClock()
    const user = renderApp()

    await press(await waitForMic())
    await waitFor(() => expect(recorder.getUserMedia).toHaveBeenCalled())
    expect(mic()).toHaveAttribute('data-state', 'listening')
    advance(2000)
    await release(user)

    await waitFor(() => expect(box()).toHaveValue(SENTENCE))
    expect(mic()).toHaveAttribute('data-state', 'idle')
    expect(recorder.track.stop).toHaveBeenCalled() // the microphone is switched off again
    const [form] = api.bodiesOf(TRANSCRIBE) as FormData[]
    expect(form.get('language')).toBe('bn-BD')
    expect((form.get('file') as File).type).toBe('audio/webm;codecs=opus')
    expect(screen.getByText(strings.voice.serverOnly, { exact: false })).toBeInTheDocument()

    async function waitForMic() {
      await screen.findByRole('button', { name: strings.voice.micIdle })
      return user
    }
  })

  it('microphone permission denied', async () => {
    installRecorder(denyMic)
    const api = mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_ON })
    const user = renderApp()
    await screen.findByRole('button', { name: strings.voice.micIdle })

    await tap(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(strings.errors.micPermission)
    expect(mic()).toHaveAttribute('data-state', 'error')
    expect(api.bodiesOf(TRANSCRIBE)).toEqual([])
  })

  it('an empty transcript means no speech', async () => {
    installRecorder(grantMic)
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_ON, [TRANSCRIBE]: { body: { text: '' } } })
    const advance = controllableClock()
    const user = renderApp()
    await screen.findByRole('button', { name: strings.voice.micIdle })

    await tap(user)
    advance(2000)
    await tap(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(strings.errors.micNoSpeech)
  })

  it('a network error while uploading', async () => {
    installRecorder(grantMic)
    mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_ON, [TRANSCRIBE]: 'network-error' })
    const advance = controllableClock()
    const user = renderApp()
    await screen.findByRole('button', { name: strings.voice.micIdle })

    await tap(user)
    advance(2000)
    await tap(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(strings.errors.micNetwork)
  })

  it('a 503 (no key on the server) hides the server fallback', async () => {
    installRecorder(grantMic)
    mockApi({
      [RECENT]: { body: [] },
      [TRANSCRIBE_STATUS]: SERVER_ON,
      [TRANSCRIBE]: { status: 503, body: { detail: 'GROQ_API_KEY is missing' } },
    })
    const advance = controllableClock()
    const user = renderApp()
    await screen.findByRole('button', { name: strings.voice.micIdle })

    await tap(user)
    advance(2000)
    await tap(user)

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Bole likhun|Abar bolun/ })).not.toBeInTheDocument(),
    )
    expect(screen.getByLabelText(strings.entryLabel)).toBeEnabled()
  })

  it('no mic button when neither the browser nor the server can do speech', async () => {
    installRecorder(grantMic)
    const api = mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: SERVER_OFF })
    renderApp()
    await waitFor(() => expect(api.requests.map((r) => r.key)).toContain(TRANSCRIBE_STATUS))
    expect(screen.queryByRole('button', { name: strings.voice.micIdle })).not.toBeInTheDocument()
    expect(within(document.body).getByRole('button', { name: strings.submit })).toBeInTheDocument()
  })
})
