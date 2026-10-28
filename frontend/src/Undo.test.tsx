/** "Bhul hoyeche? Undo" for 10 seconds after saving. */
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { UNDO_SECONDS } from './components/SavedMessage'
import { strings } from './strings'
import {
  CONFIRM,
  PARSE,
  RECENT,
  confirmResult,
  customer,
  deleteCustomerKey,
  deleteKey,
  mockApi,
  preview,
  recentRow,
} from './test/mockApi'

const SENTENCE = 'tanvir 90 taka baki'
const tanvir = customer(12, 'Tanvir', 0)
const newCustomer = preview({
  raw_text: SENTENCE,
  parsed: { customer_name: 'tanvir', amount: 90, item: null },
  match: { status: 'new', suggested_name: 'Tanvir' },
})
const saved = confirmResult(tanvir, { type: 'credit', amount: 90, item: null, raw_text: SENTENCE }, 90, true)

async function saveOne(handlers: Parameters<typeof mockApi>[0] = {}, user = userEvent.setup()) {
  let undone = false
  const api = mockApi({
    [RECENT]: () => ({ body: undone ? [] : [recentRow(99, tanvir, 90, 'credit')] }),
    [PARSE]: { body: newCustomer },
    [CONFIRM]: { status: 201, body: saved },
    [deleteKey(99)]: () => {
      undone = true
      return { status: 204 }
    },
    [deleteCustomerKey(12)]: { status: 204 },
    ...handlers,
  })
  render(<App />)
  await user.type(screen.getByLabelText(strings.entryLabel), SENTENCE)
  await user.click(screen.getByRole('button', { name: strings.submit }))
  await user.click(await screen.findByRole('button', { name: strings.save }))
  await screen.findByText(`✓ ${strings.savedTitle}`)
  return { api, user }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('undo', () => {
  it('deletes the entry and the customer it created, and puts the sentence back', async () => {
    const { api, user } = await saveOne()
    const undo = screen.getByRole('button', { name: strings.undo.label })
    expect(undo).toHaveTextContent(strings.undo.button(UNDO_SECONDS))

    await user.click(undo)

    expect(await screen.findByText(`↶ ${strings.undo.done}`)).toBeInTheDocument()
    const keys = api.requests.map((r) => r.key)
    expect(keys.indexOf(deleteKey(99))).toBeGreaterThan(-1)
    expect(keys.indexOf(deleteCustomerKey(12))).toBeGreaterThan(keys.indexOf(deleteKey(99)))
    expect(screen.queryByText(`✓ ${strings.savedTitle}`)).not.toBeInTheDocument()
    expect(screen.getByLabelText(strings.entryLabel)).toHaveValue(SENTENCE)
    expect(await screen.findByText(strings.recentEmpty)).toBeInTheDocument()
  })

  it('keeps an existing customer (only the entry goes)', async () => {
    const salma = customer(3, 'Salma', 200)
    const { api, user } = await saveOne({
      [PARSE]: {
        body: preview({
          raw_text: SENTENCE,
          match: { status: 'exact', customer: { ...salma, score: 100 }, candidates: [], suggested_name: 'Salma' },
        }),
      },
      [CONFIRM]: {
        status: 201,
        body: confirmResult(salma, { type: 'credit', amount: 500, item: null, raw_text: SENTENCE }, 700),
      },
      [deleteKey(99)]: { status: 204 },
    })
    await user.click(screen.getByRole('button', { name: strings.undo.label }))
    await screen.findByText(`↶ ${strings.undo.done}`)
    expect(api.requests.some((r) => r.key.startsWith('DELETE /shops/1/customers/'))).toBe(false)
  })

  it('counts down and is gone after 10 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await saveOne({}, user)
    const undo = screen.getByRole('button', { name: strings.undo.label })

    await act(async () => {
      vi.advanceTimersByTime(3000)
    })
    expect(undo).toHaveTextContent(strings.undo.button(UNDO_SECONDS - 3))
    await act(async () => {
      vi.advanceTimersByTime(7000)
    })
    expect(screen.queryByRole('button', { name: strings.undo.label })).not.toBeInTheDocument()
    expect(screen.getByText(`✓ ${strings.savedTitle}`)).toBeInTheDocument()
  })

  it('says so when undo fails', async () => {
    const { user } = await saveOne({ [deleteKey(99)]: 'network-error' })
    await user.click(screen.getByRole('button', { name: strings.undo.label }))
    expect(await screen.findByText(strings.undo.failed)).toBeInTheDocument()
  })
})
