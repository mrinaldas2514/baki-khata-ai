/** Shapes of the backend's JSON (see backend/app/schemas). Amounts are whole taka. */

export type TransactionType = 'credit' | 'payment'

export interface Shop {
  id: number
  name: string
  owner_name: string
  created_at: string
}

/** The logged-in shopkeeper. */
export interface User {
  id: number
  name: string
  /** Normalized: +8801711000001 / +919876543210. */
  phone: string | null
  email: string | null
  shop: Shop
  /** False: "AI bondho" — nothing is sent to the AI provider. */
  ai_enabled: boolean
  consent_version: string
  consent_at: string
  created_at: string
}

export interface AuthResult {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: User
}

export interface RegisterInput {
  name: string
  shop_name: string
  phone: string | null
  email: string | null
  password: string
  consent: boolean
  consent_version: string
}

/** Create or edit a customer. */
export interface CustomerInput {
  name: string
  phone: string | null
  note: string | null
}

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

/** A row of the customer list. */
export interface CustomerListItem extends Customer {
  /** When the oldest still-unpaid credit was given. Null when nothing is owed. */
  owed_since: string | null
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

export interface LedgerEntry extends Transaction {
  /** The customer's balance right after this transaction. */
  running_balance: number
}

/** One page of a customer's khata. */
export interface CustomerLedger {
  customer: Customer
  transactions: LedgerEntry[]
  total: number
  has_more: boolean
}

export interface TransactionWithBalance extends Transaction {
  customer_balance: number
}

export interface TransactionInput {
  type: TransactionType
  amount: number
  item: string | null
  raw_text?: string | null
  /** When it happened (ISO). Left out: now (adding) or unchanged (editing). */
  created_at?: string
}

export interface CustomerBalanceSummary {
  id: number
  name: string
  phone: string | null
  note: string | null
  balance: number
}

export interface OverdueCustomer extends CustomerBalanceSummary {
  owed_since: string
  days_outstanding: number
}

export interface DaySummary {
  /** The shop's local date, YYYY-MM-DD. */
  date: string
  credit: number
  payment: number
}

export interface Dashboard {
  total_outstanding: number
  customers_with_baki: number
  today: string
  today_collection: number
  today_new_credit: number
  top_customers: CustomerBalanceSummary[]
  overdue_days: number
  overdue_customers: OverdueCustomer[]
  /** Oldest first, ending with today. */
  last_7_days: DaySummary[]
}

export interface Reminder {
  message: string
  polished: boolean
  phone: string | null
  /** Digits only, with the country code, for https://wa.me/<number>. Null without a usable phone. */
  whatsapp_number: string | null
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
