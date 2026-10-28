import { useState } from 'react'
import type { ParsePreview } from '../api/types'
import { type CustomerChoice, type Draft, initialChoice } from '../entry'
import { formatTaka } from '../format'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'
import { CustomerOption, CustomerSummary, NewCustomerOption } from './CustomerSummary'
import { Alert, Button, ParserLabel, TypeBadge } from './ui'

interface Props {
  preview: ParsePreview
  onSave: (draft: Draft) => void
  /** Open the edit form, keeping the customer picked here (if any). */
  onEdit: (choice: CustomerChoice | null) => void
  onCancel: () => void
  saving?: boolean
  error?: string | null
}

/**
 * The amount as big as fits: up to 88 px (৳500, ৳1,500), smaller for long ones (৳1,25,000) so
 * it never runs past the card. Digits are ~0.44 em wide in Noto Sans Bengali; 7rem is the room
 * the card, panel and page take around it (in rem, so it grows with the phone's text size too).
 */
function amountFontSize(text: string): string {
  const em = (text.length * 0.46).toFixed(2)
  return `min(5.5rem, calc((100vw - 7rem) / ${em}))`
}

/** "Thik ache to?": what the AI understood, shown big and clear before anything is saved. */
export function ConfirmationCard({ preview, onSave, onEdit, onCancel, saving = false, error }: Props) {
  const { parsed, match } = preview
  const [choice, setChoice] = useState<CustomerChoice | null>(() => initialChoice(preview))
  const style = TYPE_STYLES[parsed.type]

  return (
    <section aria-labelledby="confirm-title" className="flex flex-col gap-4 rounded-3xl bg-white p-4 shadow-md">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <h2 id="confirm-title" className="text-2xl font-bold text-stone-900">
            {strings.confirmTitle}
          </h2>
          <ParserLabel parser={preview.parser} model={preview.model} />
        </div>
        <p className="text-base text-stone-600">
          {strings.youWrote}: “{preview.raw_text}”
        </p>
      </div>

      <div className={`rounded-2xl border-2 px-4 py-4 ${style.panel}`} data-testid="amount-panel">
        {/* The number to check at arm's length: as big as fits a 360 px phone. */}
        <p
          className={`leading-none font-bold tabular-nums ${style.text}`}
          style={{ fontSize: amountFontSize(formatTaka(parsed.amount)) }}
          data-testid="amount"
        >
          {formatTaka(parsed.amount)}
        </p>
        <p className="mt-2 flex flex-wrap items-center gap-2 text-lg text-stone-800">
          <TypeBadge type={parsed.type} />
          <span>{style.hint}</span>
        </p>
        {parsed.item && (
          <p className="mt-2 text-xl text-stone-900">
            {strings.itemShort}: <span className="font-semibold">{parsed.item}</span>
          </p>
        )}
      </div>

      {match.status === 'ambiguous' ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-xl font-bold text-stone-900">{strings.whichCustomer}</legend>
          {match.candidates.map((candidate) => (
            <CustomerOption
              key={candidate.id}
              customer={candidate}
              selected={choice?.kind === 'existing' && choice.customer.id === candidate.id}
              onSelect={() => setChoice({ kind: 'existing', customer: candidate })}
            />
          ))}
          <NewCustomerOption
            name={match.suggested_name}
            selected={choice?.kind === 'new'}
            onSelect={() => setChoice({ kind: 'new', name: match.suggested_name })}
          />
        </fieldset>
      ) : choice?.kind === 'existing' ? (
        <CustomerSummary customer={choice.customer} />
      ) : (
        <CustomerSummary newName={match.suggested_name} />
      )}

      {match.status === 'fuzzy' && match.customer && (
        <Alert tone="warning">{strings.fuzzyMatch(parsed.customer_name, match.customer.name)}</Alert>
      )}
      {preview.warnings.length > 0 && match.status !== 'fuzzy' && (
        <Alert tone="warning">
          <p className="font-semibold">{strings.checkThis}</p>
          <ul className="text-base">
            {preview.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Alert>
      )}
      {error && <Alert>{error}</Alert>}

      <div className="flex flex-col gap-3">
        <Button
          onClick={() => choice && onSave({ choice, amount: parsed.amount, type: parsed.type, item: parsed.item })}
          disabled={!choice || saving}
        >
          {saving ? strings.saving : choice ? strings.save : strings.pickCustomerFirst}
        </Button>
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" className="flex-[1_1_8rem]" onClick={() => onEdit(choice)} disabled={saving}>
            {strings.edit}
          </Button>
          <Button variant="danger" className="flex-[1_1_8rem]" onClick={onCancel} disabled={saving}>
            {strings.cancel}
          </Button>
        </div>
      </div>
    </section>
  )
}
