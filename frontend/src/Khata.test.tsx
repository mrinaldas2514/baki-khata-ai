/** One customer's khata: balance, running balance, "aro dekhun", edit/delete, quick entry, reminder. */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import type { LedgerEntry } from './api/types'
import { PAGE_SIZE } from './screens/KhataScreen'
import { strings } from './strings'
import {
  RECENT,
  addKey,
  customer,
  deleteKey,
  ledgerEntry,
  ledgerKey,
  ledgerPage,
  mockApi,
  patchKey,
  reminderKey,
} from './test/mockApi'

const salma = { ...customer(7, 'Salma', 700, 'Mosque road'), phone: '01811-000002' }

/** Newest first, like the API: +500, -300, +500 -> running 500, 200, 700. */
const ROWS: LedgerEntry[] = [
  ledgerEntry(3, 'credit', 500, 700, {
    item: 'dal, tel',
    rawText: 'salma apa pach sho taka baki, dal r tel',
    createdAt: '2026-10-25T08:00:00Z',
  }),
  ledgerEntry(2, 'payment', 300, 200, { rawText: 'salma 300 joma dilo', createdAt: '2026-10-20T08:00:00Z' }),
  ledgerEntry(1, 'credit', 500, 500, { item: 'chal', createdAt: '2026-10-01T08:00:00Z' }),
]

function openKhata(handlers: Parameters<typeof mockApi>[0]) {
  const api = mockApi({ [RECENT]: { body: [] }, ...handlers })
  window.location.hash = `#/customers/${salma.id}`
  render(<App />)
  return { api, user: userEvent.setup() }
}

const rows = () => screen.getAllByTestId('khata-row')
const runningBalances = () => screen.getAllByTestId('running-balance').map((el) => el.textContent)

describe('khata screen', () => {
  it('shows the customer, the balance big, and every entry newest first with its running balance', async () => {
    const { api } = openKhata({ [ledgerKey(7)]: { body: ledgerPage(salma, ROWS) } })

    expect(await screen.findByRole('heading', { name: 'Salma' })).toBeInTheDocument()
    expect(screen.getByText('Mosque road')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: strings.call('01811-000002') })).toHaveAttribute('href', 'tel:01811-000002')
    expect(screen.getByTestId('khata-balance')).toHaveTextContent('Baki ৳700')
    expect(screen.getByTestId('khata-balance')).toHaveClass('text-red-700')

    expect(runningBalances()).toEqual([
      `${strings.balanceAfter}: Baki ৳700`,
      `${strings.balanceAfter}: Baki ৳200`,
      `${strings.balanceAfter}: Baki ৳500`,
    ])
    const [newest, payment] = rows()
    expect(newest).toHaveTextContent('৳500')
    expect(newest).toHaveTextContent('dal, tel')
    expect(newest).toHaveTextContent('“salma apa pach sho taka baki, dal r tel”')
    expect(newest).toHaveTextContent('25 Oct')
    expect(payment).toHaveTextContent(strings.typePayment)
    expect(payment).toHaveTextContent('“salma 300 joma dilo”')

    expect(api.queriesOf(ledgerKey(7))).toEqual([{ order: 'newest', limit: String(PAGE_SIZE), offset: '0' }])
    expect(screen.queryByRole('button', { name: strings.showMore })).not.toBeInTheDocument()
  })

  it('shows a settled customer in green, and an advance as Agrim', async () => {
    openKhata({
      [ledgerKey(7)]: { body: ledgerPage({ ...salma, balance: -100 }, [ledgerEntry(9, 'payment', 100, -100)]) },
    })
    const balance = await screen.findByTestId('khata-balance')
    expect(balance).toHaveTextContent('Agrim ৳100')
    expect(balance).toHaveClass('text-green-700')
    expect(runningBalances()).toEqual([`${strings.balanceAfter}: Agrim ৳100`])
    // No reminder for someone who owes nothing.
    expect(screen.queryByRole('button', { name: strings.sendReminder })).not.toBeInTheDocument()
  })

  it('"Aro dekhun" adds the older entries below, continuing the running balance', async () => {
    const { api, user } = openKhata({
      [ledgerKey(7)]: (_body, query) => {
        return query.get('offset') === '0'
          ? { body: ledgerPage(salma, ROWS.slice(0, 2), 3, true) }
          : { body: ledgerPage(salma, ROWS.slice(2), 3, false) }
      },
    })

    await screen.findByRole('heading', { name: 'Salma' })
    expect(rows()).toHaveLength(2)
    expect(screen.getByText(strings.historyCount(2, 3))).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: strings.showMore }))

    await waitFor(() => expect(rows()).toHaveLength(3))
    expect(runningBalances().at(-1)).toBe(`${strings.balanceAfter}: Baki ৳500`)
    expect(api.queriesOf(ledgerKey(7)).at(-1)).toEqual({ order: 'newest', limit: String(PAGE_SIZE), offset: '2' })
    expect(screen.queryByRole('button', { name: strings.showMore })).not.toBeInTheDocument()
  })

  it('edits an entry and shows the new running balances', async () => {
    let edited = false
    const { api, user } = openKhata({
      [ledgerKey(7)]: () =>
        edited
          ? {
              body: ledgerPage({ ...salma, balance: 500 }, [
                { ...ROWS[0], running_balance: 500 },
                { ...ROWS[1], running_balance: 0 },
                { ...ROWS[2], amount: 300, running_balance: 300 },
              ]),
            }
          : { body: ledgerPage(salma, ROWS) },
      [patchKey(1)]: () => {
        edited = true
        return { body: { ...ROWS[2], amount: 300, customer_balance: 500 } }
      },
    })

    await screen.findByRole('heading', { name: 'Salma' })
    await user.click(rows()[2])
    const sheet = screen.getByRole('dialog', { name: strings.editTransactionTitle })
    const amount = within(sheet).getByLabelText(strings.amount)
    expect(amount).toHaveValue('500')
    expect(within(sheet).getByLabelText(strings.item)).toHaveValue('chal')
    await user.clear(amount)
    await user.type(amount, '300')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))

    await waitFor(() => expect(screen.getByTestId('khata-balance')).toHaveTextContent('Baki ৳500'))
    expect(api.bodiesOf(patchKey(1))).toEqual([{ type: 'credit', amount: 300, item: 'chal' }])
    expect(runningBalances()).toEqual([
      `${strings.balanceAfter}: Baki ৳500`,
      `${strings.balanceAfter}: Hisab clear`,
      `${strings.balanceAfter}: Baki ৳300`,
    ])
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(strings.savedEntry)
  })

  it('asks before deleting, and deletes only on yes', async () => {
    let deleted = false
    const { api, user } = openKhata({
      [ledgerKey(7)]: () =>
        deleted
          ? {
              body: ledgerPage(
                { ...salma, balance: 200 },
                [ROWS[1], ROWS[2]].map((r) => ({ ...r })),
              ),
            }
          : { body: ledgerPage(salma, ROWS) },
      [deleteKey(3)]: () => {
        deleted = true
        return { status: 204 }
      },
    })

    await screen.findByRole('heading', { name: 'Salma' })
    await user.click(rows()[0])
    await user.click(screen.getByRole('button', { name: strings.deleteTransaction }))

    let confirm = screen.getByRole('alertdialog', { name: strings.deleteConfirmTitle })
    expect(confirm).toHaveTextContent('৳500 Baki')
    // "No" is the safe default.
    expect(within(confirm).getByRole('button', { name: strings.deleteConfirmNo })).toHaveFocus()
    await user.click(within(confirm).getByRole('button', { name: strings.deleteConfirmNo }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(api.requests.filter((r) => r.key === deleteKey(3))).toHaveLength(0)

    await user.click(rows()[0])
    await user.click(screen.getByRole('button', { name: strings.deleteTransaction }))
    confirm = screen.getByRole('alertdialog', { name: strings.deleteConfirmTitle })
    await user.click(within(confirm).getByRole('button', { name: strings.deleteConfirmYes }))

    await waitFor(() => expect(rows()).toHaveLength(2))
    expect(api.requests.filter((r) => r.key === deleteKey(3))).toHaveLength(1)
    expect(screen.getByTestId('khata-balance')).toHaveTextContent('Baki ৳200')
    expect(screen.getByRole('status')).toHaveTextContent(strings.deletedEntry)
  })

  it('keeps the confirm open with a message when the delete fails', async () => {
    const { user } = openKhata({ [ledgerKey(7)]: { body: ledgerPage(salma, ROWS) }, [deleteKey(3)]: 'network-error' })
    await screen.findByRole('heading', { name: 'Salma' })
    await user.click(rows()[0])
    await user.click(screen.getByRole('button', { name: strings.deleteTransaction }))
    await user.click(screen.getByRole('button', { name: strings.deleteConfirmYes }))
    expect(await within(screen.getByRole('alertdialog')).findByRole('alert')).toHaveTextContent(strings.deleteFailed)
    expect(rows()).toHaveLength(3)
  })

  it.each([
    [strings.addCredit, 'credit'],
    [strings.addPayment, 'payment'],
  ] as const)('"%s" opens a small form for this customer and saves it', async (button, type) => {
    let saved = false
    const added = ledgerEntry(10, type, 150, type === 'credit' ? 850 : 550, { item: 'cha' })
    const { api, user } = openKhata({
      [ledgerKey(7)]: () => ({
        body: saved
          ? ledgerPage({ ...salma, balance: added.running_balance }, [added, ...ROWS])
          : ledgerPage(salma, ROWS),
      }),
      [addKey(7)]: () => {
        saved = true
        return { status: 201, body: { ...added, customer_balance: added.running_balance } }
      },
    })

    await screen.findByRole('heading', { name: 'Salma' })
    await user.click(screen.getByRole('button', { name: button }))
    const sheet = screen.getByRole('dialog', {
      name: strings.quickEntryTitle(type === 'credit' ? 'Baki' : 'Joma', 'Salma'),
    })
    expect(within(sheet).getByRole('radio', { name: new RegExp(type === 'credit' ? 'Baki' : 'Joma') })).toBeChecked()
    expect(within(sheet).getByLabelText(strings.amount)).toHaveFocus()

    await user.click(within(sheet).getByRole('button', { name: strings.save }))
    expect(within(sheet).getByText(strings.amountInvalid)).toBeInTheDocument()

    await user.type(within(sheet).getByLabelText(strings.amount), '১৫০')
    await user.type(within(sheet).getByLabelText(strings.item), 'cha')
    await user.click(within(sheet).getByRole('button', { name: strings.save }))

    await waitFor(() => expect(rows()).toHaveLength(4))
    expect(api.bodiesOf(addKey(7))).toEqual([{ type, amount: 150, item: 'cha' }])
    expect(screen.getByTestId('khata-balance')).toHaveTextContent(`Baki ৳${added.running_balance}`)
    // The reload asks for everything that was on screen plus the new row (at least one page).
    expect(api.queriesOf(ledgerKey(7)).at(-1)?.limit).toBe(String(PAGE_SIZE))
  })

  it('says when the customer does not exist', async () => {
    openKhata({ [ledgerKey(7)]: { status: 404, body: { detail: 'Customer 7 not found in shop 1' } } })
    expect(await screen.findByText(strings.customerNotFound)).toBeInTheDocument()
  })
})

describe('reminder', () => {
  const message = 'Priyo Salma,\nAshakori bhalo achen. Demo Dokan-e apnar 700 taka baki ache.\nDhonnobad'

  it('opens WhatsApp with the message filled in, never sending it itself', async () => {
    const { api, user } = openKhata({
      [ledgerKey(7)]: { body: ledgerPage(salma, ROWS) },
      [reminderKey(7)]: {
        body: { message, polished: false, phone: '01811-000002', whatsapp_number: '8801811000002' },
      },
    })
    await user.click(await screen.findByRole('button', { name: strings.sendReminder }))

    const sheet = screen.getByRole('dialog', { name: strings.reminderTitle('Salma') })
    const text = await within(sheet).findByLabelText(strings.reminderLabel)
    expect(text).toHaveValue(message)
    const link = within(sheet).getByRole('link', { name: strings.openWhatsApp })
    expect(link).toHaveAttribute('href', `https://wa.me/8801811000002?text=${encodeURIComponent(message)}`)
    expect(link).toHaveAttribute('target', '_blank')

    // The shopkeeper can change the words; the link follows.
    await user.type(text, ' Karim')
    expect(link).toHaveAttribute('href', `https://wa.me/8801811000002?text=${encodeURIComponent(`${message} Karim`)}`)
    expect(api.requests.map((r) => r.key)).toContain(reminderKey(7))
  })

  it('without a phone, offers to copy the message', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    const { user } = openKhata({
      [ledgerKey(7)]: { body: ledgerPage({ ...salma, phone: null }, ROWS) },
      [reminderKey(7)]: { body: { message, polished: false, phone: null, whatsapp_number: null } },
    })
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    expect(await screen.findByText(strings.noPhone)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: strings.sendReminder }))
    const sheet = screen.getByRole('dialog', { name: strings.reminderTitle('Salma') })
    expect(await within(sheet).findByText(strings.reminderNoPhone)).toBeInTheDocument()
    expect(within(sheet).queryByRole('link', { name: strings.openWhatsApp })).not.toBeInTheDocument()

    await user.click(within(sheet).getByRole('button', { name: strings.copyMessage }))
    expect(writeText).toHaveBeenCalledWith(message)
    expect(within(sheet).getByRole('status')).toHaveTextContent(strings.copied)
  })
})
