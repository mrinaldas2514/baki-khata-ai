import type { Customer, CustomerCandidate, EntryPreview, ParsePreview } from '../api/types'
import { searchKey } from '../customers'
import { type RulesEntry, cleanName, nameWords, parseText } from './rules'

/** The "model" of an offline reading: the rule-based parser, on the phone. */
export const OFFLINE_MODEL = 'rule-based (offline)'

// The backend's limits for an entry (backend/app/schemas: Amount, Name).
const MAX_AMOUNT = 10_000_000
const MAX_NAME = 100

const nameKey = (name: string) => searchKey(nameWords(name).join(' '))

/**
 * Who the name is, from the phone's last customer list: one customer with the same name
 * (ignoring honorifics, script and Banglish spelling), several (the shopkeeper picks), or none
 * (a new customer). Simpler than the server's matching: no "close enough" guesses offline.
 */
function match(name: string, customers: Customer[]): EntryPreview['match'] {
  const key = nameKey(name)
  const same: CustomerCandidate[] = customers
    .filter((customer) => key && nameKey(customer.name) === key)
    .map((customer) => ({ ...customer, score: 100 }))
  const suggested = cleanName(name)
  if (same.length === 1) return { status: 'exact', customer: same[0], candidates: same, suggested_name: suggested }
  if (same.length > 1) return { status: 'ambiguous', customer: null, candidates: same, suggested_name: suggested }
  return { status: 'new', customer: null, candidates: [], suggested_name: suggested }
}

function valid(entry: RulesEntry): boolean {
  const name = entry.customer_name.trim()
  return name.length > 0 && name.length <= MAX_NAME && entry.amount >= 1 && entry.amount <= MAX_AMOUNT
}

/**
 * The sentence read on the phone, shaped like the server's /parse answer (parser "rules").
 * Null when the rules can't find a customer and an amount: the manual form opens instead.
 */
export function localPreview(text: string, customers: Customer[]): ParsePreview | null {
  const answer = parseText(text)
  if ('error' in answer) return null
  const parsed = 'entries' in answer ? answer.entries : [answer]
  if (!parsed.every(valid)) return null
  const entries: EntryPreview[] = parsed.map((entry) => ({
    parsed: { ...entry, customer_name: entry.customer_name.trim() },
    match: match(entry.customer_name, customers),
    warnings: [],
  }))
  return { raw_text: text, ...entries[0], entries, parser: 'rules', model: OFFLINE_MODEL }
}
