import type { Customer, EntryPreview, ParseConfirm, ParsePreview, TransactionType } from './api/types'

/** Who the entry is for: someone already in the khata, or a customer to create on save. */
export type CustomerChoice =
  { kind: 'existing'; customer: Customer } | { kind: 'new'; name: string; note?: string | null }

/** A ready-to-save entry, from the confirmation card or the edit / manual form. */
export interface Draft {
  choice: CustomerChoice
  amount: number
  type: TransactionType
  item: string | null
}

/** exact / fuzzy: the matched customer. new: create the suggested name. ambiguous: ask. */
/** What the edit / manual form starts with. */
export interface FormValues {
  name: string
  choice: CustomerChoice | null
  amount: number | null
  type: TransactionType
  item: string | null
}

export const EMPTY_FORM: FormValues = { name: '', choice: null, amount: null, type: 'credit', item: null }

export function initialChoice(preview: EntryPreview): CustomerChoice | null {
  const { match } = preview
  if ((match.status === 'exact' || match.status === 'fuzzy') && match.customer) {
    return { kind: 'existing', customer: match.customer }
  }
  if (match.status === 'new') return { kind: 'new', name: match.suggested_name }
  return null
}

export function toConfirmRequest(rawText: string, draft: Draft): ParseConfirm {
  const base = { raw_text: rawText, type: draft.type, amount: draft.amount, item: draft.item }
  return draft.choice.kind === 'existing'
    ? { ...base, customer_id: draft.choice.customer.id }
    : { ...base, new_customer: { name: draft.choice.name, note: draft.choice.note || null } }
}

/** Who read the sentence, for the "AI" / "AI chhara" label. */
export type ReadBy = Pick<ParsePreview, 'parser' | 'model'>

/** One card of a sentence about several customers, as the shopkeeper has it now. */
export interface MultiItem {
  key: number
  /** What the AI understood (for the customer candidates and the suggested name). */
  entry: EntryPreview
  amount: number
  type: Draft['type']
  item: string | null
  /** Null until the shopkeeper picks between look-alikes. */
  choice: CustomerChoice | null
  editing: boolean
}

export function toMultiItems(entries: EntryPreview[]): MultiItem[] {
  return entries.map((entry, key) => ({
    key,
    entry,
    amount: entry.parsed.amount,
    type: entry.parsed.type,
    item: entry.parsed.item,
    choice: initialChoice(entry),
    editing: false,
  }))
}

export function toDraft(item: MultiItem): Draft | null {
  return item.choice && { choice: item.choice, amount: item.amount, type: item.type, item: item.item }
}
