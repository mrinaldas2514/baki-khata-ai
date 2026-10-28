/**
 * The core flow with the backend mocked: type a sentence, see the confirmation card in each
 * name-matching state (matched, ambiguous, new customer), the error fallback, then save.
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import { strings } from './strings'
import {
  CONFIRM,
  CUSTOMERS,
  PARSE,
  RECENT,
  candidate,
  confirmResult,
  customer,
  mockApi,
  preview,
  recentRow,
} from './test/mockApi'

const salma = customer(3, 'Salma', 200)
const rahimBazar = customer(1, 'Rahim', 300, 'Bazar road')
const rahimTea = customer(2, 'Rahim', 60, 'Tea stall')

async function submit(sentence: string) {
  const user = userEvent.setup()
  render(<App />)
  await user.type(screen.getByLabelText(strings.entryLabel), sentence)
  await user.click(screen.getByRole('button', { name: strings.submit }))
  return user
}

function card() {
  return screen.getByRole('region', { name: strings.confirmTitle })
}

describe('who read the sentence', () => {
  it('labels an AI reading "AI", with the model name on hover', async () => {
    mockApi({ [RECENT]: { body: [] }, [PARSE]: { body: preview({}) } })
    await submit('salma apa pach sho taka baki, dal r tel')

    const label = within(await screen.findByRole('region', { name: strings.confirmTitle })).getByTestId('parser-label')
    expect(label).toHaveTextContent(strings.parser.llm)
    expect(label).toHaveAttribute('title', strings.parser.llmTitle('openai/gpt-oss-120b'))
  })

  it('labels the rule-based parser "AI chhara"', async () => {
    mockApi({ [RECENT]: { body: [] }, [PARSE]: { body: preview({ parser: 'rules' }) } })
    await submit('salma apa pach sho taka baki, dal r tel')

    const label = within(await screen.findByRole('region', { name: strings.confirmTitle })).getByTestId('parser-label')
    expect(label).toHaveTextContent(strings.parser.rules)
    expect(label).toHaveAttribute('title', strings.parser.rulesTitle)
  })
})

describe('matched customer', () => {
  const matched = preview({
    match: { status: 'exact', customer: candidate(salma), candidates: [candidate(salma)], suggested_name: 'Salma' },
  })

  it('shows the customer, current balance, big amount, type and item', async () => {
    mockApi({ [RECENT]: { body: [] }, [PARSE]: { body: matched } })
    await submit('salma apa pach sho taka baki, dal r tel')

    const confirm = await screen.findByRole('region', { name: strings.confirmTitle })
    const summary = within(confirm).getByTestId('customer-summary')
    expect(summary).toHaveTextContent('Salma')
    expect(summary).toHaveTextContent('Ekhon: Baki ৳200')
    expect(within(confirm).getByTestId('amount')).toHaveTextContent('৳500')
    expect(within(confirm).getByTestId('amount')).toHaveClass('text-red-700')
    expect(confirm).toHaveTextContent(strings.typeCredit)
    expect(confirm).toHaveTextContent('Jinis: dal, tel')
    expect(within(confirm).queryByText(strings.newCustomer)).not.toBeInTheDocument()
  })

  it('saves to the matched customer, shows the new balance and adds it to the recent list', async () => {
    const api = mockApi({
      [RECENT]: { body: [recentRow(7, rahimBazar, 300, 'credit')] },
      [PARSE]: { body: matched },
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(salma, body as never, 700) }),
    })
    const user = await submit('salma apa pach sho taka baki, dal r tel')

    await user.click(
      await within(await screen.findByRole('region', { name: strings.confirmTitle })).findByRole('button', {
        name: strings.save,
      }),
    )

    expect(await screen.findByText(`✓ ${strings.savedTitle}`)).toBeInTheDocument()
    expect(screen.getByTestId('new-balance')).toHaveTextContent('Baki ৳700')
    expect(api.bodiesOf(CONFIRM)).toEqual([
      { raw_text: matched.raw_text, type: 'credit', amount: 500, item: 'dal, tel', customer_id: salma.id },
    ])
    const rows = within(screen.getByRole('region', { name: strings.recentTitle })).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('Salma')
    expect(rows[0]).toHaveTextContent('৳500')
    // Ready for the next entry.
    expect(screen.getByLabelText(strings.entryLabel)).toHaveValue('')
  })

  it('shows a payment in green', async () => {
    mockApi({
      [RECENT]: { body: [] },
      [PARSE]: {
        body: preview({
          raw_text: 'salma 300 dilo',
          parsed: { type: 'payment', amount: 300, item: null },
          match: { status: 'exact', customer: candidate(salma), suggested_name: 'Salma' },
        }),
      },
    })
    await submit('salma 300 dilo')

    const amount = await screen.findByTestId('amount')
    expect(amount).toHaveClass('text-green-700')
    expect(card()).toHaveTextContent(strings.typePayment)
    expect(card()).toHaveTextContent(strings.typePaymentHint)
  })

  it('asks to double-check a fuzzy match', async () => {
    mockApi({
      [RECENT]: { body: [] },
      [PARSE]: {
        body: preview({
          parsed: { customer_name: 'shalma' },
          match: { status: 'fuzzy', customer: candidate(salma, 94), candidates: [candidate(salma, 94)] },
        }),
      },
    })
    await submit('shalma 500 baki')

    expect(
      await within(await screen.findByRole('region', { name: strings.confirmTitle })).findByRole('alert'),
    ).toHaveTextContent(strings.fuzzyMatch('shalma', 'Salma'))
  })
})

describe('ambiguous customer', () => {
  const ambiguous = preview({
    raw_text: 'rahim 100 taka baki',
    parsed: { customer_name: 'rahim', amount: 100, item: null },
    match: {
      status: 'ambiguous',
      customer: null,
      candidates: [candidate(rahimBazar), candidate(rahimTea)],
      suggested_name: 'Rahim',
    },
  })

  it('lists the candidates as big buttons plus "Notun customer", and waits for a choice', async () => {
    mockApi({ [RECENT]: { body: [] }, [PARSE]: { body: ambiguous } })
    await submit('rahim 100 taka baki')

    const confirm = await screen.findByRole('region', { name: strings.confirmTitle })
    expect(within(confirm).getByText(strings.whichCustomer)).toBeInTheDocument()
    expect(within(confirm).getByRole('button', { name: /Rahim \(Bazar road\)/ })).toHaveTextContent('Baki ৳300')
    expect(within(confirm).getByRole('button', { name: /Rahim \(Tea stall\)/ })).toHaveTextContent('Baki ৳60')
    expect(within(confirm).getByRole('button', { name: /Notun customer: Rahim/ })).toBeInTheDocument()
    expect(within(confirm).getByRole('button', { name: strings.pickCustomerFirst })).toBeDisabled()
  })

  it('saves to the customer the shopkeeper picked', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [PARSE]: { body: ambiguous },
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(rahimTea, body as never, 160) }),
    })
    const user = await submit('rahim 100 taka baki')

    const confirm = await screen.findByRole('region', { name: strings.confirmTitle })
    const teaStall = within(confirm).getByRole('button', { name: /Rahim \(Tea stall\)/ })
    await user.click(teaStall)
    expect(teaStall).toHaveAttribute('aria-pressed', 'true')
    await user.click(within(confirm).getByRole('button', { name: strings.save }))

    expect(await screen.findByTestId('new-balance')).toHaveTextContent('Baki ৳160')
    expect(api.bodiesOf(CONFIRM)[0]).toMatchObject({ customer_id: rahimTea.id, amount: 100 })
  })

  it('can create a new customer instead', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [PARSE]: { body: ambiguous },
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(customer(9, 'Rahim', 0), body as never, 100, true) }),
    })
    const user = await submit('rahim 100 taka baki')

    await user.click(await screen.findByRole('button', { name: /Notun customer: Rahim/ }))
    await user.click(within(card()).getByRole('button', { name: strings.save }))

    await screen.findByTestId('new-balance')
    expect(api.bodiesOf(CONFIRM)[0]).toMatchObject({ new_customer: { name: 'Rahim', note: null } })
    expect(api.bodiesOf(CONFIRM)[0]).not.toHaveProperty('customer_id')
  })
})

describe('new customer', () => {
  const fresh = preview({
    raw_text: 'tanvir 90 taka baki',
    parsed: { customer_name: 'tanvir', amount: 90, item: null },
    match: { status: 'new', customer: null, candidates: [], suggested_name: 'Tanvir' },
  })

  it('says clearly that a new customer will be created, then creates it on save', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [PARSE]: { body: fresh },
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(customer(10, 'Tanvir', 0), body as never, 90, true) }),
    })
    const user = await submit('tanvir 90 taka baki')

    const confirm = await screen.findByRole('region', { name: strings.confirmTitle })
    const summary = within(confirm).getByTestId('customer-summary')
    expect(summary).toHaveTextContent(strings.newCustomer)
    expect(summary).toHaveTextContent('Notun customer: Tanvir')

    await user.click(within(confirm).getByRole('button', { name: strings.save }))

    expect(await screen.findByText(strings.savedNewCustomer('Tanvir'))).toBeInTheDocument()
    expect(screen.getByTestId('new-balance')).toHaveTextContent('Baki ৳90')
    expect(api.bodiesOf(CONFIRM)[0]).toEqual({
      raw_text: 'tanvir 90 taka baki',
      type: 'credit',
      amount: 90,
      item: null,
      new_customer: { name: 'Tanvir', note: null },
    })
  })

  it('keeps the card open with a friendly message when saving fails', async () => {
    mockApi({
      [RECENT]: { body: [] },
      [PARSE]: { body: fresh },
      [CONFIRM]: { status: 409, body: { detail: "A customer named 'Tanvir' without a note already exists" } },
    })
    const user = await submit('tanvir 90 taka baki')

    await user.click(
      await within(await screen.findByRole('region', { name: strings.confirmTitle })).findByRole('button', {
        name: strings.save,
      }),
    )

    expect(await within(card()).findByRole('alert')).toHaveTextContent(strings.errors.duplicateCustomer)
    expect(within(card()).getByRole('button', { name: strings.save })).toBeEnabled()
  })
})

describe('edit mode', () => {
  it('lets the shopkeeper correct amount, type and item before saving', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: [salma, rahimBazar] },
      [PARSE]: {
        body: preview({ match: { status: 'exact', customer: candidate(salma), candidates: [candidate(salma)] } }),
      },
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(salma, body as never, -400) }),
    })
    const user = await submit('salma apa pach sho taka baki, dal r tel')

    await user.click(await screen.findByRole('button', { name: strings.edit }))
    const form = screen.getByRole('region', { name: strings.editTitle })
    expect(within(form).getByLabelText(strings.customer)).toHaveValue('Salma')
    const amount = within(form).getByLabelText(strings.amount)
    expect(amount).toHaveValue('500')
    await user.clear(amount)
    await user.type(amount, '৬০০')
    await user.click(within(form).getByRole('radio', { name: new RegExp(strings.typePayment) }))
    await user.clear(within(form).getByLabelText(strings.item))
    await user.click(within(form).getByRole('button', { name: strings.save }))

    expect(await screen.findByTestId('new-balance')).toHaveTextContent('Agrim ৳400')
    expect(api.bodiesOf(CONFIRM)[0]).toMatchObject({ customer_id: salma.id, amount: 600, type: 'payment', item: null })
  })

  it('changing the name turns it into a new customer unless an existing one is picked', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: [salma, rahimBazar, rahimTea] },
      [PARSE]: {
        body: preview({ match: { status: 'exact', customer: candidate(salma), candidates: [candidate(salma)] } }),
      },
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(rahimBazar, body as never, 800) }),
    })
    const user = await submit('salma apa pach sho taka baki, dal r tel')

    await user.click(await screen.findByRole('button', { name: strings.edit }))
    const form = screen.getByRole('region', { name: strings.editTitle })
    const name = within(form).getByLabelText(strings.customer)
    await user.clear(name)
    await user.type(name, 'rahim')
    expect(within(form).getByText('Notun customer: rahim')).toBeInTheDocument()
    await user.click(await within(form).findByRole('button', { name: /Rahim \(Bazar road\)/ }))
    expect(within(form).queryByText(/Notun customer:/)).not.toBeInTheDocument()
    await user.click(within(form).getByRole('button', { name: strings.save }))

    await screen.findByTestId('new-balance')
    expect(api.bodiesOf(CONFIRM)[0]).toMatchObject({ customer_id: rahimBazar.id })
  })

  it('goes back to the entry box on cancel, keeping the sentence', async () => {
    mockApi({
      [RECENT]: { body: [] },
      [PARSE]: { body: preview({ match: { status: 'new', suggested_name: 'Salma' } }) },
    })
    const user = await submit('salma 500 baki')

    await user.click(await screen.findByRole('button', { name: strings.cancel }))
    expect(screen.queryByRole('region', { name: strings.confirmTitle })).not.toBeInTheDocument()
    expect(screen.getByLabelText(strings.entryLabel)).toHaveValue('salma 500 baki')
  })
})

describe('errors fall back to manual entry', () => {
  it.each([
    ['network failure', 'network-error' as const, strings.errors.network],
    ['AI gave a bad answer', { status: 502, body: { detail: 'invalid answer twice' } }, strings.errors.aiFailed],
    ['AI not reachable', { status: 503, body: { detail: 'not reachable' } }, strings.errors.aiUnavailable],
    ['no name or amount', { status: 422, body: { detail: 'no amount' } }, strings.errors.notTransaction],
  ])('%s: friendly message and an empty manual form', async (_case, answer, message) => {
    mockApi({ [RECENT]: { body: [] }, [CUSTOMERS]: { body: [] }, [PARSE]: answer })
    await submit('rina kichu nilo')

    const form = await screen.findByRole('region', { name: strings.manualTitle })
    expect(within(form).getByRole('alert')).toHaveTextContent(message)
    expect(within(form).getByLabelText(strings.customer)).toHaveValue('')
    expect(within(form).getByLabelText(strings.amount)).toHaveValue('')
    expect(within(form).getByRole('radio', { name: new RegExp(strings.typeCredit) })).toBeChecked()
  })

  it('saves a manual entry with the original sentence as raw_text', async () => {
    const api = mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: [salma] },
      [PARSE]: 'network-error',
      [CONFIRM]: (body) => ({ status: 201, body: confirmResult(customer(11, 'Rina', 0), body as never, 250, true) }),
    })
    const user = await submit('rina 250 er jinis nilo')

    const form = await screen.findByRole('region', { name: strings.manualTitle })
    await user.click(within(form).getByRole('button', { name: strings.save }))
    expect(within(form).getByText(strings.nameRequired)).toBeInTheDocument()
    expect(within(form).getByText(strings.amountInvalid)).toBeInTheDocument()

    await user.type(within(form).getByLabelText(strings.customer), 'Rina')
    await user.type(within(form).getByLabelText(strings.amount), '250')
    await user.type(within(form).getByLabelText(strings.item), 'saban')
    await user.click(within(form).getByRole('button', { name: strings.save }))

    expect(await screen.findByTestId('new-balance')).toHaveTextContent('Baki ৳250')
    expect(api.bodiesOf(CONFIRM)[0]).toEqual({
      raw_text: 'rina 250 er jinis nilo',
      type: 'credit',
      amount: 250,
      item: 'saban',
      new_customer: { name: 'Rina', note: null },
    })
  })

  it('low confidence: opens the form prefilled with the AI guess to check', async () => {
    mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: [] },
      [PARSE]: {
        body: preview({
          parsed: { confidence: 0.5, amount: 700 },
          match: { status: 'new', suggested_name: 'Salma' },
          warnings: ['The amount 700 was not found in the sentence. Please check it.'],
        }),
      },
    })
    await submit('salma apa pach sho baki')

    const form = await screen.findByRole('region', { name: strings.editTitle })
    expect(within(form).getByRole('alert')).toHaveTextContent(strings.errors.lowConfidence)
    expect(within(form).getByLabelText(strings.customer)).toHaveValue('Salma')
    expect(within(form).getByLabelText(strings.amount)).toHaveValue('700')
    expect(screen.queryByRole('region', { name: strings.confirmTitle })).not.toBeInTheDocument()
  })
})

describe('home screen', () => {
  it('shows the last transactions with name, amount and type', async () => {
    mockApi({
      [RECENT]: { body: [recentRow(2, salma, 300, 'payment'), recentRow(1, rahimBazar, 120, 'credit')] },
    })
    render(<App />)

    const rows = await within(screen.getByRole('region', { name: strings.recentTitle })).findAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Salma')
    expect(rows[0]).toHaveTextContent('৳300')
    expect(rows[0]).toHaveTextContent(strings.typePayment)
    expect(rows[1]).toHaveTextContent('Rahim (Bazar road)')
    expect(rows[1]).toHaveTextContent(strings.typeCredit)
  })

  it('shows a loading state while the AI reads the sentence', async () => {
    mockApi({ [RECENT]: { body: [] }, [PARSE]: () => new Promise(() => {}) })
    await submit('salma 500 baki')

    expect(screen.getByText(strings.parsing)).toBeInTheDocument()
    expect(screen.getByLabelText(strings.entryLabel)).toBeDisabled()
  })
})
