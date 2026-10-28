/**
 * Entry speed: from the first keystroke or mic press until saved, sent with the save (numbers
 * only), and the dashboard's "Gore ekta hisab: X second".
 */
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { formatSeconds } from './entrySpeed'
import { strings } from './strings'
import { CONFIRM, PARSE, RECENT, TRANSCRIBE_STATUS, confirmResult, customer, mockApi, preview } from './test/mockApi'
import { installSpeechRecognition } from './test/mockSpeech'

let now = 0
beforeEach(() => {
  now = 10_000
  vi.spyOn(performance, 'now').mockImplementation(() => now)
})

const tanvir = customer(7, 'Tanvir', 0)
const SENTENCE = 'tanvir 90 taka baki'

function handlers() {
  return {
    [RECENT]: { body: [] },
    [TRANSCRIBE_STATUS]: { body: { available: false, max_seconds: 30, max_bytes: 1_000_000 } },
    [PARSE]: { body: preview({ raw_text: SENTENCE, parsed: { customer_name: 'tanvir', amount: 90, item: null } }) },
    [CONFIRM]: (body: unknown) => ({ status: 201, body: confirmResult(tanvir, body as never, 90, true) }),
  }
}

const box = () => screen.getByLabelText(strings.entryLabel)

async function parseAndSave(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: strings.submit }))
  await screen.findByRole('region', { name: strings.confirmTitle })
  now += 1_500 // checking the card
  await user.click(screen.getByRole('button', { name: strings.save }))
  await screen.findByText(new RegExp(strings.savedTitle))
}

describe('entry speed', () => {
  it('sends the time from the first keystroke to the save, as typed', async () => {
    const api = mockApi(handlers())
    const user = userEvent.setup()
    render(<App />)

    await user.type(box(), 't')
    now += 4_000 // typing the rest
    await user.type(box(), 'anvir 90 taka baki')
    await parseAndSave(user)

    const [body] = api.bodiesOf(CONFIRM) as { timing: unknown; raw_text: string }[]
    expect(body.timing).toEqual({ duration_ms: 5_500, input: 'typed' })
  })

  it('starts over when the box is emptied, and after each save', async () => {
    const api = mockApi(handlers())
    const user = userEvent.setup()
    render(<App />)

    await user.type(box(), 'oops')
    now += 60_000
    await user.clear(box())
    now += 1_000
    await user.type(box(), SENTENCE)
    await parseAndSave(user)

    now += 30_000 // the next customer comes later
    await user.type(box(), SENTENCE)
    now += 2_000
    await parseAndSave(user)

    const timings = (api.bodiesOf(CONFIRM) as { timing: { duration_ms: number } }[]).map((b) => b.timing.duration_ms)
    expect(timings).toEqual([1_500, 3_500])
  })

  it('counts from the mic press, as voice', async () => {
    const recognition = installSpeechRecognition()
    const api = mockApi(handlers())
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: strings.voice.micIdle }))
    const rec = recognition()
    act(() => {
      rec.listen()
      now += 3_000
      rec.say(SENTENCE)
      rec.end()
    })
    await parseAndSave(user)

    const [body] = api.bodiesOf(CONFIRM) as { timing: unknown }[]
    expect(body.timing).toEqual({ duration_ms: 4_500, input: 'voice' })
  })
})

describe('formatSeconds', () => {
  it('shows tenths below 10 seconds', () => {
    expect(formatSeconds(8.43)).toBe('8.4')
    expect(formatSeconds(12.6)).toBe('13')
  })
})
