/**
 * Working without internet on the Hisab screen: the sentence is read on the phone (AI chhara),
 * the entry is kept on the phone with "Pending sync", and goes to the server by itself, once.
 */
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import type { ParseConfirm } from './api/types'
import { cacheCustomers } from './offline/customerCache'
import { strings } from './strings'
import {
  CONFIRM,
  CONFIRM_MANY,
  CUSTOMERS,
  PARSE,
  RECENT,
  confirmResult,
  customer,
  mockApi,
  recentRow,
} from './test/mockApi'

const rahim = customer(1, 'Rahim', 300, 'Bazar road')
const karim = customer(2, 'Karim', 0)

function goOffline() {
  Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })
  act(() => void window.dispatchEvent(new Event('offline')))
}

function goOnline() {
  Reflect.deleteProperty(navigator, 'onLine')
  act(() => void window.dispatchEvent(new Event('online')))
}

const status = () => screen.getByTestId('online-status')
const box = () => screen.getByLabelText(strings.entryLabel)
const card = () => screen.getByRole('region', { name: strings.confirmTitle })

async function write(sentence: string) {
  const user = userEvent.setup()
  const { unmount } = render(<App />)
  await user.type(box(), sentence)
  await user.click(screen.getByRole('button', { name: strings.submit }))
  return Object.assign(user, { unmount })
}

const saved = (body: unknown, who = rahim, balance = 500) => ({
  status: 201,
  body: confirmResult(who, body as never, balance),
})

describe('offline', () => {
  it('reads the sentence on the phone, keeps the entry, and sends it when back online', async () => {
    cacheCustomers(1, [rahim, karim])
    const api = mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: [rahim, karim] },
      [CONFIRM]: (body) => saved(body),
    })
    goOffline()
    const user = await write('rahim 200 baki')

    // Read on the phone: no request, the "AI chhara" label, and why.
    expect(api.bodiesOf(PARSE)).toEqual([])
    expect(within(card()).getByTestId('parser-label')).toHaveTextContent(strings.parser.rules)
    expect(screen.getByText(strings.offline.readOnPhone)).toBeInTheDocument()
    expect(within(card()).getByTestId('customer-summary')).toHaveTextContent('Rahim')
    expect(within(card()).getByTestId('amount')).toHaveTextContent('৳200')

    await user.click(screen.getByRole('button', { name: strings.save }))
    expect(await screen.findByText(`📱 ${strings.offline.queuedTitle}`)).toBeInTheDocument()
    expect(api.bodiesOf(CONFIRM)).toEqual([])
    const pending = within(screen.getByRole('region', { name: `⏳ ${strings.offline.pendingTitle(1)}` }))
    expect(pending.getByTestId('pending-item')).toHaveTextContent('Rahim')
    expect(pending.getByTestId('pending-item')).toHaveTextContent(strings.offline.pendingBadge)
    expect(status()).toHaveAttribute('data-online', 'false')
    expect(status()).toHaveTextContent(`${strings.offline.offline} · ${strings.offline.pendingCount(1)}`)
    expect(box()).toHaveValue('')

    // Back online: sent by itself, with the key and the time it was written.
    api.requests.length = 0
    goOnline()
    await waitFor(() => expect(api.bodiesOf(CONFIRM)).toHaveLength(1))
    const [request] = api.requests.filter((r) => r.key === CONFIRM)
    expect(request.headers.get('Idempotency-Key')).toMatch(/^[0-9a-f-]{36}$/)
    expect(request.body).toMatchObject({
      customer_id: rahim.id,
      amount: 200,
      type: 'credit',
      raw_text: 'rahim 200 baki',
    })
    expect((request.body as ParseConfirm).created_at).toMatch(/^\d{4}-\d\d-\d\dT/)
    await waitFor(() => expect(screen.queryByTestId('pending-item')).not.toBeInTheDocument())
    expect(status()).toHaveTextContent(strings.offline.online)
    expect(api.requests.some((r) => r.key === RECENT)).toBe(true) // the list is reloaded
  })

  it("says so when the phone can't read it either, and the manual form still saves it", async () => {
    mockApi({ [RECENT]: { body: [] } })
    goOffline()
    const user = await write('rina kichu nilo')
    const form = screen.getByRole('region', { name: strings.manualTitle })
    expect(within(form).getByRole('alert')).toHaveTextContent(strings.offline.cantRead)
    await user.type(within(form).getByLabelText(strings.customer), 'Rina')
    await user.type(within(form).getByLabelText(strings.amount), '150')
    await user.click(within(form).getByRole('button', { name: strings.save }))
    expect(await screen.findByTestId('pending-item')).toHaveTextContent('Rina')
  })

  it('several customers offline: a card each, kept as one save', async () => {
    cacheCustomers(1, [rahim, karim])
    const api = mockApi({ [RECENT]: { body: [] } })
    goOffline()
    const user = await write('rahim 200 baki, karim 500 dilo')
    expect(screen.getAllByTestId('multi-card')).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: strings.multi.saveAll(2) }))
    const item = await screen.findByTestId('pending-item')
    expect(item).toHaveTextContent('Rahim')
    expect(item).toHaveTextContent('Karim')
    expect(api.requests.filter((r) => r.key === CONFIRM_MANY)).toEqual([])
  })

  it('Undo throws away an entry that is still on the phone', async () => {
    cacheCustomers(1, [rahim])
    mockApi({ [RECENT]: { body: [] } })
    goOffline()
    const user = await write('rahim 200 baki')
    await user.click(screen.getByRole('button', { name: strings.save }))
    await user.click(await screen.findByRole('button', { name: strings.undo.label }))
    await waitFor(() => expect(screen.queryByTestId('pending-item')).not.toBeInTheDocument())
    expect(box()).toHaveValue('rahim 200 baki')
  })

  it('entries on the phone survive closing the app', async () => {
    cacheCustomers(1, [rahim])
    mockApi({ [RECENT]: { body: [] } })
    goOffline()
    const user = await write('rahim 200 baki')
    await user.click(screen.getByRole('button', { name: strings.save }))
    await screen.findByTestId('pending-item')

    user.unmount() // the app is closed...
    render(<App />) // ...and opened again
    expect(await screen.findByTestId('pending-item')).toHaveTextContent('Rahim')
  })

  it('Settings warns before logging out with entries still on the phone', async () => {
    cacheCustomers(1, [rahim])
    mockApi({ [RECENT]: { body: [] } })
    goOffline()
    const user = await write('rahim 200 baki')
    await user.click(screen.getByRole('button', { name: strings.save }))
    await screen.findByTestId('pending-item')
    await user.click(screen.getByRole('link', { name: strings.settings.open }))
    expect(await screen.findByText(strings.offline.logoutWarning(1))).toBeInTheDocument()
  })
})

describe('a weak connection', () => {
  it('a parse without an answer is read on the phone instead', async () => {
    cacheCustomers(1, [rahim])
    mockApi({ [RECENT]: { body: [] }, [PARSE]: 'network-error' })
    await write('rahim 200 baki')
    expect(await screen.findByText(strings.offline.readAfterNetworkError)).toBeInTheDocument()
    expect(within(card()).getByTestId('parser-label')).toHaveTextContent(strings.parser.rules)
  })

  it('a save without an answer is kept on the phone and retried with the same key: saved once', async () => {
    cacheCustomers(1, [rahim])
    let answer: 'network-error' | 'ok' = 'network-error'
    const api = mockApi({
      [RECENT]: { body: [recentRow(5, rahim, 100, 'credit')] },
      [PARSE]: 'network-error',
      [CONFIRM]: (body) => (answer === 'network-error' ? 'network-error' : saved(body)),
    })
    const user = await write('rahim 200 baki')
    await user.click(screen.getByRole('button', { name: strings.save }))
    expect(await screen.findByText(`📱 ${strings.offline.queuedTitle}`)).toBeInTheDocument()

    const syncNow = await screen.findByRole('button', { name: strings.offline.syncNow })
    answer = 'ok' // the connection is better now
    await user.click(syncNow)
    await waitFor(() => expect(screen.queryByTestId('pending-item')).not.toBeInTheDocument())
    const keys = api.requests.filter((r) => r.key === CONFIRM).map((r) => r.headers.get('Idempotency-Key'))
    expect(keys.length).toBeGreaterThanOrEqual(2) // the first try, then the queue's
    expect(new Set(keys).size).toBe(1) // every try with the same key: the server saves it once
  })

  it('a save the server refuses is not kept on the phone: the card says why', async () => {
    cacheCustomers(1, [rahim])
    mockApi({
      [RECENT]: { body: [] },
      [PARSE]: 'network-error',
      [CONFIRM]: { status: 409, body: { detail: 'exists' } },
    })
    const user = await write('rahim 200 baki')
    await user.click(screen.getByRole('button', { name: strings.save }))
    expect(await screen.findByText(strings.errors.duplicateCustomer)).toBeInTheDocument()
    expect(screen.queryByTestId('pending-item')).not.toBeInTheDocument()
  })
})

describe('online / offline in the title bar', () => {
  it('shows the connection as it changes', async () => {
    mockApi({ [RECENT]: { body: [] } })
    render(<App />)
    expect(status()).toHaveTextContent(strings.offline.online)
    goOffline()
    expect(status()).toHaveTextContent(strings.offline.offline)
    expect(status()).toHaveTextContent(strings.offline.statusLabel(false, 0)) // for screen readers
    goOnline()
    expect(status()).toHaveTextContent(strings.offline.online)
  })
})
