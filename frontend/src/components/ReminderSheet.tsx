import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Customer, Reminder } from '../api/types'
import { normalizeMobile } from '../phone'
import { copyText, whatsappLink } from '../reminder'
import { strings } from '../strings'
import { Sheet } from './Dialog'
import { Alert, Button, ButtonLink, Field, inputClass } from './ui'

/**
 * "Reminder pathan": the backend writes a polite message, the shopkeeper can change it, then
 * WhatsApp opens with it typed in. Sending is always the shopkeeper's own tap in WhatsApp.
 * Without a phone number the message can be copied instead.
 */
export function ReminderSheet({
  customer,
  onClose,
  onCustomerUpdated,
}: {
  customer: Customer
  onClose: () => void
  /** The phone number was added here: the khata shows it too. */
  onCustomerUpdated?: (customer: Customer) => void
}) {
  const [reminder, setReminder] = useState<Reminder | null>(null)
  const [failed, setFailed] = useState(false)
  const [message, setMessage] = useState('')
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const [phoneSaved, setPhoneSaved] = useState(false)

  const load = useCallback(() => {
    api.reminder(customer.id).then(
      (result) => {
        setReminder(result)
        setMessage(result.message)
      },
      () => setFailed(true),
    )
  }, [customer.id])

  useEffect(() => {
    load()
  }, [load])

  /** Saved the missing number: ask for the reminder again, now with its WhatsApp number. */
  async function savePhone(phone: string) {
    const updated = await api.updateCustomer(customer.id, { phone })
    onCustomerUpdated?.(updated)
    const next = await api.reminder(customer.id)
    // Keep what the shopkeeper already changed in the message.
    setReminder({ ...next, message })
    setPhoneSaved(true)
  }

  async function copy() {
    setCopyState((await copyText(message)) ? 'copied' : 'failed')
  }

  return (
    <Sheet title={strings.reminderTitle(customer.name)} onClose={onClose}>
      {failed ? (
        <div className="flex flex-col gap-3">
          <Alert>{strings.reminderFailed}</Alert>
          <Button
            variant="secondary"
            onClick={() => {
              setFailed(false)
              load()
            }}
          >
            {strings.retry}
          </Button>
        </div>
      ) : reminder === null ? (
        <p role="status" className="text-lg text-stone-600">
          {strings.reminderLoading}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label htmlFor="reminder-message" className="text-lg font-semibold text-stone-900">
              {strings.reminderLabel}
            </label>
            <textarea
              id="reminder-message"
              value={message}
              onChange={(event) => {
                setMessage(event.target.value)
                setCopyState('idle')
              }}
              rows={8}
              className={`${inputClass} py-3 text-lg leading-snug`}
            />
          </div>
          {reminder.whatsapp_number ? (
            <>
              {phoneSaved && (
                <p role="status" className="text-lg font-semibold text-green-700">
                  ✓ {strings.reminderPhoneSaved}
                </p>
              )}
              <ButtonLink
                variant="whatsapp"
                href={whatsappLink(reminder.whatsapp_number, message)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {strings.openWhatsApp}
              </ButtonLink>
              <p className="text-base text-stone-600">{strings.reminderHint}</p>
            </>
          ) : (
            <>
              <Alert tone="warning">{strings.reminderNoPhone}</Alert>
              <AddPhone onSave={savePhone} />
            </>
          )}
          <Button
            variant={reminder.whatsapp_number ? 'secondary' : 'primary'}
            onClick={copy}
            disabled={!message.trim()}
          >
            {strings.copyMessage}
          </Button>
          {copyState !== 'idle' && (
            <p
              role="status"
              className={`text-lg font-semibold ${copyState === 'copied' ? 'text-green-700' : 'text-red-700'}`}
            >
              {copyState === 'copied' ? `✓ ${strings.copied}` : strings.copyFailed}
            </p>
          )}
        </div>
      )}
    </Sheet>
  )
}

/** "Phone number nei": add it right here, then WhatsApp can open. */
function AddPhone({ onSave }: { onSave: (phone: string) => Promise<void> }) {
  const [phone, setPhone] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const normalized = normalizeMobile(phone)
    if (!normalized) {
      setProblem(strings.customerForm.phoneInvalid)
      return
    }
    setProblem(null)
    setSaving(true)
    try {
      await onSave(normalized)
    } catch {
      setProblem(strings.errors.saveFailed)
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
      <Field
        id="reminder-phone"
        label={strings.customerForm.phone}
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        placeholder={strings.customerForm.phonePlaceholder}
        type="tel"
        inputMode="tel"
        autoComplete="off"
        problem={problem}
      />
      <Button type="submit" variant="whatsapp" disabled={saving}>
        {saving ? strings.saving : strings.reminderAddPhone}
      </Button>
    </form>
  )
}
