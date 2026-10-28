import { useId, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { User } from '../api/types'
import { Sheet } from '../components/Dialog'
import { Alert, Button, PasswordInput } from '../components/ui'
import { forgetCustomers } from '../offline/customerCache'
import { forgetShop, useQueue } from '../offline/queue'
import { formatPhone } from '../phone'
import { currentShopId, endSession, updateUser } from '../session'
import { strings } from '../strings'

/** Save a downloaded file on the phone (or computer). */
function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  // Give the browser a moment to start the download before the URL goes.
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/** The account, "AI bondho rakhun", CSV export, logout and deleting the account. */
export function SettingsScreen({ user }: { user: User }) {
  return (
    <div className="flex flex-col gap-5">
      <h2 className="text-2xl font-bold text-stone-900">{strings.settings.title}</h2>
      <section aria-labelledby="account-title" className="rounded-3xl bg-white p-4 shadow-md">
        <h3 id="account-title" className="text-lg text-stone-600">
          {strings.settings.account}
        </h3>
        <p className="text-2xl font-bold break-words text-stone-900">{user.name}</p>
        <p className="text-xl break-words text-stone-800">{user.shop.name}</p>
        {user.phone && <p className="text-lg text-stone-600">{formatPhone(user.phone)}</p>}
        {user.email && <p className="text-lg break-all text-stone-600">{user.email}</p>}
      </section>
      <AiSetting user={user} />
      <ExportSection />
      <LogoutButton />
      <DeleteAccount />
    </div>
  )
}

function AiSetting({ user }: { user: User }) {
  const [saving, setSaving] = useState(false)
  const [failed, setFailed] = useState(false)
  const hintId = useId()
  const aiOff = !user.ai_enabled

  async function toggle() {
    setSaving(true)
    setFailed(false)
    try {
      updateUser(await api.setAiEnabled(aiOff))
    } catch {
      setFailed(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-md">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xl font-bold text-stone-900" id={`${hintId}-label`}>
          {strings.settings.aiTitle}
        </h3>
        <button
          type="button"
          role="switch"
          aria-checked={aiOff}
          aria-labelledby={`${hintId}-label`}
          aria-describedby={hintId}
          onClick={toggle}
          disabled={saving}
          className={`relative h-10 w-18 shrink-0 rounded-full transition-colors disabled:opacity-60 ${aiOff ? 'bg-emerald-700' : 'bg-stone-300'}`}
        >
          <span
            aria-hidden
            className={`absolute top-1 left-1 size-8 rounded-full bg-white shadow transition-transform ${aiOff ? 'translate-x-8' : ''}`}
          />
        </button>
      </div>
      <p id={hintId} className="text-lg text-stone-700">
        {saving ? strings.settings.aiSaving : aiOff ? strings.settings.aiOffHint : strings.settings.aiOnHint}
      </p>
      {failed && <Alert>{strings.settings.aiFailed}</Alert>}
    </section>
  )
}

function ExportSection() {
  const [state, setState] = useState<'idle' | 'busy' | 'failed'>('idle')

  async function download() {
    setState('busy')
    try {
      const { blob, filename } = await api.exportCsv()
      saveFile(blob, filename)
      setState('idle')
    } catch {
      setState('failed')
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-md">
      <h3 className="text-xl font-bold text-stone-900">{strings.settings.exportTitle}</h3>
      <p className="text-lg text-stone-700">{strings.settings.exportHint}</p>
      <Button variant="secondary" onClick={download} disabled={state === 'busy'}>
        {state === 'busy' ? strings.settings.exporting : strings.settings.exportButton}
      </Button>
      {state === 'failed' && <Alert>{strings.settings.exportFailed}</Alert>}
    </section>
  )
}

function LogoutButton() {
  const [busy, setBusy] = useState(false)
  const pending = useQueue().items.length

  async function logout() {
    setBusy(true)
    // Logged out on the phone whatever happens; the server is told when it can be reached.
    await api.logout().catch(() => {})
    endSession('logout')
  }

  return (
    <>
      {pending > 0 && <Alert tone="warning">{strings.offline.logoutWarning(pending)}</Alert>}
      <Button variant="secondary" onClick={logout} disabled={busy}>
        {busy ? strings.settings.loggingOut : strings.settings.logout}
      </Button>
    </>
  )
}

function DeleteAccount() {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function close() {
    setOpen(false)
    setPassword('')
    setError(null)
  }

  async function confirm() {
    if (!password) {
      setError(strings.auth.passwordRequired)
      return
    }
    setBusy(true)
    setError(null)
    try {
      const shopId = currentShopId()
      await api.deleteAccount(password)
      await Promise.all([forgetShop(shopId), forgetCustomers(shopId)])
      endSession('deleted')
    } catch (failure) {
      setError(
        failure instanceof ApiError && failure.status === 403
          ? strings.settings.wrongPassword
          : strings.settings.deleteFailed,
      )
      setBusy(false)
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-3xl border-2 border-red-200 bg-white p-4">
      <h3 className="text-xl font-bold text-red-800">{strings.settings.deleteTitle}</h3>
      <p className="text-lg text-stone-700">{strings.settings.deleteHint}</p>
      <Button variant="danger" onClick={() => setOpen(true)}>
        {strings.settings.deleteButton}
      </Button>
      {open && (
        <Sheet title={strings.settings.deleteConfirmTitle} onClose={() => !busy && close()}>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              confirm()
            }}
          >
            <p className="text-lg text-stone-800">{strings.settings.deleteConfirmBody}</p>
            <PasswordInput
              id="delete-password"
              label={strings.auth.password}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
            {error && <Alert>{error}</Alert>}
            <Button type="submit" variant="destructive" disabled={busy}>
              {busy ? strings.settings.deleting : strings.settings.deleteConfirmYes}
            </Button>
            <Button variant="secondary" onClick={close} disabled={busy}>
              {strings.settings.deleteConfirmNo}
            </Button>
          </form>
        </Sheet>
      )}
    </section>
  )
}
