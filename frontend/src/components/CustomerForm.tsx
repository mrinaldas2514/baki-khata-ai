import { type FormEvent, useState } from 'react'
import type { CustomerInput } from '../api/types'
import { formatPhone, normalizeMobile } from '../phone'
import { strings } from '../strings'
import { Alert, Button, Field } from './ui'

interface Props {
  initial?: CustomerInput
  saving: boolean
  error?: string | null
  /** The backend rejected the phone (422): show it next to the box. */
  phoneRejected?: boolean
  onSave: (values: CustomerInput) => void
  onCancel: () => void
}

/** Name, mobile number and area/note: a new customer, or fixing one. */
export function CustomerForm({ initial, saving, error, phoneRejected = false, onSave, onCancel }: Props) {
  const [name, setName] = useState(initial?.name ?? '')
  const [phone, setPhone] = useState(initial?.phone ? formatPhone(initial.phone) : '')
  const [note, setNote] = useState(initial?.note ?? '')
  const [problems, setProblems] = useState<{ name?: string; phone?: string }>({})

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const normalized = phone.trim() ? normalizeMobile(phone) : null
    const found = {
      name: name.trim() ? undefined : strings.nameRequired,
      phone: phone.trim() && !normalized ? strings.customerForm.phoneInvalid : undefined,
    }
    setProblems(found)
    if (found.name || found.phone) return
    onSave({ name: name.trim(), phone: normalized, note: note.trim() || null })
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      <Field
        id="customer-name"
        label={strings.customerForm.name}
        value={name}
        onChange={(event) => setName(event.target.value)}
        maxLength={100}
        autoComplete="off"
        problem={problems.name}
      />
      <Field
        id="customer-phone"
        label={strings.customerForm.phone}
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        placeholder={strings.customerForm.phonePlaceholder}
        type="tel"
        inputMode="tel"
        autoComplete="off"
        problem={problems.phone ?? (phoneRejected ? strings.customerForm.phoneInvalid : undefined)}
      />
      <Field
        id="customer-note"
        label={strings.customerForm.note}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        maxLength={200}
        autoComplete="off"
      />
      {error && <Alert>{error}</Alert>}
      <div className="flex flex-col gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? strings.saving : strings.save}
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          {strings.cancel}
        </Button>
      </div>
    </form>
  )
}
