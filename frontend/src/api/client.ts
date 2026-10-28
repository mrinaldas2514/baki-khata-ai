import { API_URL } from '../config'
import { currentShopId, endSession, getSession } from '../session'
import type {
  AuthResult,
  Customer,
  CustomerInput,
  CustomerLedger,
  CustomerListItem,
  Dashboard,
  ParseConfirm,
  ParseConfirmResult,
  ParsePreview,
  RecentTransaction,
  RegisterInput,
  Reminder,
  TransactionInput,
  TransactionWithBalance,
  TranscribeResult,
  TranscribeStatus,
  User,
} from './types'

// The AI can take a while on a slow connection (the backend waits up to 20 s and retries once).
const TIMEOUT_MS = 45_000

export interface FieldError {
  field: string | null
  message: string
}

/** `kind: 'network'`: no answer at all (offline, server down, timeout). Otherwise `status` is set. */
export class ApiError extends Error {
  readonly kind: 'network' | 'http'
  readonly status: number | null
  readonly fieldErrors: FieldError[]
  /** Seconds to wait, after a 429 (too many tries). */
  readonly retryAfter: number | null

  constructor(
    kind: 'network' | 'http',
    status: number | null,
    message: string,
    fieldErrors: FieldError[] = [],
    retryAfter: number | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.fieldErrors = fieldErrors
    this.retryAfter = retryAfter
  }
}

// A 401 from these means "wrong password", not "the login ended".
const NO_LOGOUT_ON_401 = new Set(['/auth/login', '/auth/register'])

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getSession()?.token
  const headers = new Headers(init.headers)
  // A FormData body (audio upload) sets its own multipart Content-Type.
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers, signal: AbortSignal.timeout(TIMEOUT_MS) })
  } catch (error) {
    throw new ApiError('network', null, error instanceof Error ? error.message : String(error))
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    // The login expired, was logged out elsewhere, or the account is gone: back to the login screen.
    if (response.status === 401 && token && !NO_LOGOUT_ON_401.has(path)) endSession('expired')
    throw new ApiError(
      'http',
      response.status,
      body?.detail ?? response.statusText,
      body?.errors ?? [],
      body?.retry_after ?? null,
    )
  }
  return response
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await send(path, init)
  // 204 No Content (a delete) has no body.
  return (response.status === 204 ? undefined : await response.json()) as T
}

/** The logged-in shopkeeper's shop; every shop URL is built when the request is made. */
const shopPath = () => `/shops/${currentShopId()}`

export const api = {
  register: (data: RegisterInput) =>
    request<AuthResult>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  /** `login` is a phone number (any format) or an email. */
  login: (login: string, password: string) =>
    request<AuthResult>('/auth/login', { method: 'POST', body: JSON.stringify({ login, password }) }),

  /** The token stops working on the server too. */
  logout: () => request<void>('/auth/logout', { method: 'POST' }),

  me: () => request<User>('/auth/me'),

  /** "AI bondho rakhun": false means nothing is sent to the AI provider. */
  setAiEnabled: (aiEnabled: boolean) =>
    request<User>('/auth/me', { method: 'PATCH', body: JSON.stringify({ ai_enabled: aiEnabled }) }),

  /** Deletes the account, the shop and every customer and entry. Needs the password. */
  deleteAccount: (password: string) =>
    request<void>('/auth/me', { method: 'DELETE', body: JSON.stringify({ password }) }),

  /** The whole khata as a CSV file (UTF-8 with BOM, for Excel). */
  exportCsv: async (): Promise<{ blob: Blob; filename: string }> => {
    const response = await send(`${shopPath()}/export.csv`)
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'baki-khata.csv'
    return { blob: await response.blob(), filename }
  },

  /** Turn a sentence into a preview. Saves nothing. */
  parse: (text: string) =>
    request<ParsePreview>(`${shopPath()}/parse`, { method: 'POST', body: JSON.stringify({ text }) }),

  /** Save a (possibly edited) entry, creating the customer if it's new. */
  confirm: (data: ParseConfirm) =>
    request<ParseConfirmResult>(`${shopPath()}/parse/confirm`, { method: 'POST', body: JSON.stringify(data) }),

  recentTransactions: (limit = 10) => request<RecentTransaction[]>(`${shopPath()}/transactions?limit=${limit}`),

  customers: () => request<CustomerListItem[]>(`${shopPath()}/customers`),

  createCustomer: (data: CustomerInput) =>
    request<Customer>(`${shopPath()}/customers`, { method: 'POST', body: JSON.stringify(data) }),

  /** Only the fields given change. */
  updateCustomer: (id: number, data: Partial<CustomerInput>) =>
    request<Customer>(`${shopPath()}/customers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  /** Only works for a customer with no entries (409 otherwise): used by Undo. */
  deleteCustomer: (id: number) => request<void>(`${shopPath()}/customers/${id}`, { method: 'DELETE' }),

  /** One page of a customer's khata, newest first, each row with the balance right after it. */
  ledger: (customerId: number, { limit, offset = 0 }: { limit: number; offset?: number }) =>
    request<CustomerLedger>(
      `${shopPath()}/customers/${customerId}/transactions?order=newest&limit=${limit}&offset=${offset}`,
    ),

  addTransaction: (customerId: number, data: TransactionInput) =>
    request<TransactionWithBalance>(`${shopPath()}/customers/${customerId}/transactions`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateTransaction: (id: number, data: Partial<TransactionInput>) =>
    request<TransactionWithBalance>(`${shopPath()}/transactions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteTransaction: (id: number) => request<void>(`${shopPath()}/transactions/${id}`, { method: 'DELETE' }),

  dashboard: () => request<Dashboard>(`${shopPath()}/dashboard`),

  /** A polite reminder message for the customer's baki. Nothing is sent: the shopkeeper sends it. */
  reminder: (customerId: number) =>
    request<Reminder>(`${shopPath()}/customers/${customerId}/reminder`, { method: 'POST', body: '{}' }),

  /** Whether the server can turn recordings into text (it needs a Groq key), and its limits. */
  transcribeStatus: () => request<TranscribeStatus>('/transcribe/status'),

  /** A short recording -> text for the entry box (then checked and sent to `parse` as usual). */
  transcribe: (audio: Blob, language: string) => {
    const form = new FormData()
    form.append('file', audio, 'voice')
    form.append('language', language)
    return request<TranscribeResult>('/transcribe', { method: 'POST', body: form })
  },
}
