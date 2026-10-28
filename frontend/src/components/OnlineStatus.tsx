import { useOnline } from '../offline/online'
import { useQueue } from '../offline/queue'
import { strings } from '../strings'

/** In the title bar: "● Online" / "● Offline", and how many entries are still on the phone. */
export function OnlineStatus() {
  const online = useOnline()
  const { items, syncing } = useQueue()
  const pending = items.length
  return (
    // A polite live region (not role="status"): screen readers hear "Offline" when it happens.
    <p
      aria-live="polite"
      data-testid="online-status"
      data-online={online}
      className={`flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold ${
        online ? 'bg-emerald-950 text-emerald-50' : 'bg-amber-300 text-amber-950'
      }`}
    >
      <span aria-hidden className={`size-2.5 rounded-full ${online ? 'bg-emerald-400' : 'bg-amber-800'}`} />
      <span className="sr-only">{strings.offline.statusLabel(online, pending)}</span>
      <span aria-hidden>
        {syncing ? strings.offline.syncing : online ? strings.offline.online : strings.offline.offline}
        {pending > 0 && !syncing && ` · ${strings.offline.pendingCount(pending)}`}
      </span>
    </p>
  )
}
