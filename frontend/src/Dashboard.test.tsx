import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import type { Dashboard } from './api/types'
import { strings } from './strings'
import { DASHBOARD, RECENT, mockApi } from './test/mockApi'

const DATA: Dashboard = {
  total_outstanding: 125000,
  customers_with_baki: 6,
  today: '2026-10-27',
  today_collection: 1500,
  today_new_credit: 320,
  top_customers: [
    { id: 4, name: 'Jasim', phone: null, note: null, balance: 1500 },
    { id: 1, name: 'Rahim', phone: null, note: 'Bazar road', balance: 300 },
  ],
  overdue_days: 30,
  overdue_customers: [
    {
      id: 4,
      name: 'Jasim',
      phone: null,
      note: null,
      balance: 1500,
      owed_since: '2026-09-22T06:00:00Z',
      days_outstanding: 35,
    },
  ],
  last_7_days: [
    { date: '2026-10-21', credit: 500, payment: 0 },
    { date: '2026-10-22', credit: 0, payment: 0 },
    { date: '2026-10-23', credit: 1200, payment: 300 },
    { date: '2026-10-24', credit: 0, payment: 200 },
    { date: '2026-10-25', credit: 850, payment: 0 },
    { date: '2026-10-26', credit: 120, payment: 1000 },
    { date: '2026-10-27', credit: 320, payment: 1500 },
  ],
}

function openDashboard(data: Dashboard = DATA) {
  mockApi({ [RECENT]: { body: [] }, [DASHBOARD]: { body: data } })
  window.location.hash = '#/dashboard'
  render(<App />)
  return userEvent.setup()
}

describe('dashboard', () => {
  it('shows the three big numbers', async () => {
    openDashboard()
    expect(await screen.findByTestId('stat-total')).toHaveTextContent(`${strings.totalBaki}৳1,25,000`)
    expect(screen.getByTestId('stat-total')).toHaveTextContent(strings.totalBakiFrom(6))
    expect(screen.getByTestId('stat-today-payment')).toHaveTextContent(`${strings.todayPayment}৳1,500`)
    expect(screen.getByTestId('stat-today-credit')).toHaveTextContent(`${strings.todayNewCredit}৳320`)
  })

  it('lists the top customers and the old baki, each linking to the khata', async () => {
    openDashboard()
    const top = await screen.findByRole('list', { name: strings.topTitle })
    expect(
      within(top)
        .getAllByRole('link')
        .map((a) => a.getAttribute('href')),
    ).toEqual(['#/customers/4', '#/customers/1'])
    expect(top).toHaveTextContent('Rahim')
    expect(top).toHaveTextContent('Bazar road')
    const overdue = screen.getByRole('list', { name: `⚠ ${strings.overdueTitle(30)}` })
    expect(overdue).toHaveTextContent('Jasim')
    expect(overdue).toHaveTextContent(strings.overdueSince(35))
    expect(overdue).toHaveTextContent('22 Sept theke')
  })

  it('charts the last 7 days; tapping a day reads out its numbers', async () => {
    const user = openDashboard()
    expect(await screen.findByTestId('week-detail')).toHaveTextContent(
      strings.weekDayDetail(`${strings.today} (27 Oct)`, '৳320', '৳1,500'),
    )
    const days = within(screen.getByRole('group', { name: strings.weekTitle })).getAllByRole('button')
    expect(days).toHaveLength(7)
    await user.click(days[2])
    expect(screen.getByTestId('week-detail')).toHaveTextContent(strings.weekDayDetail('23 Oct', '৳1,200', '৳300'))
    expect(days[2]).toHaveAttribute('aria-pressed', 'true')
    // The same numbers as a table for screen readers.
    const table = screen.getByRole('table', { name: strings.weekTableCaption })
    expect(within(table).getAllByRole('row')).toHaveLength(8)
  })

  it('says when there is nothing to show', async () => {
    openDashboard({
      ...DATA,
      total_outstanding: 0,
      customers_with_baki: 0,
      top_customers: [],
      overdue_customers: [],
      last_7_days: DATA.last_7_days.map((d) => ({ ...d, credit: 0, payment: 0 })),
    })
    expect(await screen.findByText(strings.topEmpty)).toBeInTheDocument()
    expect(screen.getByText(strings.overdueEmpty(30))).toBeInTheDocument()
    expect(screen.getByText(strings.weekEmpty)).toBeInTheDocument()
  })
})
