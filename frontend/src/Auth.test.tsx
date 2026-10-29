/** Login, register (with the privacy note), staying logged in, logout, and an expired login. */
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { CONSENT_VERSION, DEMO_LOGIN } from './config'
import { endSession, getSession, setSession } from './session'
import { strings } from './strings'
import { LOGIN, LOGOUT, RECENT, REGISTER, TEST_SESSION, TRANSCRIBE_STATUS, authResult, mockApi } from './test/mockApi'

describe('login', () => {
  beforeEach(() => {
    endSession('logout')
  })

  it('shows the login screen when nobody is logged in, then the app after login', async () => {
    const api = mockApi({
      [LOGIN]: { body: authResult({ name: 'Karim', shop: { ...TEST_SESSION.user.shop, name: 'Karim Store' } }) },
      [RECENT]: { body: [] },
    })
    const user = userEvent.setup()
    render(<App />)

    expect(screen.getByRole('heading', { name: strings.auth.loginTitle })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: strings.nav.label })).not.toBeInTheDocument()

    await user.type(screen.getByLabelText(strings.auth.loginLabel), ' 01711-000001 ')
    await user.type(screen.getByLabelText(strings.auth.password), 'secret-pass-1')
    await user.click(screen.getByRole('button', { name: strings.auth.loginButton }))

    expect(await screen.findByLabelText(strings.entryLabel)).toBeInTheDocument()
    expect(screen.getByText('Karim Store')).toBeInTheDocument()
    expect(api.bodiesOf(LOGIN)).toEqual([{ login: '01711-000001', password: 'secret-pass-1' }])
    expect(getSession()?.token).toBe('new-token')
    // Every request after login carries the token.
    const recent = api.requests.find((r) => r.key === RECENT)
    expect(recent?.headers.get('Authorization')).toBe('Bearer new-token')
  })

  it('shows and hides the password', async () => {
    mockApi({})
    const user = userEvent.setup()
    render(<App />)
    const password = screen.getByLabelText(strings.auth.password)
    const toggle = screen.getByRole('button', { name: strings.auth.showPassword })
    expect(password).toHaveAttribute('type', 'password')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')

    await user.click(toggle)
    expect(password).toHaveAttribute('type', 'text')
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(toggle).toHaveTextContent(strings.auth.hide)
    await user.click(toggle)
    expect(password).toHaveAttribute('type', 'password')
  })

  it('says so on a wrong password, and stays on the login screen', async () => {
    mockApi({ [LOGIN]: { status: 401, body: { detail: 'Wrong phone/email or password' } } })
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText(strings.auth.loginLabel), '01711000001')
    await user.type(screen.getByLabelText(strings.auth.password), 'nope-nope')
    await user.click(screen.getByRole('button', { name: strings.auth.loginButton }))

    expect(await screen.findByText(strings.auth.wrongLogin)).toBeInTheDocument()
    expect(getSession()).toBeNull()
  })

  it('asks for both fields before sending anything', async () => {
    const api = mockApi({})
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: strings.auth.loginButton }))
    expect(screen.getByText(strings.auth.loginRequired)).toBeInTheDocument()
    expect(screen.getByText(strings.auth.passwordRequired)).toBeInTheDocument()
    expect(api.requests).toHaveLength(0)
  })

  it('shows a friendly message when there were too many tries', async () => {
    mockApi({ [LOGIN]: { status: 429, body: { detail: 'Too many', retry_after: 42 } } })
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText(strings.auth.loginLabel), '01711000001')
    await user.type(screen.getByLabelText(strings.auth.password), 'whatever1')
    await user.click(screen.getByRole('button', { name: strings.auth.loginButton }))
    expect(await screen.findByText(strings.errors.rateLimited(42))).toBeInTheDocument()
  })

  it('shows the demo login only when VITE_SHOW_DEMO_LOGIN=true', () => {
    mockApi({})
    const { unmount } = render(<App />)
    expect(screen.queryByTestId('demo-login')).not.toBeInTheDocument()
    unmount()

    vi.stubEnv('VITE_SHOW_DEMO_LOGIN', 'true')
    try {
      render(<App />)
      expect(screen.getByTestId('demo-login')).toHaveTextContent(
        `${strings.auth.demoLogin}: ${DEMO_LOGIN.phone} / ${DEMO_LOGIN.password}`,
      )
    } finally {
      vi.unstubAllEnvs()
    }
  })
})

describe('register', () => {
  beforeEach(() => {
    endSession('logout')
    window.location.hash = '#/register'
  })

  async function fillIn(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText(strings.auth.yourName), 'Karim')
    await user.type(screen.getByLabelText(strings.auth.shopName), 'Karim Store')
    await user.type(screen.getByLabelText(strings.auth.phone), '01711-000001')
    await user.type(screen.getByLabelText(strings.auth.newPassword), 'secret-pass-1')
  }

  it('shows the privacy note, which must be ticked to continue', async () => {
    const api = mockApi({ [REGISTER]: { status: 201, body: authResult() }, [RECENT]: { body: [] } })
    const user = userEvent.setup()
    render(<App />)

    for (const point of strings.consent.points) expect(screen.getByText(point)).toBeInTheDocument()
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: strings.auth.registerButton }))
    expect(screen.getByText(strings.auth.consentRequired)).toBeInTheDocument()
    expect(api.requests).toHaveLength(0)

    await user.click(screen.getByRole('checkbox', { name: strings.consent.agree }))
    await user.click(screen.getByRole('button', { name: strings.auth.registerButton }))

    expect(await screen.findByLabelText(strings.entryLabel)).toBeInTheDocument()
    expect(api.bodiesOf(REGISTER)).toEqual([
      {
        name: 'Karim',
        shop_name: 'Karim Store',
        phone: '01711-000001',
        email: null,
        password: 'secret-pass-1',
        consent: true,
        consent_version: CONSENT_VERSION,
      },
    ])
    expect(window.location.hash).toBe('#/')
  })

  it('checks the phone number and password length on the phone first', async () => {
    const api = mockApi({})
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText(strings.auth.yourName), 'Karim')
    await user.type(screen.getByLabelText(strings.auth.shopName), 'Karim Store')
    await user.type(screen.getByLabelText(strings.auth.phone), '12345')
    await user.type(screen.getByLabelText(strings.auth.newPassword), 'short')
    await user.click(screen.getByRole('checkbox', { name: strings.consent.agree }))
    await user.click(screen.getByRole('button', { name: strings.auth.registerButton }))

    expect(screen.getByText(strings.customerForm.phoneInvalid)).toBeInTheDocument()
    expect(screen.getByText(strings.auth.passwordShort)).toBeInTheDocument()
    expect(api.requests).toHaveLength(0)
  })

  it('says when the number already has an account', async () => {
    mockApi({ [REGISTER]: { status: 409, body: { detail: 'exists' } } })
    const user = userEvent.setup()
    render(<App />)
    await fillIn(user)
    await user.click(screen.getByRole('checkbox', { name: strings.consent.agree }))
    await user.click(screen.getByRole('button', { name: strings.auth.registerButton }))
    expect(await screen.findByText(strings.auth.accountExists)).toBeInTheDocument()
  })
})

describe('staying logged in', () => {
  it('keeps the login across a reload (it is saved on the phone)', async () => {
    setSession({ ...TEST_SESSION, token: 'saved-token' })
    vi.resetModules()
    const reloaded = await import('./session')
    expect(reloaded.getSession()?.token).toBe('saved-token')
    expect(reloaded.getSession()?.user.shop.id).toBe(1)
  })

  it('goes back to the login screen when the backend says the login ended (401)', async () => {
    mockApi({ [RECENT]: { status: 401, body: { detail: 'Login has expired' } } })
    render(<App />)
    expect(await screen.findByRole('heading', { name: strings.auth.loginTitle })).toBeInTheDocument()
    expect(screen.getByText(strings.auth.sessionExpired)).toBeInTheDocument()
    expect(getSession()).toBeNull()
    expect(localStorage.getItem('baki-khata.session')).toBeNull()
  })

  it('logs out by itself when the token expires', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      mockApi({ [RECENT]: { body: [] }, [TRANSCRIBE_STATUS]: { body: { available: false } } })
      setSession({ ...TEST_SESSION, expiresAt: new Date(Date.now() + 60_000).toISOString() })
      render(<App />)
      expect(screen.getByLabelText(strings.entryLabel)).toBeInTheDocument()

      await act(async () => {
        vi.advanceTimersByTime(61_000)
      })
      expect(screen.getByRole('heading', { name: strings.auth.loginTitle })).toBeInTheDocument()
      expect(screen.getByText(strings.auth.sessionExpired)).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('an already expired saved login opens the login screen', () => {
    mockApi({})
    setSession({ ...TEST_SESSION, expiresAt: '2020-01-01T00:00:00Z' })
    render(<App />)
    expect(screen.getByRole('heading', { name: strings.auth.loginTitle })).toBeInTheDocument()
  })
})

describe('logout', () => {
  it('tells the server, forgets the login and shows the login screen', async () => {
    const api = mockApi({ [LOGOUT]: { status: 204 }, [RECENT]: { body: [] } })
    window.location.hash = '#/settings'
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: strings.settings.logout }))

    expect(await screen.findByRole('heading', { name: strings.auth.loginTitle })).toBeInTheDocument()
    expect(screen.getByText(strings.auth.loggedOut)).toBeInTheDocument()
    expect(api.requests.find((r) => r.key === LOGOUT)?.headers.get('Authorization')).toBe('Bearer test-token')
    expect(getSession()).toBeNull()
  })

  it('logs out on the phone even when the server cannot be reached', async () => {
    mockApi({ [LOGOUT]: 'network-error', [RECENT]: { body: [] } })
    window.location.hash = '#/settings'
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: strings.settings.logout }))
    await waitFor(() => expect(getSession()).toBeNull())
  })
})
