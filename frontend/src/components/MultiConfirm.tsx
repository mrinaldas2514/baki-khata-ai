import { LOW_CONFIDENCE } from '../config'
import type { CustomerChoice, MultiItem, ReadBy } from '../entry'
import { formatTaka } from '../format'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'
import { CustomerOption, CustomerSummary, NewCustomerOption } from './CustomerSummary'
import { EntryForm } from './EntryForm'
import { Alert, Button, ParserLabel, TypeBadge } from './ui'

interface Props {
  rawText: string
  items: MultiItem[]
  readBy: ReadBy
  onChange: (items: MultiItem[]) => void
  onSaveAll: () => void
  onCancel: () => void
  saving: boolean
  error?: string | null
}

/**
 * "rahim 200 baki, karim 500 dilo, salma 100 baki": a card per customer. Each can be fixed
 * ("Thik kore din") or dropped ("Bad din"); "Sob save korun" saves them all together.
 */
export function MultiConfirm({ rawText, items, readBy, onChange, onSaveAll, onCancel, saving, error }: Props) {
  const update = (key: number, changes: Partial<MultiItem>) =>
    onChange(items.map((item) => (item.key === key ? { ...item, ...changes } : item)))
  const ready = items.every((item) => item.choice && !item.editing)

  return (
    <section aria-labelledby="multi-title" className="flex flex-col gap-4">
      <div className="rounded-3xl bg-white p-4 shadow-md">
        <h2 id="multi-title" className="text-2xl font-bold text-stone-900">
          {strings.multi.title(items.length)}
        </h2>
        <p className="text-base text-stone-600">
          {strings.youWrote}: “{rawText}”
        </p>
        <p className="mt-2 text-lg text-stone-800">{strings.multi.hint}</p>
      </div>

      {items.map((item, index) =>
        item.editing ? (
          <EntryForm
            key={item.key}
            title={strings.multi.editTitle(index + 1)}
            rawText=""
            initial={{
              name: item.entry.match.suggested_name,
              choice: item.choice,
              amount: item.amount,
              type: item.type,
              item: item.item,
            }}
            suggestions={item.entry.match.candidates}
            onSave={(draft) => update(item.key, { ...draft, editing: false })}
            onCancel={() => update(item.key, { editing: false })}
          />
        ) : (
          <EntryCard
            key={item.key}
            index={index}
            item={item}
            readBy={readBy}
            onChoose={(choice) => update(item.key, { choice })}
            onEdit={() => update(item.key, { editing: true })}
            onRemove={() => onChange(items.filter((other) => other.key !== item.key))}
            disabled={saving}
          />
        ),
      )}

      {error && <Alert>{error}</Alert>}
      <div className="flex flex-col gap-3">
        <Button onClick={onSaveAll} disabled={!ready || saving || items.length === 0}>
          {saving ? strings.saving : ready ? strings.multi.saveAll(items.length) : strings.multi.pickAll}
        </Button>
        <Button variant="danger" onClick={onCancel} disabled={saving}>
          {strings.cancel}
        </Button>
      </div>
    </section>
  )
}

function EntryCard({
  index,
  item,
  readBy,
  onChoose,
  onEdit,
  onRemove,
  disabled,
}: {
  index: number
  item: MultiItem
  readBy: ReadBy
  onChoose: (choice: CustomerChoice) => void
  onEdit: () => void
  onRemove: () => void
  disabled: boolean
}) {
  const { match, parsed, warnings } = item.entry
  const style = TYPE_STYLES[item.type]
  const name =
    item.choice?.kind === 'existing' ? item.choice.customer.name : (item.choice?.name ?? match.suggested_name)
  const notSure = parsed.confidence < LOW_CONFIDENCE

  return (
    <article
      aria-label={strings.multi.entryLabel(index + 1, name)}
      data-testid="multi-card"
      className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-md"
    >
      <div className={`flex flex-wrap items-center gap-3 rounded-2xl border-2 px-4 py-3 ${style.panel}`}>
        <span className={`text-4xl font-bold tabular-nums ${style.text}`} data-testid="amount">
          {formatTaka(item.amount)}
        </span>
        <TypeBadge type={item.type} />
        <span className="ml-auto">
          <ParserLabel parser={readBy.parser} model={readBy.model} />
        </span>
        {item.item && (
          <span className="w-full text-lg text-stone-900">
            {strings.itemShort}: <span className="font-semibold">{item.item}</span>
          </span>
        )}
      </div>

      {match.status === 'ambiguous' && !item.choice ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-xl font-bold text-stone-900">{strings.whichCustomer}</legend>
          {match.candidates.map((candidate) => (
            <CustomerOption
              key={candidate.id}
              customer={candidate}
              selected={false}
              onSelect={() => onChoose({ kind: 'existing', customer: candidate })}
            />
          ))}
          <NewCustomerOption
            name={match.suggested_name}
            selected={false}
            onSelect={() => onChoose({ kind: 'new', name: match.suggested_name })}
          />
        </fieldset>
      ) : item.choice?.kind === 'existing' ? (
        <CustomerSummary customer={item.choice.customer} />
      ) : (
        <CustomerSummary newName={name} />
      )}

      {match.status === 'fuzzy' && match.customer && item.choice?.kind === 'existing' && (
        <Alert tone="warning">{strings.fuzzyMatch(parsed.customer_name, match.customer.name)}</Alert>
      )}
      {notSure && <Alert tone="warning">{strings.errors.lowConfidence}</Alert>}
      {warnings.length > 0 && match.status !== 'fuzzy' && (
        <Alert tone="warning">
          <ul className="text-base">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Alert>
      )}

      <div className="flex gap-3">
        <Button
          variant="secondary"
          className="flex-1 px-2! text-lg! whitespace-nowrap"
          onClick={onEdit}
          disabled={disabled}
        >
          {strings.edit}
        </Button>
        <Button
          variant="danger"
          className="flex-1 px-2! text-lg! whitespace-nowrap"
          onClick={onRemove}
          disabled={disabled}
        >
          {strings.multi.remove}
        </Button>
      </div>
    </article>
  )
}
