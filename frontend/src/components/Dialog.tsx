import { type ReactNode, useEffect, useEffectEvent, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { strings } from '../strings'
import { Button } from './ui'

/** Close on Escape, keep the page behind from scrolling, and give focus back when closed. */
function useModal(onClose: () => void, initialFocus: () => HTMLElement | null | undefined) {
  const close = useEffectEvent(onClose)
  const focusFirst = useEffectEvent(() => initialFocus()?.focus())
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    focusFirst()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [])
}

/** A panel that slides up from the bottom of the phone: small forms, the reminder. */
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  useModal(onClose, () => panel.current?.querySelector<HTMLElement>('input, textarea') ?? panel.current)

  return createPortal(
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-stone-900/50"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="max-h-[92dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white px-4 pt-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] shadow-xl focus:outline-none"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 id={titleId} className="pt-2 text-2xl font-bold text-stone-900">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={strings.closeDialog}
            className="flex size-12 shrink-0 items-center justify-center rounded-full text-3xl text-stone-600 active:bg-stone-100"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}

/** "Are you sure?" before something that can't be undone. Focus starts on the safe choice. */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  cancelLabel,
  busy = false,
  busyLabel,
  error,
  onConfirm,
  onCancel,
}: {
  title: string
  body: string
  confirmLabel: string
  cancelLabel: string
  busy?: boolean
  busyLabel?: string
  error?: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  const titleId = useId()
  const bodyId = useId()
  const cancel = useRef<HTMLButtonElement>(null)
  useModal(
    () => !busy && onCancel(),
    () => cancel.current,
  )

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 px-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        className="flex w-full max-w-sm flex-col gap-4 rounded-3xl bg-white p-5 shadow-xl"
      >
        <h2 id={titleId} className="text-2xl font-bold text-stone-900">
          {title}
        </h2>
        <p id={bodyId} className="text-lg text-stone-700">
          {body}
        </p>
        {error && (
          <p role="alert" className="text-lg text-red-700">
            {error}
          </p>
        )}
        <div className="flex flex-col gap-3">
          <Button variant="destructive" onClick={onConfirm} disabled={busy}>
            {busy && busyLabel ? busyLabel : confirmLabel}
          </Button>
          <Button ref={cancel} variant="secondary" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
