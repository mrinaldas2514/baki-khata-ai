/** Shapes of the backend's JSON (see backend/app/schemas). Amounts are whole taka. */

export type TransactionType = 'credit' | 'payment'

export interface Customer {
  id: number
  shop_id: number
  name: string
  phone: string | null
  note: string | null
  created_at: string
  /** Credit minus payments. Positive: owes the shop. Negative: paid in advance. */
  balance: number
}

export interface CustomerCandidate extends Customer {
  score: number
}

export type MatchStatus = 'exact' | 'fuzzy' | 'ambiguous' | 'new'

export interface ParsePreview {
  raw_text: string
  parsed: {
    customer_name: string
    amount: number
    type: TransactionType
    item: string | null
    confidence: number
  }
  match: {
    status: MatchStatus
    customer: CustomerCandidate | null
    candidates: CustomerCandidate[]
    suggested_name: string
  }
  warnings: string[]
}

export interface Transaction {
  id: number
  shop_id: number
  customer_id: number
  type: TransactionType
  amount: number
  item: string | null
  raw_text: string | null
  created_at: string
}

export interface RecentTransaction extends Transaction {
  customer_name: string
  customer_note: string | null
}

export interface ParseConfirm {
  raw_text: string
  type: TransactionType
  amount: number
  item: string | null
  customer_id?: number
  new_customer?: { name: string; note?: string | null }
}

export interface ParseConfirmResult {
  transaction: Transaction & { customer_balance: number }
  customer: Customer
  customer_created: boolean
}

export interface TranscribeResult {
  /** Empty when no speech was heard. */
  text: string
}

export interface TranscribeStatus {
  available: boolean
  max_seconds: number
  max_bytes: number
}
