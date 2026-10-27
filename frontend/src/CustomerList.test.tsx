/** The bottom tabs and the customer list: sorting, search in both scripts, opening a khata. */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import { strings } from './strings'
import { CUSTOMERS, DASHBOARD, RECENT, ledgerKey, ledgerPage, listItem, mockApi } from './test/mockApi'

const CUSTOMER_LIST = [
  listItem(1, 'Rahim', 300, { note: 'Bazar road', phone: '01711-000001', owedSince: '2026-09-10T00:00:00Z' }),
  listItem(2, 'Salma', 0),
  listItem(3, 'Jasim', 1500, { owedSince: '2026-10-20T00:00:00Z' }),
  listItem(4, 'Abul', -200),
  listItem(5, 'আয়েশা', 750, { owedSince: '2026-08-01T00:00:00Z' }),
]

function openCustomers() {
  mockApi({ [RECENT]: { body: [] }, [CUSTOMERS]: { body: CUSTOMER_LIST } })
  window.location.hash = '#/customers'
  render(<App />)
  return userEvent.setup()
}

async function shownNames() {
  const list = await screen.findByRole('list', { name: strings.customersTitle })
  return within(list)
    .getAllByRole('link')
    .map((row) => row.querySelector('p')?.textContent)
}

describe('bottom navigation', () => {
  it('has three tabs and marks the open one', async () => {
    mockApi({ [RECENT]: { body: [] }, [CUSTOMERS]: { body: CUSTOMER_LIST }, [DASHBOARD]: 'network-error' })
    const user = userEvent.setup()
    render(<App />)

    const nav = screen.getByRole('navigation', { name: strings.nav.label })
    const tabs = within(nav).getAllByRole('link')
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      strings.nav.hisab,
      strings.nav.customers,
      strings.nav.dashboard,
    ])
    expect(within(nav).getByRole('link', { name: strings.nav.hisab })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByLabelText(strings.entryLabel)).toBeVisible()

    await user.click(within(nav).getByRole('link', { name: strings.nav.customers }))
    expect(await screen.findByRole('heading', { name: strings.customersTitle })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: strings.nav.customers })).toHaveAttribute('aria-current', 'page')
    // The entry screen stays (hidden) so a half-typed sentence isn't lost.
    expect(screen.getByLabelText(strings.entryLabel)).not.toBeVisible()

    await user.click(within(nav).getByRole('link', { name: strings.nav.dashboard }))
    expect(await screen.findByText(strings.dashboardFailed)).toBeInTheDocument()
  })
})

describe('customer list', () => {
  it('shows each balance in words and colour, biggest baki first', async () => {
    openCustomers()

    expect(await shownNames()).toEqual(['Jasim', 'আয়েশা', 'Rahim', 'Abul', 'Salma'])
    const balances = screen.getAllByTestId('customer-balance')
    expect(balances[0]).toHaveTextContent('Baki ৳1,500')
    expect(balances[0]).toHaveClass('text-red-700')
    expect(balances[3]).toHaveTextContent('Agrim ৳200')
    expect(balances[3]).toHaveClass('text-green-700')
    expect(balances[4]).toHaveTextContent(`✓ ${strings.balanceClearShort}`)
    expect(balances[4]).toHaveClass('text-green-700')
    expect(screen.getByText(strings.customersWithBaki(3, '৳2,550'))).toBeInTheDocument()
    expect(screen.getByRole('button', { name: strings.sort['most-owed'] })).toHaveAttribute('aria-pressed', 'true')
  })

  it('sorts by oldest baki and by name', async () => {
    const user = openCustomers()
    await shownNames()

    await user.click(screen.getByRole('button', { name: strings.sort['oldest-owed'] }))
    expect(await shownNames()).toEqual(['আয়েশা', 'Rahim', 'Jasim', 'Abul', 'Salma'])
    expect(screen.getByRole('button', { name: strings.sort['oldest-owed'] })).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: strings.sort.name }))
    expect(await shownNames()).toEqual(['Abul', 'Jasim', 'Rahim', 'Salma', 'আয়েশা'])
  })

  it('searches English and Bangla names, areas and phone numbers', async () => {
    const user = openCustomers()
    const search = await screen.findByLabelText(strings.searchLabel)

    await user.type(search, 'রহিম')
    expect(await shownNames()).toEqual(['Rahim'])

    await user.clear(search)
    await user.type(search, 'ayesha')
    expect(await shownNames()).toEqual(['আয়েশা'])

    await user.clear(search)
    await user.type(search, 'bazar')
    expect(await shownNames()).toEqual(['Rahim'])

    await user.clear(search)
    await user.type(search, '01711')
    expect(await shownNames()).toEqual(['Rahim'])

    await user.clear(search)
    await user.type(search, 'tanvir')
    expect(screen.getByText(strings.noSearchResult('tanvir'))).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: strings.clearSearch }))
    expect(await shownNames()).toHaveLength(5)
  })

  it('opens the khata of the tapped customer, and keeps the search on the way back', async () => {
    const rahim = CUSTOMER_LIST[0]
    mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: { body: CUSTOMER_LIST },
      [ledgerKey(rahim.id)]: { body: ledgerPage(rahim, []) },
    })
    window.location.hash = '#/customers'
    const user = userEvent.setup()
    render(<App />)

    await user.type(await screen.findByLabelText(strings.searchLabel), 'rah')
    await user.click(await screen.findByRole('link', { name: /Rahim/ }))

    expect(await screen.findByRole('heading', { name: 'Rahim', level: 2 })).toBeInTheDocument()
    expect(window.location.hash).toBe('#/customers/1')

    await user.click(screen.getByRole('link', { name: new RegExp(strings.backToCustomers) }))
    await waitFor(() => expect(screen.getByLabelText(strings.searchLabel)).toHaveValue('rah'))
  })

  it('says so when the list could not load, and retries', async () => {
    let calls = 0
    mockApi({
      [RECENT]: { body: [] },
      [CUSTOMERS]: () => (++calls === 1 ? 'network-error' : { body: CUSTOMER_LIST }),
    })
    window.location.hash = '#/customers'
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: strings.retry }))
    expect(await shownNames()).toHaveLength(5)
  })
})
