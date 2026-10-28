/** Settings: "AI bondho rakhun", the CSV download, and deleting the account. */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { getSession } from './session'
import { strings } from './strings'
import { DELETE_ME, EXPORT, ME, RECENT, TEST_USER, mockApi } from './test/mockApi'

function openSettings(handlers: Parameters<typeof mockApi>[0]) {
  const api = mockApi({ [RECENT]: { body: [] }, ...handlers })
  window.location.hash = '#/settings'
  render(<App />)
  return { api, user: userEvent.setup() }
}

describe('settings', () => {
  it('is opened from the header and shows the account', async () => {
    mockApi({ [RECENT]: { body: [] } })
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: strings.settings.open }))
    expect(screen.getByRole('heading', { name: strings.settings.title })).toBeInTheDocument()
    expect(screen.getByText('01700-000000')).toBeInTheDocument()
  })

  it('turns AI off: the switch, the saved login and the Hisab screen all say so', async () => {
    const { api, user } = openSettings({ [ME]: { body: { ...TEST_USER, ai_enabled: false } } })
    const toggle = screen.getByRole('switch', { name: strings.settings.aiTitle })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText(strings.settings.aiOnHint)).toBeInTheDocument()

    await user.click(toggle)

    expect(await screen.findByText(strings.settings.aiOffHint)).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    expect(api.bodiesOf(ME)).toEqual([{ ai_enabled: false }])
    expect(getSession()?.user.ai_enabled).toBe(false)

    await user.click(screen.getByRole('link', { name: strings.nav.hisab }))
    expect(screen.getByText(strings.settings.aiOffBanner)).toBeInTheDocument()
  })

  it('downloads the whole khata as a CSV file', async () => {
    // jsdom has no object URLs; the browser saves the file when the link is clicked.
    const createObjectURL = vi.fn(() => 'blob:khata')
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() })
    const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    try {
      const { api, user } = openSettings({ [EXPORT]: { body: 'customer_id,customer_name' } })

      await user.click(screen.getByRole('button', { name: strings.settings.exportButton }))

      await vi.waitFor(() => expect(clicked).toHaveBeenCalledTimes(1))
      const link = clicked.mock.contexts[0] as HTMLAnchorElement
      expect(link.href).toBe('blob:khata')
      expect(link.download).toBe('baki-khata.csv')
      expect(createObjectURL).toHaveBeenCalledTimes(1)
      expect(api.requests.map((r) => r.key)).toContain(EXPORT)
      expect(screen.queryByText(strings.settings.exportFailed)).not.toBeInTheDocument()
    } finally {
      Object.assign(URL, { createObjectURL: undefined, revokeObjectURL: undefined })
    }
  })

  it('says so when the download fails', async () => {
    const { user } = openSettings({ [EXPORT]: 'network-error' })
    await user.click(screen.getByRole('button', { name: strings.settings.exportButton }))
    expect(await screen.findByText(strings.settings.exportFailed)).toBeInTheDocument()
  })
})

describe('deleting the account', () => {
  it('asks first, needs the password, then logs out with everything gone', async () => {
    const { api, user } = openSettings({
      [DELETE_ME]: (body) =>
        (body as { password: string }).password === 'secret-pass-1'
          ? { status: 204 }
          : { status: 403, body: { detail: 'Wrong password' } },
    })

    await user.click(screen.getByRole('button', { name: strings.settings.deleteButton }))
    const dialog = screen.getByRole('dialog', { name: strings.settings.deleteConfirmTitle })
    expect(dialog).toHaveTextContent(strings.settings.deleteConfirmBody)

    // "Na, rakhun" closes it and nothing happens.
    await user.click(within(dialog).getByRole('button', { name: strings.settings.deleteConfirmNo }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(api.requests.filter((r) => r.key === DELETE_ME)).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: strings.settings.deleteButton }))
    const again = screen.getByRole('dialog', { name: strings.settings.deleteConfirmTitle })
    const yes = within(again).getByRole('button', { name: strings.settings.deleteConfirmYes })
    await user.click(yes)
    expect(within(again).getByText(strings.auth.passwordRequired)).toBeInTheDocument()

    await user.type(within(again).getByLabelText(strings.auth.password), 'wrong-one')
    await user.click(yes)
    expect(await within(again).findByText(strings.settings.wrongPassword)).toBeInTheDocument()
    expect(getSession()).not.toBeNull()

    await user.clear(within(again).getByLabelText(strings.auth.password))
    await user.type(within(again).getByLabelText(strings.auth.password), 'secret-pass-1')
    await user.click(yes)

    expect(await screen.findByRole('heading', { name: strings.auth.loginTitle })).toBeInTheDocument()
    expect(screen.getByText(strings.auth.accountDeleted)).toBeInTheDocument()
    expect(api.bodiesOf(DELETE_ME)).toEqual([{ password: 'wrong-one' }, { password: 'secret-pass-1' }])
    expect(getSession()).toBeNull()
  })
})
