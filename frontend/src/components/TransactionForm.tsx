import { type FormEvent, useState } from 'react'
import type { TransactionInput, TransactionType } from '../api/types'
import { moveToDate, parseAmount, toDateInput } from '../format'
import { strings } from '../strings'
import { Alert, AmountInput, Button, TypeToggle, inputClass } from './ui'

interface Props {
  /** `created_at` when editing an entry; a new one starts on today. */
  initial: { type: TransactionType; amount: number | null; item: string | null; created_at?: string }
  /** The sentence the entry was saved from, shown so the shopkeeper remembers it. */
  rawText?: string | null
  saving: boolean
  error?: string | null
  onSave: (values: TransactionInput) => void
  onCancel: () => void
  /** Only when editing: offers "Muche felun". */
  onDelete?: () => void
}

/** The small form on the khata screen: a quick baki/joma for this customer, or editing one entry. */
export function TransactionForm({ initial, rawText, saving, error, onSave, onCancel, onDelete }: Props) {
  const [type, setType] = useState<TransactionType>(initial.type)
  const [amountText, setAmountText] = useState(initial.amount ? String(initial.amount) : '')
  const [item, setItem] = useState(initial.item ?? '')
  const [amountProblem, setAmountProblem] = useState<string | null>(null)
  // Fixed when the form opens: the entry's own day (or today for a new one), and today.
  const [{ startDay, today }] = useState(() => ({
    startDay: toDateInput(initial.created_at ?? new Date()),
    today: toDateInput(new Date()),
  }))
  const [day, setDay] = useState(startDay)
  const [dayProblem, setDayProblem] = useState<string | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const amount = parseAmount(amountText)
    // Only a changed date is sent: an untouched one keeps the entry's exact time (or "now").
    const moved = day === startDay ? undefined : moveToDate(day, initial.created_at ?? new Date())
    setAmountProblem(amount === null ? strings.amountInvalid : null)
    setDayProblem(moved === null ? strings.dateInvalid : null)
    if (amount === null || moved === null) return
    onSave({ type, amount, item: item.trim() || null, ...(moved && { created_at: moved.toISOString() }) })
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      {rawText && (
        <p className="text-base text-stone-600">
          {strings.youWrote}: “{rawText}”
        </p>
      )}
      <div className="flex flex-col gap-2">
        <label htmlFor="txn-amount" className="text-xl font-semibold text-stone-900">
          {strings.amount}
        </label>
        <AmountInput id="txn-amount" value={amountText} onChange={setAmountText} invalid={Boolean(amountProblem)} />
        {amountProblem && <p className="text-lg text-red-700">{amountProblem}</p>}
      </div>

      <TypeToggle name="txn-type" value={type} onChange={setType} />

      <div className="flex flex-col gap-2">
        <label htmlFor="txn-date" className="text-xl font-semibold text-stone-900">
          {strings.date}
        </label>
        <input
          id="txn-date"
          type="date"
          value={day}
          max={today}
          onChange={(event) => setDay(event.target.value)}
          aria-invalid={Boolean(dayProblem)}
          className={inputClass}
        />
        {dayProblem && <p className="text-lg text-red-700">{dayProblem}</p>}
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="txn-item" className="text-xl font-semibold text-stone-900">
          {strings.item}
        </label>
        <input
          id="txn-item"
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
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          {strings.cancel}
        </Button>
        {onDelete && (
          <Button variant="danger" onClick={onDelete} disabled={saving}>
            {strings.deleteTransaction}
          </Button>
        )}
      </div>
    </form>
  )
}
