import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { Customer, TransactionType } from '../api/types'
import type { CustomerChoice, Draft, FormValues } from '../entry'
import { parseAmount } from '../format'
import { cachedCustomers } from '../offline/customerCache'
import { currentShopId } from '../session'
import { strings } from '../strings'
import { CustomerOption } from './CustomerSummary'
import { Alert, AmountInput, Button, TypeToggle, inputClass } from './ui'

interface Props {
  title: string
  rawText: string
  initial: FormValues
  /** Customers to offer before the full list has loaded (e.g. the AI's candidates). */
  suggestions?: Customer[]
  /** Why the form is shown, e.g. "AI bujhte pareni. Niche nije likhe din." */
  notice?: string | null
  onSave: (draft: Draft) => void
  onCancel: () => void
  saving?: boolean
  error?: string | null
}

const MAX_MATCHES = 5
const NO_CUSTOMERS: Customer[] = []

const normalize = (text: string) => text.trim().toLowerCase().replace(/\s+/g, ' ')

/** Edit mode and manual entry: customer, amount, type and item, all correctable. */
export function EntryForm({
  title,
  rawText,
  initial,
  suggestions = NO_CUSTOMERS,
  notice,
  onSave,
  onCancel,
  saving = false,
  error,
}: Props) {
  const [name, setName] = useState(() => {
    if (initial.choice?.kind === 'existing') return initial.choice.customer.name
    if (initial.choice?.kind === 'new') return initial.choice.name
    return initial.name
  })
  const [picked, setPicked] = useState<Customer | null>(
    initial.choice?.kind === 'existing' ? initial.choice.customer : null,
  )
  const [note, setNote] = useState('')
  const [amountText, setAmountText] = useState(initial.amount ? String(initial.amount) : '')
  const [type, setType] = useState<TransactionType>(initial.type)
  const [item, setItem] = useState(initial.item ?? '')
  const [problems, setProblems] = useState<{ name?: string; amount?: string }>({})
  const [loaded, setLoaded] = useState<Customer[]>([])

  useEffect(() => {
    let active = true
    // Offline: the list kept on the phone. Without any list the form still works: the name
    // just becomes a new customer.
    api.customers().then(
      (customers) => active && setLoaded(customers),
      () => active && setLoaded(cachedCustomers(currentShopId())),
    )
    return () => {
      active = false
    }
  }, [])

  const allCustomers = useMemo(() => {
    const byId = new Map<number, Customer>()
    for (const customer of [...suggestions, ...loaded]) byId.set(customer.id, customer)
    return [...byId.values()]
  }, [suggestions, loaded])

  const query = normalize(name)
  const matches = useMemo(() => {
    if (!query) return []
    const found = allCustomers.filter((c) => normalize(c.name).includes(query) || query.includes(normalize(c.name)))
    return found.slice(0, MAX_MATCHES)
  }, [allCustomers, query])
  const sameNameExists = !picked && query !== '' && allCustomers.some((c) => normalize(c.name) === query)

  function changeName(text: string) {
    setName(text)
    // Typing a different name means a different (possibly new) customer.
    if (picked && normalize(text) !== normalize(picked.name)) setPicked(null)
  }

  function pick(customer: Customer) {
    setPicked(customer)
    setName(customer.name)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const amount = parseAmount(amountText)
    const found = {
      name: picked || name.trim() ? undefined : strings.nameRequired,
      amount: amount === null ? strings.amountInvalid : undefined,
    }
    setProblems(found)
    if (found.name || found.amount || amount === null) return
    const choice: CustomerChoice = picked
      ? { kind: 'existing', customer: picked }
      : { kind: 'new', name: name.trim(), note: note.trim() || null }
    onSave({ choice, amount, type, item: item.trim() || null })
  }

  return (
    <section aria-labelledby="entry-form-title" className="rounded-3xl bg-white p-4 shadow-md">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        <div>
          <h2 id="entry-form-title" className="text-2xl font-bold text-stone-900">
            {title}
          </h2>
          {rawText && (
            <p className="text-base text-stone-600">
              {strings.youWrote}: “{rawText}”
            </p>
          )}
        </div>
        {notice && <Alert tone="warning">{notice}</Alert>}

        <div className="flex flex-col gap-2">
          <label htmlFor="entry-name" className="text-xl font-semibold text-stone-900">
            {strings.customer}
          </label>
          <input
            id="entry-name"
            value={name}
            onChange={(event) => changeName(event.target.value)}
            placeholder={strings.customerNamePlaceholder}
            autoComplete="off"
            aria-invalid={Boolean(problems.name)}
            className={inputClass}
          />
          {problems.name && <p className="text-lg text-red-700">{problems.name}</p>}
          {matches.length > 0 && (
            <div className="flex flex-col gap-2" role="group" aria-label={strings.existingCustomer}>
              {matches.map((customer) => (
                <CustomerOption
                  key={customer.id}
                  customer={customer}
                  selected={picked?.id === customer.id}
                  onSelect={() => pick(customer)}
                />
              ))}
            </div>
          )}
          {!picked && query && (
            <p className="rounded-xl bg-sky-50 px-3 py-2 text-lg font-semibold text-sky-900">
              {strings.newCustomerNamed(name.trim())}
            </p>
          )}
          {sameNameExists && (
            <>
              <p className="text-base text-amber-900">{strings.sameNameExists}</p>
              <input
                aria-label={strings.note}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={strings.note}
                className={inputClass}
              />
            </>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="entry-amount" className="text-xl font-semibold text-stone-900">
            {strings.amount}
          </label>
          <AmountInput
            id="entry-amount"
            value={amountText}
            onChange={setAmountText}
            invalid={Boolean(problems.amount)}
          />
          {problems.amount && <p className="text-lg text-red-700">{problems.amount}</p>}
        </div>

        <TypeToggle name="entry-type" value={type} onChange={setType} />

        <div className="flex flex-col gap-2">
          <label htmlFor="entry-item" className="text-xl font-semibold text-stone-900">
            {strings.item}
          </label>
          <input
            id="entry-item"
            value={item}
            onChange={(event) => setItem(event.target.value)}
            maxLength={200}
            autoComplete="off"
            className={inputClass}
          />
        </div>

        {error && <Alert>{error}</Alert>}

        <div className="flex flex-col gap-3">
          <Button type="submit" disabled={saving}>
            {saving ? strings.saving : strings.save}
          </Button>
          <Button variant="danger" onClick={onCancel} disabled={saving}>
            {strings.cancel}
          </Button>
        </div>
      </form>
    </section>
  )
}
