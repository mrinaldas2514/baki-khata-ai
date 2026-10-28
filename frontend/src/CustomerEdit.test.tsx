/** Adding and editing customers (name, phone, area), the reminder's "add phone", and entry dates. */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { toDateInput } from './format'
import { strings } from './strings'
import {
  CREATE_CUSTOMER,
  CUSTOMERS,
  RECENT,
  customer,
  customerKey,
  ledgerEntry,
  ledgerKey,
  ledgerPage,
  listItem,
  mockApi,
  patchKey,
  reminderKey,
} from './test/mockApi'

const salma = customer(7, 'Salma', 700, 'Mosque road')

function openKhata(handlers: Parameters<typeof mockApi>[0]) {
  const api = mockApi({ [RECENT]: { body: [] }, ...handlers })
  window.location.hash = `#/customers/${salma.id}`
  render(<App />)
  return { api, user: userEvent.setup() }
}

describe('adding a customer', () => {
  it('opens a form from the list, normalizes the phone and opens the new khata', async () => {
    const created = { ...customer(12, 'Tanvir', 0, 'Haat'), phone: '+8801711000001' }
    const api = mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: [listItem(1, 'Rahim', 0)] },
      [CREATE_CUSTOMER]: { status: 201, body: created },
      [ledgerKey(12)]: { body: ledgerPage(created, []) },
    })
    window.location.hash = '#/customers'
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: strings.customerForm.addButton }))
    const sheet = screen.getByRole('dialog', { name: strings.customerForm.addTitle })
    await user.type(within(sheet).getByLabelText(strings.customerForm.name), ' Tanvir ')
    await user.type(within(sheet).getByLabelText(strings.customerForm.phone), '01711-000001')
    await user.type(within(sheet).getByLabelText(strings.customerForm.note), 'Haat')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))

    expect(await screen.findByRole('heading', { name: 'Tanvir' })).toBeInTheDocument()
    expect(api.bodiesOf(CREATE_CUSTOMER)).toEqual([{ name: 'Tanvir', phone: '+8801711000001', note: 'Haat' }])
    expect(window.location.hash).toBe('#/customers/12')
    expect(screen.getByRole('link', { name: strings.call('01711-000001') })).toBeInTheDocument()
  })

  it('refuses a number that is not a Bangladesh or India mobile, before saving', async () => {
    const api = mockApi({ [RECENT]: { body: [] }, [CUSTOMERS]: { body: [] } })
    window.location.hash = '#/customers'
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: strings.customerForm.addButton }))
    const sheet = screen.getByRole('dialog')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))
    expect(within(sheet).getByText(strings.nameRequired)).toBeInTheDocument()

    await user.type(within(sheet).getByLabelText(strings.customerForm.name), 'Tanvir')
    await user.type(within(sheet).getByLabelText(strings.customerForm.phone), '+44 7700 900123')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))
    expect(within(sheet).getByText(strings.customerForm.phoneInvalid)).toBeInTheDocument()
    expect(api.requests.filter((r) => r.key === CREATE_CUSTOMER)).toHaveLength(0)
  })
})

describe('editing a customer', () => {
  it('changes name, phone and area from the khata', async () => {
    const updated = { ...salma, name: 'Salma Begum', phone: '+919876543210', note: 'Station road' }
    const { api, user } = openKhata({
      [ledgerKey(7)]: { body: ledgerPage(salma, []) },
      [customerKey(7)]: { body: updated },
    })

    await user.click(await screen.findByRole('button', { name: `✎ ${strings.customerForm.editButton}` }))
    const sheet = screen.getByRole('dialog', { name: strings.customerForm.editTitle })
    const name = within(sheet).getByLabelText(strings.customerForm.name)
    expect(name).toHaveValue('Salma')
    expect(within(sheet).getByLabelText(strings.customerForm.note)).toHaveValue('Mosque road')
    await user.clear(name)
    await user.type(name, 'Salma Begum')
    await user.type(within(sheet).getByLabelText(strings.customerForm.phone), '+91 98765 43210')
    const note = within(sheet).getByLabelText(strings.customerForm.note)
    await user.clear(note)
    await user.type(note, 'Station road')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))

    expect(await screen.findByRole('heading', { name: 'Salma Begum' })).toBeInTheDocument()
    expect(api.bodiesOf(customerKey(7))).toEqual([
      { name: 'Salma Begum', phone: '+919876543210', note: 'Station road' },
    ])
    expect(screen.getByText('Station road')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: strings.call('+91 98765 43210') })).toBeInTheDocument()
    expect(screen.getByText(`✓ ${strings.customerForm.saved}`)).toBeInTheDocument()
    expect(screen.getByTestId('khata-balance')).toHaveTextContent('Baki ৳700')
  })

  it('shows the backend saying the name clashes', async () => {
    const { user } = openKhata({
      [ledgerKey(7)]: { body: ledgerPage(salma, []) },
      [customerKey(7)]: { status: 409, body: { detail: 'exists' } },
    })
    await user.click(await screen.findByRole('button', { name: `✎ ${strings.customerForm.editButton}` }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: strings.save }))
    expect(await screen.findByText(strings.errors.duplicateCustomer)).toBeInTheDocument()
  })
})

describe('reminder without a phone', () => {
  it('asks for the number, saves it, then offers WhatsApp', async () => {
    const message = 'Priyo Salma,\nApnar 700 taka baki ache.'
    const { api, user } = openKhata({
      [ledgerKey(7)]: { body: ledgerPage(salma, [ledgerEntry(1, 'credit', 700, 700)]) },
      [reminderKey(7)]: () =>
        api.requests.some((r) => r.key === customerKey(7))
          ? { body: { message, polished: false, phone: '+8801811000002', whatsapp_number: '8801811000002' } }
          : { body: { message, polished: false, phone: null, whatsapp_number: null } },
      [customerKey(7)]: { body: { ...salma, phone: '+8801811000002' } },
    })

    await user.click(await screen.findByRole('button', { name: strings.sendReminder }))
    const sheet = await screen.findByRole('dialog', { name: strings.reminderTitle('Salma') })
    expect(await within(sheet).findByText(strings.reminderNoPhone)).toBeInTheDocument()
    expect(within(sheet).queryByRole('link', { name: strings.openWhatsApp })).not.toBeInTheDocument()

    const phone = within(sheet).getByLabelText(strings.customerForm.phone)
    await user.type(phone, '123')
    await user.click(within(sheet).getByRole('button', { name: strings.reminderAddPhone }))
    expect(within(sheet).getByText(strings.customerForm.phoneInvalid)).toBeInTheDocument()

    await user.clear(phone)
    await user.type(phone, '01811-000002')
    await user.click(within(sheet).getByRole('button', { name: strings.reminderAddPhone }))

    const whatsapp = await within(sheet).findByRole('link', { name: strings.openWhatsApp })
    expect(whatsapp.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/8801811000002\?text=/)
    expect(api.bodiesOf(customerKey(7))).toEqual([{ phone: '+8801811000002' }])
    expect(within(sheet).getByText(`✓ ${strings.reminderPhoneSaved}`)).toBeInTheDocument()
  })
})

describe("changing an entry's date", () => {
  const rows = [
    ledgerEntry(3, 'credit', 500, 700, { createdAt: '2026-10-25T08:00:00Z' }),
    ledgerEntry(2, 'payment', 300, 200, { createdAt: '2026-10-20T08:00:00Z' }),
    ledgerEntry(1, 'credit', 500, 500, { createdAt: '2026-10-01T08:00:00Z' }),
  ]

  it('sends the new date (same time of day) and reloads every running balance', async () => {
    // After moving the payment before the first credit, the running balances change.
    const after = [
      ledgerEntry(3, 'credit', 500, 700, { createdAt: '2026-10-25T08:00:00Z' }),
      ledgerEntry(1, 'credit', 500, 200, { createdAt: '2026-10-01T08:00:00Z' }),
      ledgerEntry(2, 'payment', 300, -300, { createdAt: '2026-09-15T08:00:00Z' }),
    ]
    let patched = false
    const { api, user } = openKhata({
      [ledgerKey(7)]: () => ({ body: ledgerPage(salma, patched ? after : rows) }),
      [patchKey(2)]: () => {
        patched = true
        return { body: { ...rows[1], created_at: '2026-09-15T08:00:00Z', customer_balance: 700 } }
      },
    })

    const [, payment] = await screen.findAllByTestId('khata-row')
    await user.click(payment)
    const sheet = screen.getByRole('dialog', { name: strings.editTransactionTitle })
    const date = within(sheet).getByLabelText(strings.date)
    expect(date).toHaveValue(toDateInput('2026-10-20T08:00:00Z'))
    expect(date).toHaveAttribute('max', toDateInput(new Date()))
    fireEvent.change(date, { target: { value: '2026-09-15' } })
    await user.click(within(sheet).getByRole('button', { name: strings.save }))

    await screen.findByText(`✓ ${strings.savedEntry}`)
    const [body] = api.bodiesOf(patchKey(2)) as { created_at: string }[]
    const sent = new Date(body.created_at)
    expect(toDateInput(sent)).toBe('2026-09-15')
    const original = new Date('2026-10-20T08:00:00Z')
    expect([sent.getHours(), sent.getMinutes()]).toEqual([original.getHours(), original.getMinutes()])
    expect(screen.getAllByTestId('running-balance').map((el) => el.textContent)).toEqual([
      `${strings.balanceAfter}: Baki ৳700`,
      `${strings.balanceAfter}: Baki ৳200`,
      `${strings.balanceAfter}: Agrim ৳300`,
    ])
  })

  it('refuses a date in the future', async () => {
    const { api, user } = openKhata({ [ledgerKey(7)]: { body: ledgerPage(salma, rows) } })
    await user.click((await screen.findAllByTestId('khata-row'))[0])
    const sheet = screen.getByRole('dialog')
    const tomorrow = new Date(Date.now() + 86_400_000)
    fireEvent.change(within(sheet).getByLabelText(strings.date), { target: { value: toDateInput(tomorrow) } })
    await user.click(within(sheet).getByRole('button', { name: strings.save }))
    expect(within(sheet).getByText(strings.dateInvalid)).toBeInTheDocument()
    expect(api.requests.filter((r) => r.key === patchKey(3))).toHaveLength(0)
  })

  it('leaves the date out when it was not changed', async () => {
    const { api, user } = openKhata({
      [ledgerKey(7)]: { body: ledgerPage(salma, rows) },
      [patchKey(3)]: { body: { ...rows[0], amount: 550, customer_balance: 750 } },
    })
    await user.click((await screen.findAllByTestId('khata-row'))[0])
    const sheet = screen.getByRole('dialog')
    const amount = within(sheet).getByLabelText(strings.amount)
    await user.clear(amount)
    await user.type(amount, '550')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))
    await screen.findByText(`✓ ${strings.savedEntry}`)
    expect(api.bodiesOf(patchKey(3))).toEqual([{ type: 'credit', amount: 550, item: null }])
  })
})
