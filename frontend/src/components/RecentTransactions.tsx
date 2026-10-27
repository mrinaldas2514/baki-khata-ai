import type { RecentTransaction } from '../api/types'
import { formatTaka, formatWhen } from '../format'
import { href } from '../route'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'
import { Button, TypeBadge } from './ui'

interface Props {
  transactions: RecentTransaction[] | null
  failed?: boolean
  onRetry?: () => void
  /** Briefly highlighted, e.g. the entry that was just saved. */
  highlightId?: number | null
}

export function RecentTransactions({ transactions, failed = false, onRetry, highlightId }: Props) {
  return (
    <section aria-labelledby="recent-title" className="flex flex-col gap-3">
      <h2 id="recent-title" className="text-xl font-bold text-stone-800">
        {strings.recentTitle}
      </h2>
      {failed ? (
        <div className="flex flex-col gap-3 rounded-2xl bg-white p-4">
          <p className="text-lg text-stone-700">{strings.recentFailed}</p>
          {onRetry && (
            <Button variant="secondary" onClick={onRetry}>
              {strings.retry}
            </Button>
          )}
        </div>
      ) : transactions === null ? (
        <p className="text-lg text-stone-600" role="status">
          {strings.loading}
        </p>
      ) : transactions.length === 0 ? (
        <p className="rounded-2xl bg-white p-4 text-lg text-stone-600">{strings.recentEmpty}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-stone-200 overflow-hidden rounded-2xl bg-white">
          {transactions.map((txn) => (
            <li key={txn.id}>
              <a
                href={href.khata(txn.customer_id)}
                className={`flex min-h-16 items-center justify-between gap-3 px-4 py-3 active:bg-stone-100 ${txn.id === highlightId ? 'bg-emerald-50' : ''}`}
              >
                <div className="min-w-0">
                  <p className="truncate text-lg font-semibold text-stone-900">
                    {txn.customer_name}
                    {txn.customer_note && (
                      <>
                        {' '}
                        <span className="font-normal text-stone-500">({txn.customer_note})</span>
                      </>
                    )}
                  </p>
                  <p className="truncate text-base text-stone-600">
                    {formatWhen(txn.created_at)}
                    {txn.item && ` · ${txn.item}`}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className={`text-xl font-bold tabular-nums ${TYPE_STYLES[txn.type].text}`}>
                    {formatTaka(txn.amount)}
                  </span>
                  <TypeBadge type={txn.type} />
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
