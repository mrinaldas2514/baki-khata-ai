import { useEffect, useRef, useState } from 'react'
import { api } from './api/client'
import { BottomNav } from './components/BottomNav'
import { OnlineStatus } from './components/OnlineStatus'
import { type CustomerSort } from './customers'
import { loadCustomerCache } from './offline/customerCache'
import { isOnline } from './offline/online'
import { startAutoSync } from './offline/queue'
import { href, tabOf, useRoute } from './route'
import { LoginScreen, RegisterScreen } from './screens/AuthScreens'
import { CustomersScreen } from './screens/CustomersScreen'
import { DashboardScreen } from './screens/DashboardScreen'
import { HisabScreen } from './screens/HisabScreen'
import { KhataScreen } from './screens/KhataScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { type Session, endSession, isExpired, lastEndReason, useSession } from './session'
import { strings } from './strings'

// setTimeout can't wait longer than about 24.8 days.
const MAX_TIMER_MS = 2_147_483_647

/** Log out by itself when the token expires, even if the app is just left open. */
function useLogoutAtExpiry(session: Session | null) {
  useEffect(() => {
    if (!session) return
    if (isExpired(session)) {
      endSession('expired')
      return
    }
    const wait = Math.min(new Date(session.expiresAt).getTime() - Date.now(), MAX_TIMER_MS)
    const timer = setTimeout(() => endSession('expired'), wait)
    return () => clearTimeout(timer)
  }, [session])
}

/** The app shell: login while logged out; otherwise a title bar, the current screen and the tabs. */
export default function App() {
  const session = useSession()
  const route = useRoute()
  useLogoutAtExpiry(session)

  if (!session) {
    return (
      <div className="min-h-dvh bg-stone-100">
        <Header />
        <main className="mx-auto max-w-md px-4 py-5">
          {route.name === 'register' ? <RegisterScreen /> : <LoginScreen endReason={lastEndReason()} />}
        </main>
      </div>
    )
  }
  // `key`: a different login starts with fresh screens (nothing of the last shop stays).
  return <LoggedIn key={session.user.id} session={session} />
}

function LoggedIn({ session }: { session: Session }) {
  const route = useRoute()
  const tab = tabOf(route)
  const topRef = useRef<HTMLDivElement>(null)
  // Kept here so search and sort survive opening a khata and coming back.
  const [listSearch, setListSearch] = useState('')
  const [listSort, setListSort] = useState<CustomerSort>('most-owed')

  useEffect(() => {
    topRef.current?.scrollIntoView?.({ block: 'start' })
  }, [route])

  // Working offline: entries kept on the phone are sent when there is internet, and the last
  // customer list is on the phone (and refreshed now) for reading entries without the server.
  const shopId = session.user.shop.id
  useEffect(() => {
    void loadCustomerCache(shopId).then(() => {
      if (isOnline()) api.customers().catch(() => {})
    })
    return startAutoSync(shopId)
  }, [shopId])

  useEffect(() => {
    // Just logged in or registered: start on the Hisab tab.
    if (route.name === 'login' || route.name === 'register') window.location.hash = href.hisab
  }, [route.name])

  return (
    <div ref={topRef} className="min-h-dvh bg-stone-100 pb-[calc(5rem+env(safe-area-inset-bottom))]">
      <Header shopName={session.user.shop.name} settingsOpen={route.name === 'settings'} />
      <main className="mx-auto max-w-md px-4 py-5">
        <div hidden={tab !== 'hisab'}>
          <HisabScreen active={tab === 'hisab'} aiEnabled={session.user.ai_enabled} />
        </div>
        {route.name === 'customers' && (
          <CustomersScreen search={listSearch} onSearch={setListSearch} sort={listSort} onSort={setListSort} />
        )}
        {route.name === 'khata' && <KhataScreen key={route.customerId} customerId={route.customerId} />}
        {route.name === 'dashboard' && <DashboardScreen />}
        {route.name === 'settings' && <SettingsScreen user={session.user} />}
      </main>
      <BottomNav active={tab} />
    </div>
  )
}

function Header({ shopName, settingsOpen = false }: { shopName?: string; settingsOpen?: boolean }) {
  return (
    <header className="bg-emerald-800 px-4 py-2 text-white">
      <div className="mx-auto flex min-h-12 max-w-md flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold">{strings.appTitle}</h1>
          {shopName && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <p className="truncate text-base text-emerald-100">{shopName}</p>
              <OnlineStatus />
            </div>
          )}
        </div>
        {shopName && (
          <a
            href={href.settings}
            aria-current={settingsOpen ? 'page' : undefined}
            className={`flex min-h-12 shrink-0 items-center gap-2 rounded-xl px-3 text-lg font-semibold ${settingsOpen ? 'bg-emerald-950' : 'active:bg-emerald-900'}`}
          >
            <svg
              viewBox="0 0 24 24"
              className="size-6"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
            </svg>
            {strings.settings.open}
          </a>
        )}
      </div>
    </header>
  )
}
