import { vi } from 'vitest'
import type {
  Customer,
  CustomerCandidate,
  CustomerLedger,
  CustomerListItem,
  LedgerEntry,
  ParsePreview,
  RecentTransaction,
  TransactionType,
} from '../api/types'

/** What a mocked endpoint answers: JSON (status 200 unless given), or a thrown network error. */
export type MockAnswer = { status?: number; body?: unknown } | 'network-error'
type Handler = MockAnswer | ((body: unknown, query: URLSearchParams) => MockAnswer | Promise<MockAnswer>)

/**
 * Replace `fetch` with fake endpoints, keyed by "METHOD /path" (shop 1, query string ignored).
 * Returns the list of requests made, with their parsed JSON bodies and query parameters.
 */
export function mockApi(handlers: Record<string, Handler>) {
  const requests: { key: string; body: unknown; query: URLSearchParams }[] = []
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const { pathname: path, searchParams: query } = new URL(url)
    const key = `${init.method ?? 'GET'} ${path}`
    // FormData (an audio upload) is passed through as is; JSON is parsed.
    const body = init.body instanceof FormData ? init.body : init.body ? JSON.parse(String(init.body)) : undefined
    requests.push({ key, body, query })
    const handler = handlers[key] ?? { status: 404, body: { detail: `No mock for ${key}` } }
    const answer = await (typeof handler === 'function' ? handler(body, query) : handler)
    if (answer === 'network-error') throw new TypeError('Failed to fetch')
    if (answer.status === 204) return new Response(null, { status: 204 })
    return new Response(JSON.stringify(answer.body ?? null), {
      status: answer.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    requests,
    bodiesOf: (key: string) => requests.filter((r) => r.key === key).map((r) => r.body),
    queriesOf: (key: string) => requests.filter((r) => r.key === key).map((r) => Object.fromEntries(r.query)),
  }
}

export const PARSE = 'POST /shops/1/parse'
export const CONFIRM = 'POST /shops/1/parse/confirm'
export const RECENT = 'GET /shops/1/transactions'
export const CUSTOMERS = 'GET /shops/1/customers'
export const DASHBOARD = 'GET /shops/1/dashboard'
export const ledgerKey = (customerId: number) => `GET /shops/1/customers/${customerId}/transactions`
export const addKey = (customerId: number) => `POST /shops/1/customers/${customerId}/transactions`
export const reminderKey = (customerId: number) => `POST /shops/1/customers/${customerId}/reminder`
export const patchKey = (id: number) => `PATCH /shops/1/transactions/${id}`
export const deleteKey = (id: number) => `DELETE /shops/1/transactions/${id}`
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

export function listItem(
  id: number,
  name: string,
  balance: number,
  {
    note = null,
    phone = null,
    owedSince = null,
  }: { note?: string | null; phone?: string | null; owedSince?: string | null } = {},
): CustomerListItem {
  return { ...customer(id, name, balance, note), phone, owed_since: owedSince }
}

export function ledgerEntry(
  id: number,
  type: TransactionType,
  amount: number,
  runningBalance: number,
  {
    item = null,
    rawText = null,
    createdAt = NOW,
  }: { item?: string | null; rawText?: string | null; createdAt?: string } = {},
): LedgerEntry {
  return {
    id,
    shop_id: 1,
    customer_id: 7,
    type,
    amount,
    item,
    raw_text: rawText,
    created_at: createdAt,
    running_balance: runningBalance,
  }
}

export function ledgerPage(who: Customer, rows: LedgerEntry[], total = rows.length, hasMore = false): CustomerLedger {
  return { customer: who, transactions: rows, total, has_more: hasMore }
}
