import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Customer, LedgerEntry, TransactionInput, TransactionType } from '../api/types'
import { ConfirmDialog, Sheet } from '../components/Dialog'
import { ReminderSheet } from '../components/ReminderSheet'
import { TransactionForm } from '../components/TransactionForm'
import { Alert, Button, TypeBadge } from '../components/ui'
import { saveErrorMessage } from '../errors'
import { describeBalance, formatDateTime, formatTaka } from '../format'
import { href } from '../route'
import { strings } from '../strings'
import { TYPE_STYLES, balanceTone } from '../typeStyles'

/** Rows per "Aro dekhun". */
export const PAGE_SIZE = 20
// The most the backend returns at once; reloading after a change stays within it.
const MAX_PAGE = 200

interface Ledger {
  customer: Customer
  rows: LedgerEntry[]
  total: number
  hasMore: boolean
}

type Panel =
  | { kind: 'add'; type: TransactionType }
  | { kind: 'edit'; entry: LedgerEntry }
  | { kind: 'delete'; entry: LedgerEntry }
  | { kind: 'reminder' }

/** One customer's khata: balance on top, quick baki/joma, reminder, and the full history. */
export function KhataScreen({ customerId }: { customerId: number }) {
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [loadError, setLoadError] = useState<'not-found' | 'failed' | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [moreFailed, setMoreFailed] = useState(false)
  const [panel, setPanel] = useState<Panel | null>(null)
  const [busy, setBusy] = useState(false)
  const [panelError, setPanelError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [highlightId, setHighlightId] = useState<number | null>(null)
  const [refreshFailed, setRefreshFailed] = useState(false)

  /** (Re)load the newest `count` rows. After a change every running balance may be different. */
  const reload = useCallback(
    (count: number) =>
      api
        .ledger(customerId, { limit: Math.min(Math.max(count, PAGE_SIZE), MAX_PAGE) })
        .then((page) =>
          setLedger({ customer: page.customer, rows: page.transactions, total: page.total, hasMore: page.has_more }),
        ),
    [customerId],
  )

  const firstLoad = useCallback(() => {
    reload(PAGE_SIZE).catch((error) =>
      setLoadError(error instanceof ApiError && error.status === 404 ? 'not-found' : 'failed'),
    )
  }, [reload])

  useEffect(() => {
    firstLoad()
  }, [firstLoad])

  async function showMore() {
    if (!ledger) return
    setLoadingMore(true)
    setMoreFailed(false)
    try {
      const page = await api.ledger(customerId, { limit: PAGE_SIZE, offset: ledger.rows.length })
      setLedger((current) => {
        if (!current) return current
        // An entry added elsewhere in the meantime shifts the pages; never show a row twice.
        const seen = new Set(current.rows.map((row) => row.id))
        return {
          customer: page.customer,
          rows: [...current.rows, ...page.transactions.filter((row) => !seen.has(row.id))],
          total: page.total,
          hasMore: page.has_more,
        }
      })
    } catch {
      setMoreFailed(true)
    } finally {
      setLoadingMore(false)
    }
  }

  function open(next: Panel | null) {
    setPanel(next)
    setPanelError(null)
  }

  async function run(action: () => Promise<number | null>, done: string, extraRows: number) {
    if (!ledger) return
    setBusy(true)
    setPanelError(null)
    let id: number | null
    try {
      id = await action()
    } catch (error) {
      setPanelError(panel?.kind === 'delete' ? strings.deleteFailed : saveErrorMessage(error))
      setBusy(false)
      return
    }
    setPanel(null)
    setNotice(done)
    setHighlightId(id)
    setBusy(false)
    try {
      await reload(ledger.rows.length + extraRows)
      setRefreshFailed(false)
    } catch {
      // Saved, but the list on screen is out of date until it loads again.
      setRefreshFailed(true)
    }
  }

  const add = (values: TransactionInput) =>
    run(() => api.addTransaction(customerId, values).then((txn) => txn.id), strings.savedEntry, 1)
  const edit = (entry: LedgerEntry, values: TransactionInput) =>
    run(() => api.updateTransaction(entry.id, values).then((txn) => txn.id), strings.savedEntry, 0)
  const remove = (entry: LedgerEntry) =>
    run(() => api.deleteTransaction(entry.id).then(() => null), strings.deletedEntry, 0)

  if (loadError) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink />
        <div className="flex flex-col gap-3 rounded-2xl bg-white p-4">
          <p className="text-lg text-stone-700">
            {loadError === 'not-found' ? strings.customerNotFound : strings.khataFailed}
          </p>
          {loadError === 'failed' && (
            <Button
              variant="secondary"
              onClick={() => {
                setLoadError(null)
                firstLoad()
              }}
            >
              {strings.retry}
            </Button>
          )}
        </div>
      </div>
    )
  }
  if (!ledger) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink />
        <p role="status" className="text-lg text-stone-600">
          {strings.loading}
        </p>
      </div>
    )
  }

  const { customer, rows, total, hasMore } = ledger
  return (
    <div className="flex flex-col gap-5">
      <BackLink />

      <section aria-labelledby="khata-name" className="flex flex-col gap-4 rounded-3xl bg-white p-4 shadow-md">
        <div>
          <h2 id="khata-name" className="text-3xl font-bold break-words text-stone-900">
            {customer.name}
          </h2>
          {customer.note && <p className="text-lg text-stone-600">{customer.note}</p>}
          {customer.phone ? (
            <a
              href={`tel:${customer.phone}`}
              className="inline-flex min-h-12 items-center text-lg font-semibold text-sky-800 underline underline-offset-4"
            >
              {strings.call(customer.phone)}
            </a>
          ) : (
            <p className="text-base text-stone-500">{strings.noPhone}</p>
          )}
        </div>

        <div
          className={`rounded-2xl border-2 px-4 py-3 ${customer.balance > 0 ? TYPE_STYLES.credit.panel : TYPE_STYLES.payment.panel}`}
        >
          <p className="text-lg text-stone-700">{strings.currentBalance}</p>
          <p className={`text-4xl font-bold tabular-nums ${balanceTone(customer.balance)}`} data-testid="khata-balance">
            {describeBalance(customer.balance)}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Button
            variant="credit"
            className="px-2! whitespace-nowrap"
            onClick={() => open({ kind: 'add', type: 'credit' })}
          >
            {strings.addCredit}
          </Button>
          <Button
            variant="payment"
            className="px-2! whitespace-nowrap"
            onClick={() => open({ kind: 'add', type: 'payment' })}
          >
            {strings.addPayment}
          </Button>
        </div>
        {customer.balance > 0 && (
          <Button variant="whatsapp" onClick={() => open({ kind: 'reminder' })}>
            {strings.sendReminder}
          </Button>
        )}
      </section>

      {notice && (
        <p
          role="status"
          className="rounded-2xl border-2 border-emerald-500 bg-emerald-50 px-4 py-3 text-lg font-semibold text-emerald-900"
        >
          ✓ {notice}
        </p>
      )}

      {refreshFailed && (
        <div className="flex flex-col gap-3">
          <Alert>{strings.khataFailed}</Alert>
          <Button
            variant="secondary"
            onClick={() =>
              reload(rows.length).then(
                () => setRefreshFailed(false),
                () => {},
              )
            }
          >
            {strings.retry}
          </Button>
        </div>
      )}

      <section aria-labelledby="history-title" className="flex flex-col gap-3">
        <div>
          <h2 id="history-title" className="text-xl font-bold text-stone-800">
            {strings.historyTitle}
          </h2>
          {rows.length > 0 && <p className="text-base text-stone-600">{strings.historyHint}</p>}
        </div>
        {rows.length === 0 ? (
          <p className="rounded-2xl bg-white p-4 text-lg text-stone-600">{strings.historyEmpty}</p>
        ) : (
          <ul
            aria-label={strings.historyTitle}
            className="flex flex-col divide-y divide-stone-200 overflow-hidden rounded-2xl bg-white"
          >
            {rows.map((entry) => (
              <EntryRow
                key={entry.id}
                entry={entry}
                highlighted={entry.id === highlightId}
                onSelect={() => open({ kind: 'edit', entry })}
              />
            ))}
          </ul>
        )}
        {rows.length > 0 && rows.length < total && (
          <p className="text-center text-base text-stone-600">{strings.historyCount(rows.length, total)}</p>
        )}
        {hasMore && (
          <Button variant="secondary" onClick={showMore} disabled={loadingMore}>
            {loadingMore ? strings.loadingMore : strings.showMore}
          </Button>
        )}
        {moreFailed && <Alert>{strings.showMoreFailed}</Alert>}
      </section>

      {panel?.kind === 'add' && (
        <Sheet
          title={strings.quickEntryTitle(TYPE_STYLES[panel.type].label, customer.name)}
          onClose={() => !busy && open(null)}
        >
          <TransactionForm
            initial={{ type: panel.type, amount: null, item: null }}
            saving={busy}
            error={panelError}
            onSave={add}
            onCancel={() => open(null)}
          />
        </Sheet>
      )}
      {panel?.kind === 'edit' && (
        <Sheet title={strings.editTransactionTitle} onClose={() => !busy && open(null)}>
          <TransactionForm
            initial={panel.entry}
            rawText={panel.entry.raw_text}
            saving={busy}
            error={panelError}
            onSave={(values) => edit(panel.entry, values)}
            onCancel={() => open(null)}
            onDelete={() => open({ kind: 'delete', entry: panel.entry })}
          />
        </Sheet>
      )}
      {panel?.kind === 'delete' && (
        <ConfirmDialog
          title={strings.deleteConfirmTitle}
          body={strings.deleteConfirmBody(
            formatTaka(panel.entry.amount),
            TYPE_STYLES[panel.entry.type].label,
            formatDateTime(panel.entry.created_at),
          )}
          confirmLabel={strings.deleteConfirmYes}
          cancelLabel={strings.deleteConfirmNo}
          busy={busy}
          busyLabel={strings.deleting}
          error={panelError}
          onConfirm={() => remove(panel.entry)}
          onCancel={() => open(null)}
        />
      )}
      {panel?.kind === 'reminder' && <ReminderSheet customer={customer} onClose={() => open(null)} />}
    </div>
  )
}

function BackLink() {
  return (
    <a
      href={href.customers}
      className="inline-flex min-h-12 items-center gap-2 self-start rounded-xl pr-3 text-lg font-semibold text-emerald-800 active:bg-stone-200"
    >
      <span aria-hidden className="text-2xl">
        ←
      </span>
      {strings.backToCustomers}
    </a>
  )
}

/** One khata line: when, what, how much, what was said, and the balance after it. Tap to edit. */
function EntryRow({
  entry,
  highlighted,
  onSelect,
}: {
  entry: LedgerEntry
  highlighted: boolean
  onSelect: () => void
}) {
  const style = TYPE_STYLES[entry.type]
  return (
    <li>
      <button
        type="button"
        data-testid="khata-row"
        onClick={onSelect}
        className={`flex w-full flex-col gap-1 px-4 py-3 text-left active:bg-stone-100 ${highlighted ? 'bg-emerald-50' : ''}`}
      >
        <span className="flex w-full items-start justify-between gap-3">
          <span className="min-w-0">
            <span className="block text-base text-stone-600">{formatDateTime(entry.created_at)}</span>
            {entry.item && <span className="block text-lg font-semibold break-words text-stone-900">{entry.item}</span>}
          </span>
          <span className="flex shrink-0 flex-col items-end gap-1">
            <span className={`text-xl font-bold tabular-nums ${style.text}`}>{formatTaka(entry.amount)}</span>
            <TypeBadge type={entry.type} />
          </span>
        </span>
        {entry.raw_text && (
          <span className="block text-base break-words text-stone-600 italic">“{entry.raw_text}”</span>
        )}
        <span className="block text-base text-stone-700" data-testid="running-balance">
          {strings.balanceAfter}:{' '}
          <span className={`font-semibold ${balanceTone(entry.running_balance)}`}>
            {describeBalance(entry.running_balance)}
          </span>
        </span>
      </button>
    </li>
  )
}
