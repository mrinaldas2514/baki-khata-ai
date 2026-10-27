import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Customer, Reminder } from '../api/types'
import { copyText, whatsappLink } from '../reminder'
import { strings } from '../strings'
import { Sheet } from './Dialog'
import { Alert, Button, ButtonLink, inputClass } from './ui'

/**
 * "Reminder pathan": the backend writes a polite message, the shopkeeper can change it, then
 * WhatsApp opens with it typed in. Sending is always the shopkeeper's own tap in WhatsApp.
 * Without a phone number the message can be copied instead.
 */
export function ReminderSheet({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const [reminder, setReminder] = useState<Reminder | null>(null)
  const [failed, setFailed] = useState(false)
  const [message, setMessage] = useState('')
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')

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
            <Alert tone="warning">{strings.reminderNoPhone}</Alert>
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
