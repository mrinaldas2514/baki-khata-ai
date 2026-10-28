/** The offline queue: kept on the phone, sent in order with its Idempotency-Key, never twice. */
import { describe, expect, it } from 'vitest'
import type { ParseConfirm } from '../api/types'
import { CONFIRM, CONFIRM_MANY, confirmResult, customer, mockApi } from '../test/mockApi'
import { type QueuedSave, discard, enqueue, forgetShop, syncQueue } from './queue'
import { getAll } from './store'

const SHOP = 1

function save(name: string, amount: number, overrides: Partial<QueuedSave> = {}) {
  const entry: ParseConfirm = {
    raw_text: `${name} ${amount} baki`,
    type: 'credit',
    amount,
    item: null,
    new_customer: { name },
  }
  return {
    key: `key-${name}-${amount}`,
    rawText: entry.raw_text,
    endpoint: 'confirm' as const,
    entries: [entry],
    summary: [{ name, amount, type: 'credit' as const }],
    ...overrides,
  }
}

/** /parse/confirm creating a customer with this id per name. */
function created(ids: Record<string, number>) {
  return (body: unknown) => {
    const entry = body as ParseConfirm
    const name = entry.new_customer?.name ?? 'Someone'
    const id = entry.customer_id ?? ids[name]
    return {
      status: 201,
      body: confirmResult(customer(id, name, entry.amount), entry, entry.amount, !entry.customer_id),
    }
  }
}

const offline = () => Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })
const online = () => Reflect.deleteProperty(navigator, 'onLine')

describe('offline queue', () => {
  it('keeps the save on the phone with the time it was saved', async () => {
    offline()
    const item = await enqueue(SHOP, save('Tanvir', 90))
    online()
    const [stored] = await getAll<QueuedSave>('queue')
    expect(stored).toEqual(item)
    expect(stored.status).toBe('pending')
    expect(stored.entries[0].created_at).toBe(stored.savedAt)
  })

  it('sends them oldest first, each with its own Idempotency-Key, then forgets them', async () => {
    offline()
    await enqueue(SHOP, save('Tanvir', 90))
    await enqueue(SHOP, save('Rina', 40))
    online()
    const api = mockApi({ [CONFIRM]: created({ Tanvir: 7, Rina: 8 }) })
    await syncQueue(SHOP)
    expect(api.requests.map((r) => [r.key, r.headers.get('Idempotency-Key')])).toEqual([
      [CONFIRM, 'key-Tanvir-90'],
      [CONFIRM, 'key-Rina-40'],
    ])
    expect(await getAll('queue')).toEqual([])
  })

  it('stops at the first one without an answer and tries again later with the same key', async () => {
    offline()
    await enqueue(SHOP, save('Tanvir', 90))
    await enqueue(SHOP, save('Rina', 40))
    online()
    const failing = mockApi({ [CONFIRM]: 'network-error' })
    await syncQueue(SHOP)
    expect(failing.requests).toHaveLength(1) // Rina waits behind Tanvir
    expect(await getAll('queue')).toHaveLength(2)

    // The first try may have been saved; the server answers the same key with that result.
    const api = mockApi({ [CONFIRM]: created({ Tanvir: 7, Rina: 8 }) })
    await syncQueue(SHOP)
    expect(api.requests.map((r) => r.headers.get('Idempotency-Key'))).toEqual(['key-Tanvir-90', 'key-Rina-40'])
    expect(await getAll('queue')).toEqual([])
  })

  it.each([429, 500, 503, 401])('waits after a %i (server trouble, not a wrong entry)', async (status) => {
    offline()
    await enqueue(SHOP, save('Tanvir', 90))
    online()
    mockApi({ [CONFIRM]: { status, body: { detail: 'later' } } })
    await syncQueue(SHOP)
    const [item] = await getAll<QueuedSave>('queue')
    expect(item.status).toBe('pending')
  })

  it('marks one the server refuses as failed, with why, and goes on with the rest', async () => {
    offline()
    await enqueue(SHOP, save('Tanvir', 90))
    await enqueue(SHOP, save('Rina', 40))
    online()
    mockApi({
      [CONFIRM]: (body) =>
        (body as ParseConfirm).new_customer?.name === 'Tanvir'
          ? { status: 409, body: { detail: 'A customer named Tanvir already exists' } }
          : created({ Rina: 8 })(body),
    })
    await syncQueue(SHOP)
    const left = await getAll<QueuedSave>('queue')
    expect(left).toHaveLength(1)
    expect(left[0]).toMatchObject({ key: 'key-Tanvir-90', status: 'failed' })
    expect(left[0].error).toMatch(/customer/i)

    await discard(SHOP, 'key-Tanvir-90')
    expect(await getAll('queue')).toEqual([])
  })

  it('a new customer written twice offline is created once', async () => {
    offline()
    await enqueue(SHOP, save('Tanvir', 50))
    await enqueue(SHOP, save('tanvir', 20))
    online()
    const api = mockApi({ [CONFIRM]: created({ Tanvir: 7 }) })
    await syncQueue(SHOP)
    const [first, second] = api.bodiesOf(CONFIRM) as ParseConfirm[]
    expect(first.new_customer).toEqual({ name: 'Tanvir' })
    expect(second).toMatchObject({ customer_id: 7 })
    expect(second).not.toHaveProperty('new_customer')
  })

  it('a save of several goes to /parse/confirm-many, where it was first tried', async () => {
    offline()
    const one = save('Tanvir', 50)
    const two = save('Rina', 20)
    await enqueue(SHOP, { ...one, endpoint: 'confirm-many', entries: [...one.entries, ...two.entries] })
    online()
    const api = mockApi({
      [CONFIRM_MANY]: (body) => ({
        status: 201,
        body: {
          results: (body as { entries: ParseConfirm[] }).entries.map((e) => created({ Tanvir: 7, Rina: 8 })(e).body),
        },
      }),
    })
    await syncQueue(SHOP)
    expect(api.requests.map((r) => r.key)).toEqual([CONFIRM_MANY])
    expect((api.bodiesOf(CONFIRM_MANY)[0] as { entries: unknown[] }).entries).toHaveLength(2)
  })

  it('a deleted account leaves nothing on the phone', async () => {
    offline()
    await enqueue(SHOP, save('Tanvir', 90))
    online()
    await forgetShop(SHOP)
    expect(await getAll('queue')).toEqual([])
  })
})
