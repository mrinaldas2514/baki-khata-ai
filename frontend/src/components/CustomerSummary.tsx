import type { Customer } from '../api/types'
import { describeBalance } from '../format'
import { strings } from '../strings'

/** "Rahim (Bazar road) · Ekhon: Baki ৳300", or "Notun customer: Tanvir". */
export function CustomerSummary({ customer, newName }: { customer?: Customer; newName?: string }) {
  if (customer) {
    return (
      <div className="rounded-2xl border-2 border-stone-200 bg-stone-50 px-4 py-3" data-testid="customer-summary">
        <p className="text-2xl font-bold text-stone-900">
          {customer.name}
          {customer.note && (
            <>
              {' '}
              <span className="text-lg font-normal text-stone-600">({customer.note})</span>
            </>
          )}
        </p>
        <p className="text-lg text-stone-700">
          {strings.currentBalance}: <span className="font-semibold">{describeBalance(customer.balance)}</span>
        </p>
      </div>
    )
  }
  return (
    <div
      className="rounded-2xl border-2 border-dashed border-sky-500 bg-sky-50 px-4 py-3"
      data-testid="customer-summary"
    >
      <p className="text-2xl font-bold text-stone-900">{strings.newCustomerNamed(newName ?? '')}</p>
      <p className="text-base text-sky-900">{strings.newCustomerHint}</p>
    </div>
  )
}

/** One large button per customer, to pick between look-alikes ("Rahim (Bazar road)" / "Rahim (Tea stall)"). */
export function CustomerOption({
  customer,
  selected,
  onSelect,
}: {
  customer: Customer
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex min-h-16 w-full flex-col items-start justify-center rounded-2xl border-2 px-4 py-2 text-left transition-colors ${
        selected
          ? 'border-emerald-600 bg-emerald-50 ring-2 ring-emerald-600'
          : 'border-stone-300 bg-white active:bg-stone-100'
      }`}
    >
      <span className="text-xl font-semibold text-stone-900">
        {selected && '✓ '}
        {customer.name}
        {customer.note && (
          <>
            {' '}
            <span className="font-normal text-stone-600">({customer.note})</span>
          </>
        )}
      </span>{' '}
      <span className="text-base text-stone-600">{describeBalance(customer.balance)}</span>
    </button>
  )
}

export function NewCustomerOption({
  name,
  selected,
  onSelect,
}: {
  name: string
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex min-h-16 w-full items-center rounded-2xl border-2 border-dashed px-4 py-2 text-left text-xl font-semibold transition-colors ${
        selected
          ? 'border-sky-600 bg-sky-50 ring-2 ring-sky-600'
          : 'border-sky-400 bg-white text-sky-900 active:bg-sky-50'
      }`}
    >
      {selected && '✓ '}+ {strings.newCustomerNamed(name)}
    </button>
  )
}
