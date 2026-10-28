import { useEffect, useState } from 'react'
import type { ParseConfirmResult } from '../api/types'
import { describeBalance, formatTaka } from '../format'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'
import { Button } from './ui'

/** How long "Bhul hoyeche? Undo" stays after saving. */
export const UNDO_SECONDS = 10

type UndoState = 'offered' | 'undoing' | 'failed'

/** Shown after saving: what was saved, each customer's new balance, and Undo for 10 seconds. */
export function SavedMessage({
  results,
  onClose,
  onUndo,
}: {
  results: ParseConfirmResult[]
  onClose: () => void
  /** Delete what was just saved. Resolves when done; throws if it couldn't. */
  onUndo?: () => Promise<void>
}) {
  const many = results.length > 1
  return (
    <section role="status" className="flex flex-col gap-3 rounded-3xl border-2 border-emerald-500 bg-emerald-50 p-4">
      <p className="text-2xl font-bold text-emerald-800">
        ✓ {many ? strings.multi.savedTitle(results.length) : strings.savedTitle}
      </p>
      {results.map((result) => (
        <SavedEntry key={result.transaction.id} result={result} compact={many} />
      ))}
      {onUndo && <UndoButton onUndo={onUndo} />}
      <Button variant="secondary" onClick={onClose}>
        {strings.close}
      </Button>
    </section>
  )
}

function SavedEntry({ result, compact }: { result: ParseConfirmResult; compact: boolean }) {
  const { transaction, customer } = result
  const style = TYPE_STYLES[transaction.type]
  if (compact) {
    return (
      <div className="rounded-2xl bg-white px-4 py-3" data-testid="saved-entry">
        <p className="text-xl text-stone-800">
          {customer.name}: <span className={`font-bold ${style.text}`}>{formatTaka(transaction.amount)}</span>{' '}
          {style.label}
        </p>
        <p className="text-lg text-stone-700">
          {strings.currentBalance}: <span className="font-semibold">{describeBalance(customer.balance)}</span>
        </p>
        {result.customer_created && (
          <p className="text-base text-stone-600">{strings.savedNewCustomer(customer.name)}</p>
        )}
      </div>
    )
  }
  return (
    <>
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
    </>
  )
}

/** "Bhul hoyeche? Undo (9)": counts down, then goes away. */
function UndoButton({ onUndo }: { onUndo: () => Promise<void> }) {
  // A fixed end time: phones slow timers down in the background, the clock keeps going.
  const [deadline] = useState(() => Date.now() + UNDO_SECONDS * 1000)
  const [now, setNow] = useState(() => Date.now())
  const [state, setState] = useState<UndoState>('offered')
  const secondsLeft = Math.ceil((deadline - now) / 1000)

  useEffect(() => {
    if (state !== 'offered') return
    const timer = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(timer)
  }, [state])

  async function undo() {
    setState('undoing')
    try {
      await onUndo()
    } catch {
      setState('failed')
    }
  }

  if (state === 'offered' && secondsLeft <= 0) return null
  if (state === 'failed') return <p className="text-lg text-red-700">{strings.undo.failed}</p>
  return (
    <Button
      variant="danger"
      onClick={undo}
      disabled={state === 'undoing'}
      aria-label={strings.undo.label}
      className="border-amber-400! text-amber-900!"
    >
      {state === 'undoing' ? strings.undo.undoing : `↶ ${strings.undo.button(secondsLeft)}`}
    </Button>
  )
}
