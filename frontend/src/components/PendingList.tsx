import { formatTaka, formatWhen } from '../format'
import { useOnline } from '../offline/online'
import { type QueuedSave, discard, syncQueue, useQueue } from '../offline/queue'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'
import { Button, TypeBadge } from './ui'

/**
 * Entries saved on the phone that haven't reached the server yet, above the recent list.
 * Each shows "Pending sync"; one the server refused shows why, with "Bad din" to drop it.
 */
export function PendingList({ shopId }: { shopId: number }) {
  const { items, syncing } = useQueue()
  const online = useOnline()
  if (items.length === 0) return null
  const anyPending = items.some((item) => item.status === 'pending')

  return (
    <section aria-labelledby="pending-title" className="flex flex-col gap-3">
      <h2 id="pending-title" className="text-xl font-bold text-amber-900">
        ⏳ {strings.offline.pendingTitle(items.length)}
      </h2>
      <ul className="flex flex-col divide-y divide-amber-200 overflow-hidden rounded-2xl border-2 border-amber-300 bg-white">
        {items.map((item) => (
          <PendingItem key={item.key} item={item} onDiscard={() => discard(shopId, item.key)} />
        ))}
      </ul>
      {online && anyPending && (
        <Button variant="secondary" onClick={() => syncQueue(shopId)} disabled={syncing}>
          {syncing ? strings.offline.syncing : strings.offline.syncNow}
        </Button>
      )}
    </section>
  )
}

function PendingItem({ item, onDiscard }: { item: QueuedSave; onDiscard: () => void }) {
  const failed = item.status === 'failed'
  return (
    <li className="flex flex-col gap-2 px-4 py-3" data-testid="pending-item">
      {item.summary.map((entry, i) => (
        <div key={i} className="flex items-center justify-between gap-3">
          <p className="min-w-0 truncate text-lg font-semibold text-stone-900">{entry.name}</p>
          <div className="flex shrink-0 items-center gap-2">
            <span className={`text-xl font-bold tabular-nums ${TYPE_STYLES[entry.type].text}`}>
              {formatTaka(entry.amount)}
            </span>
            <TypeBadge type={entry.type} />
          </div>
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full border px-2.5 py-0.5 text-sm font-bold ${
            failed ? 'border-red-300 bg-red-50 text-red-800' : 'border-amber-400 bg-amber-50 text-amber-900'
          }`}
        >
          {failed ? `⚠ ${strings.offline.failedBadge}` : `⏳ ${strings.offline.pendingBadge}`}
        </span>
        <span className="text-base text-stone-600">{strings.offline.savedAt(formatWhen(item.savedAt))}</span>
      </div>
      {failed && (
        <>
          <p className="text-base text-red-800">{item.error}</p>
          <Button
            variant="danger"
            onClick={onDiscard}
            aria-label={strings.offline.discardLabel(item.summary.map((e) => e.name).join(', '))}
          >
            {strings.offline.discard}
          </Button>
        </>
      )}
    </li>
  )
}
