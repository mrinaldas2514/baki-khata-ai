import type { FormEvent, ReactNode } from 'react'
import { strings } from '../strings'
import { Button } from './ui'

interface Props {
  value: string
  onChange: (text: string) => void
  onSubmit: (text: string) => void
  busy?: boolean
  /**
   * Extra buttons shown next to "Hisab korun" (the mic). The text is controlled by the parent,
   * so a transcript fills (or submits) the box exactly like typing does.
   */
  actions?: ReactNode
  /** Shown under the buttons (voice status and settings). */
  footer?: ReactNode
}

/** The big "Ki hisab likhben?" box. */
export function SmartEntry({ value, onChange, onSubmit, busy = false, actions, footer }: Props) {
  const text = value.trim()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (text && !busy) onSubmit(text)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <label htmlFor="smart-entry" className="text-2xl font-bold text-stone-900">
        {strings.entryLabel}
      </label>
      <textarea
        id="smart-entry"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          // Enter submits (Shift+Enter for a new line), like a chat app.
          if (event.key === 'Enter' && !event.shiftKey) handleSubmit(event)
        }}
        placeholder={strings.entryPlaceholder}
        rows={3}
        maxLength={500}
        disabled={busy}
        autoComplete="off"
        className="w-full resize-none rounded-2xl border-2 border-stone-300 bg-white p-4 text-xl leading-relaxed text-stone-900 placeholder:text-stone-500 focus:border-emerald-600 focus:outline-none disabled:bg-stone-100"
      />
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={!text || busy} className="flex-[1_1_9rem]">
          {strings.submit}
        </Button>
        {actions}
      </div>
      {footer}
    </form>
  )
}
