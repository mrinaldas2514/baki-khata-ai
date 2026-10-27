import type { ParseConfirmResult } from '../api/types'
import { describeBalance, formatTaka } from '../format'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'
import { Button } from './ui'

/** Shown after saving: what was saved and the customer's new balance. */
export function SavedMessage({ result, onClose }: { result: ParseConfirmResult; onClose: () => void }) {
  const { transaction, customer } = result
  const style = TYPE_STYLES[transaction.type]
  return (
    <section role="status" className="flex flex-col gap-3 rounded-3xl border-2 border-emerald-500 bg-emerald-50 p-4">
      <p className="text-2xl font-bold text-emerald-800">✓ {strings.savedTitle}</p>
      <p className="text-xl text-stone-800">
        {customer.name}: <span className={`font-bold ${style.text}`}>{formatTaka(transaction.amount)}</span>{' '}
        {style.label}
      </p>
      {result.customer_created && <p className="text-lg text-stone-700">{strings.savedNewCustomer(customer.name)}</p>}
      <div className="rounded-2xl bg-white px-4 py-3">
        <p className="text-lg text-stone-600">{strings.newBalanceOf(customer.name)}</p>
        <p className="text-3xl font-bold text-stone-900" data-testid="new-balance">
          {describeBalance(customer.balance)}
        </p>
      </div>
      <Button variant="secondary" onClick={onClose}>
        {strings.close}
      </Button>
    </section>
  )
}
