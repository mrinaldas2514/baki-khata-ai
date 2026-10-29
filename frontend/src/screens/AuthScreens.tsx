import { type FormEvent, type ReactNode, useState } from 'react'
import { api } from '../api/client'
import { Alert, Button, Field, PasswordInput } from '../components/ui'
import { CONSENT_VERSION, DEMO_LOGIN, showDemoLogin } from '../config'
import { authErrorMessage, fieldProblem } from '../errors'
import { normalizeMobile } from '../phone'
import { href } from '../route'
import { type EndReason, startSession } from '../session'
import { strings } from '../strings'

const END_MESSAGES: Record<EndReason, string> = {
  expired: strings.auth.sessionExpired,
  logout: strings.auth.loggedOut,
  deleted: strings.auth.accountDeleted,
}

function AuthCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section aria-labelledby="auth-title" className="flex flex-col gap-5 rounded-3xl bg-white p-4 shadow-md">
      <div>
        <h2 id="auth-title" className="text-3xl font-bold text-stone-900">
          {title}
        </h2>
        <p className="text-lg text-stone-600">{subtitle}</p>
      </div>
      {children}
    </section>
  )
}

/** Phone (or email) and password. A 401 here only means a wrong password. */
export function LoginScreen({ endReason }: { endReason: EndReason | null }) {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [problems, setProblems] = useState<{ login?: string; password?: string }>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const found = {
      login: login.trim() ? undefined : strings.auth.loginRequired,
      password: password ? undefined : strings.auth.passwordRequired,
    }
    setProblems(found)
    if (found.login || found.password) return
    setBusy(true)
    setError(null)
    try {
      startSession(await api.login(login.trim(), password))
    } catch (failure) {
      setError(authErrorMessage(failure))
      setBusy(false)
    }
  }

  return (
    <AuthCard title={strings.auth.loginTitle} subtitle={strings.auth.loginSubtitle}>
      {endReason && !error && (
        <Alert tone={endReason === 'expired' ? 'warning' : 'info'}>{END_MESSAGES[endReason]}</Alert>
      )}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        <Field
          id="login"
          label={strings.auth.loginLabel}
          value={login}
          onChange={(event) => setLogin(event.target.value)}
          placeholder={strings.auth.loginPlaceholder}
          autoComplete="username"
          autoCapitalize="none"
          inputMode="email"
          problem={problems.login}
        />
        <PasswordInput
          id="login-password"
          label={strings.auth.password}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          problem={problems.password}
        />
        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={busy}>
          {busy ? strings.auth.loggingIn : strings.auth.loginButton}
        </Button>
      </form>
      <p className="text-center text-lg text-stone-700">
        {strings.auth.noAccount}{' '}
        <a href={href.register} className="font-semibold text-emerald-800 underline underline-offset-4">
          {strings.auth.toRegister}
        </a>
      </p>
      {showDemoLogin() && (
        <p className="text-center text-base text-stone-600" data-testid="demo-login">
          {strings.auth.demoLogin}: {DEMO_LOGIN.phone} / {DEMO_LOGIN.password}
        </p>
      )}
    </AuthCard>
  )
}

interface RegisterProblems {
  name?: string
  shop?: string
  phone?: string
  email?: string
  password?: string
  consent?: string
}

/** Name, shop, mobile (or email), password, and the privacy note that must be ticked. */
export function RegisterScreen() {
  const [name, setName] = useState('')
  const [shopName, setShopName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [consent, setConsent] = useState(false)
  const [problems, setProblems] = useState<RegisterProblems>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function check(): RegisterProblems {
    const normalized = phone.trim() ? normalizeMobile(phone) : null
    return {
      name: name.trim() ? undefined : strings.auth.nameRequired,
      shop: shopName.trim() ? undefined : strings.auth.shopRequired,
      phone: !phone.trim()
        ? email.trim()
          ? undefined
          : strings.auth.phoneRequired
        : normalized
          ? undefined
          : strings.customerForm.phoneInvalid,
      email: !email.trim() || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()) ? undefined : strings.auth.emailInvalid,
      password: password.length >= 8 ? undefined : strings.auth.passwordShort,
      consent: consent ? undefined : strings.auth.consentRequired,
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const found = check()
    setProblems(found)
    if (Object.values(found).some(Boolean)) return
    setBusy(true)
    setError(null)
    try {
      startSession(
        await api.register({
          name: name.trim(),
          shop_name: shopName.trim(),
          phone: phone.trim() || null,
          email: email.trim() || null,
          password,
          consent,
          consent_version: CONSENT_VERSION,
        }),
      )
    } catch (failure) {
      setError(authErrorMessage(failure))
      if (fieldProblem(failure, 'phone')) setProblems({ phone: strings.customerForm.phoneInvalid })
      setBusy(false)
    }
  }

  return (
    <AuthCard title={strings.auth.registerTitle} subtitle={strings.auth.registerSubtitle}>
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        <Field
          id="register-name"
          label={strings.auth.yourName}
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="name"
          maxLength={100}
          problem={problems.name}
        />
        <Field
          id="register-shop"
          label={strings.auth.shopName}
          value={shopName}
          onChange={(event) => setShopName(event.target.value)}
          autoComplete="organization"
          maxLength={100}
          problem={problems.shop}
        />
        <Field
          id="register-phone"
          label={strings.auth.phone}
          hint={strings.auth.phoneHint}
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          placeholder={strings.auth.phonePlaceholder}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          problem={problems.phone}
        />
        <Field
          id="register-email"
          label={strings.auth.email}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          type="email"
          autoComplete="email"
          autoCapitalize="none"
          problem={problems.email}
        />
        <PasswordInput
          id="register-password"
          label={strings.auth.newPassword}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          problem={problems.password}
        />

        <fieldset
          aria-describedby="consent-points"
          className={`flex flex-col gap-3 rounded-2xl border-2 p-4 ${problems.consent ? 'border-red-400 bg-red-50' : 'border-emerald-300 bg-emerald-50'}`}
        >
          <legend className="px-1 text-xl font-bold text-stone-900">{strings.consent.title}</legend>
          <ul id="consent-points" className="flex list-disc flex-col gap-2 pl-5 text-lg text-stone-800">
            {strings.consent.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-white px-3 text-lg font-semibold text-stone-900 has-focus-visible:ring-2 has-focus-visible:ring-stone-900">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
              aria-invalid={Boolean(problems.consent)}
              className="size-7 shrink-0 accent-emerald-700"
            />
            {strings.consent.agree}
          </label>
          {problems.consent && <p className="text-lg text-red-700">{problems.consent}</p>}
        </fieldset>

        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={busy}>
          {busy ? strings.auth.registering : strings.auth.registerButton}
        </Button>
      </form>
      <p className="text-center text-lg text-stone-700">
        {strings.auth.haveAccount}{' '}
        <a href={href.login} className="font-semibold text-emerald-800 underline underline-offset-4">
          {strings.auth.toLogin}
        </a>
      </p>
    </AuthCard>
  )
}
