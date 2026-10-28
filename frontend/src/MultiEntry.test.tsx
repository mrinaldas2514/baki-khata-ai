/** "rahim 200 baki, karim 500 dilo, salma 100 baki": a card per customer, fix or drop any, save all. */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import type { EntryPreview, ParseConfirm } from './api/types'
import { strings } from './strings'
import {
  CONFIRM_MANY,
  CUSTOMERS,
  PARSE,
  RECENT,
  candidate,
  confirmResult,
  customer,
  mockApi,
  preview,
} from './test/mockApi'

const SENTENCE = 'rahim 200 baki, karim 500 dilo, salma 100 baki'
const rahim = customer(1, 'Rahim', 300, 'Bazar road')
const karimA = customer(2, 'Karim', 0, 'Haat')
const karimB = customer(3, 'Karim', 50, 'Station')

const ENTRIES: EntryPreview[] = [
  {
    parsed: { customer_name: 'rahim', amount: 200, type: 'credit', item: null, confidence: 0.9 },
    match: { status: 'exact', customer: candidate(rahim), candidates: [candidate(rahim)], suggested_name: 'Rahim' },
    warnings: [],
  },
  {
    parsed: { customer_name: 'karim', amount: 500, type: 'payment', item: null, confidence: 0.9 },
    match: {
      status: 'ambiguous',
      customer: null,
      candidates: [candidate(karimA), candidate(karimB)],
      suggested_name: 'Karim',
    },
    warnings: [],
  },
  {
    parsed: { customer_name: 'salma', amount: 100, type: 'credit', item: 'dal', confidence: 0.9 },
    match: { status: 'new', customer: null, candidates: [], suggested_name: 'Salma' },
    warnings: [],
  },
]

const multiPreview = { ...preview({ raw_text: SENTENCE }), ...ENTRIES[0], entries: ENTRIES }

async function submit(handlers: Parameters<typeof mockApi>[0]) {
  const api = mockApi({ [RECENT]: { body: [] }, [PARSE]: { body: multiPreview }, ...handlers })
  const user = userEvent.setup()
  render(<App />)
  await user.type(screen.getByLabelText(strings.entryLabel), SENTENCE)
  await user.click(screen.getByRole('button', { name: strings.submit }))
  await screen.findByRole('heading', { name: strings.multi.title(3) })
  return { api, user }
}

const cards = () => screen.getAllByTestId('multi-card')

describe('several customers in one sentence', () => {
  it('shows a card for each, and waits for a pick between look-alikes', async () => {
    const { user } = await submit({})
    const [first, second, third] = cards()
    expect(first).toHaveAccessibleName(strings.multi.entryLabel(1, 'Rahim'))
    expect(within(first).getByTestId('amount')).toHaveTextContent('৳200')
    expect(within(first).getByTestId('customer-summary')).toHaveTextContent('Ekhon: Baki ৳300')
    expect(within(second).getByText(strings.whichCustomer)).toBeInTheDocument()
    expect(within(second).getByTestId('amount')).toHaveTextContent('৳500')
    expect(second).toHaveTextContent(strings.typePayment)
    expect(within(third).getByTestId('customer-summary')).toHaveTextContent(strings.newCustomerNamed('Salma'))
    expect(third).toHaveTextContent('Jinis: dal')
    for (const each of cards()) expect(within(each).getByTestId('parser-label')).toHaveTextContent(strings.parser.llm)

    const save = screen.getByRole('button', { name: strings.multi.pickAll })
    expect(save).toBeDisabled()
    await user.click(within(second).getByRole('button', { name: /Karim.*Station/ }))
    expect(screen.getByRole('button', { name: strings.multi.saveAll(3) })).toBeEnabled()
  })

  it('saves all of them together after fixing one and dropping one', async () => {
    const { api, user } = await submit({
      [CUSTOMERS]: { body: [] },
      [CONFIRM_MANY]: (body) => {
        const entries = (body as { entries: ParseConfirm[] }).entries
        return {
          status: 201,
          body: {
            results: [
              {
                ...confirmResult(rahim, entries[0] as never, 550),
                transaction: { ...confirmResult(rahim, entries[0] as never, 550).transaction, id: 101 },
              },
              {
                ...confirmResult(karimA, entries[1] as never, -500),
                transaction: { ...confirmResult(karimA, entries[1] as never, -500).transaction, id: 102 },
              },
            ],
          },
        }
      },
    })
    const [first, second, third] = cards()
    // Drop Salma.
    await user.click(within(third).getByRole('button', { name: strings.multi.remove }))
    expect(cards()).toHaveLength(2)
    expect(screen.getByRole('heading', { name: strings.multi.title(2) })).toBeInTheDocument()
    // Pick the Karim from Haat.
    await user.click(within(second).getByRole('button', { name: /Karim.*Haat/ }))
    // Fix Rahim's amount.
    await user.click(within(first).getByRole('button', { name: strings.edit }))
    const form = screen.getByRole('region', { name: strings.multi.editTitle(1) })
    const amount = within(form).getByLabelText(strings.amount)
    await user.clear(amount)
    await user.type(amount, '250')
    await user.click(within(form).getByRole('button', { name: strings.save }))
    expect(within(cards()[0]).getByTestId('amount')).toHaveTextContent('৳250')

    await user.click(screen.getByRole('button', { name: strings.multi.saveAll(2) }))

    expect(await screen.findByText(`✓ ${strings.multi.savedTitle(2)}`)).toBeInTheDocument()
    expect(api.bodiesOf(CONFIRM_MANY)).toEqual([
      {
        entries: [
          { raw_text: SENTENCE, type: 'credit', amount: 250, item: null, customer_id: 1 },
          { raw_text: SENTENCE, type: 'payment', amount: 500, item: null, customer_id: 2 },
        ],
      },
    ])
    const saved = screen.getAllByTestId('saved-entry')
    expect(saved[0]).toHaveTextContent('Rahim: ৳250 Baki')
    expect(saved[0]).toHaveTextContent('Baki ৳550')
    expect(saved[1]).toHaveTextContent('Agrim ৳500')
    expect(screen.getByLabelText(strings.entryLabel)).toHaveValue('')
  })

  it('dropping every card goes back to the box with the sentence', async () => {
    const { user } = await submit({})
    for (const card of cards()) await user.click(within(card).getByRole('button', { name: strings.multi.remove }))
    expect(screen.queryByTestId('multi-card')).not.toBeInTheDocument()
    expect(screen.getByLabelText(strings.entryLabel)).toHaveValue(SENTENCE)
  })

  it('a failed save says so and keeps every card', async () => {
    const { user } = await submit({ [CONFIRM_MANY]: 'network-error' })
    await user.click(within(cards()[1]).getByRole('button', { name: /Karim.*Haat/ }))
    await user.click(screen.getByRole('button', { name: strings.multi.saveAll(3) }))
    expect(await screen.findByText(strings.errors.network)).toBeInTheDocument()
    expect(cards()).toHaveLength(3)
  })
})

describe('the recent list after saving several', () => {
  it('shows the last entry of the sentence on top', async () => {
    const { user } = await submit({
      [CONFIRM_MANY]: (body) => {
        const [a, b, c] = (body as { entries: ParseConfirm[] }).entries
        const result = (who: typeof rahim, entry: ParseConfirm, id: number) => {
          const r = confirmResult(who, entry as never, 0)
          return { ...r, transaction: { ...r.transaction, id } }
        }
        return {
          status: 201,
          body: { results: [result(rahim, a, 1), result(karimA, b, 2), result(customer(9, 'Salma', 0), c, 3)] },
        }
      },
    })
    await user.click(within(cards()[1]).getByRole('button', { name: /Karim.*Haat/ }))
    await user.click(screen.getByRole('button', { name: strings.multi.saveAll(3) }))
    await screen.findByText(`✓ ${strings.multi.savedTitle(3)}`)
    const recent = within(screen.getByRole('region', { name: strings.recentTitle })).getAllByRole('link')
    expect(recent.map((row) => row.querySelector('p')?.textContent)).toEqual([
      'Salma',
      'Karim (Haat)',
      'Rahim (Bazar road)',
    ])
  })
})
