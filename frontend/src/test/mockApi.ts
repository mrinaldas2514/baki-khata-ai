import { vi } from 'vitest'
import type { Customer, CustomerCandidate, ParsePreview, RecentTransaction } from '../api/types'

/** What a mocked endpoint answers: JSON (status 200 unless given), or a thrown network error. */
export type MockAnswer = { status?: number; body?: unknown } | 'network-error'
type Handler = MockAnswer | ((body: unknown) => MockAnswer | Promise<MockAnswer>)

/**
 * Replace `fetch` with fake endpoints, keyed by "METHOD /path" (shop 1, query string ignored).
 * Returns the list of requests made, with their parsed JSON bodies.
 */
export function mockApi(handlers: Record<string, Handler>) {
  const requests: { key: string; body: unknown }[] = []
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const path = new URL(url).pathname
    const key = `${init.method ?? 'GET'} ${path}`
    // FormData (an audio upload) is passed through as is; JSON is parsed.
    const body = init.body instanceof FormData ? init.body : init.body ? JSON.parse(String(init.body)) : undefined
    requests.push({ key, body })
    const handler = handlers[key] ?? { status: 404, body: { detail: `No mock for ${key}` } }
    const answer = await (typeof handler === 'function' ? handler(body) : handler)
    if (answer === 'network-error') throw new TypeError('Failed to fetch')
    return new Response(JSON.stringify(answer.body ?? null), {
      status: answer.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { requests, bodiesOf: (key: string) => requests.filter((r) => r.key === key).map((r) => r.body) }
}

export const PARSE = 'POST /shops/1/parse'
export const CONFIRM = 'POST /shops/1/parse/confirm'
export const RECENT = 'GET /shops/1/transactions'
export const CUSTOMERS = 'GET /shops/1/customers'
export const TRANSCRIBE = 'POST /transcribe'
export const TRANSCRIBE_STATUS = 'GET /transcribe/status'

const NOW = '2026-10-27T10:00:00Z'

export function customer(id: number, name: string, balance: number, note: string | null = null): Customer {
  return { id, shop_id: 1, name, phone: null, note, created_at: NOW, balance }
}

export function candidate(c: Customer, score = 100): CustomerCandidate {
  return { ...c, score }
}

export function preview(overrides: {
  raw_text?: string
  parsed?: Partial<ParsePreview['parsed']>
  match?: Partial<ParsePreview['match']>
  warnings?: string[]
}): ParsePreview {
  return {
    raw_text: overrides.raw_text ?? 'salma apa pach sho taka baki, dal r tel',
    parsed: {
      customer_name: 'salma',
      amount: 500,
      type: 'credit',
      item: 'dal, tel',
      confidence: 0.95,
      ...overrides.parsed,
    },
    match: { status: 'new', customer: null, candidates: [], suggested_name: 'Salma', ...overrides.match },
    warnings: overrides.warnings ?? [],
  }
}

/** The /parse/confirm answer for saving `amount` for `who`, ending at `balance`. */
export function confirmResult(
  who: Customer,
  request: { type: 'credit' | 'payment'; amount: number; item: string | null; raw_text: string },
  balance: number,
  created = false,
) {
  return {
    transaction: {
      id: 99,
      shop_id: 1,
      customer_id: who.id,
      type: request.type,
      amount: request.amount,
      item: request.item,
      raw_text: request.raw_text,
      created_at: NOW,
      customer_balance: balance,
    },
    customer: { ...who, balance },
    customer_created: created,
  }
}

export function recentRow(id: number, who: Customer, amount: number, type: 'credit' | 'payment'): RecentTransaction {
  return {
    id,
    shop_id: 1,
    customer_id: who.id,
    type,
    amount,
    item: null,
    raw_text: null,
    created_at: NOW,
    customer_name: who.name,
    customer_note: who.note,
  }
}
