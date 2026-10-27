import { API_URL, SHOP_ID } from '../config'
import type {
  Customer,
  ParseConfirm,
  ParseConfirmResult,
  ParsePreview,
  RecentTransaction,
  TranscribeResult,
  TranscribeStatus,
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

  constructor(kind: 'network' | 'http', status: number | null, message: string, fieldErrors: FieldError[] = []) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      // A FormData body (audio upload) sets its own multipart Content-Type.
      headers: init.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init.headers },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch (error) {
    throw new ApiError('network', null, error instanceof Error ? error.message : String(error))
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError('http', response.status, body?.detail ?? response.statusText, body?.errors ?? [])
  }
  return (await response.json()) as T
}

const shop = `/shops/${SHOP_ID}`

export const api = {
  /** Turn a sentence into a preview. Saves nothing. */
  parse: (text: string) => request<ParsePreview>(`${shop}/parse`, { method: 'POST', body: JSON.stringify({ text }) }),

  /** Save a (possibly edited) entry, creating the customer if it's new. */
  confirm: (data: ParseConfirm) =>
    request<ParseConfirmResult>(`${shop}/parse/confirm`, { method: 'POST', body: JSON.stringify(data) }),

  recentTransactions: (limit = 10) => request<RecentTransaction[]>(`${shop}/transactions?limit=${limit}`),

  customers: () => request<Customer[]>(`${shop}/customers`),

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
