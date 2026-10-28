import { useEffect, useState } from 'react'

/**
 * Where the app is, kept in the URL hash so the phone's back button works:
 *
 *   #/              Hisab (the entry screen)
 *   #/customers     the customer list
 *   #/customers/7   one customer's khata
 *   #/dashboard     the dashboard
 *   #/settings      settings: AI off, CSV export, logout, delete account
 *   #/login         login (shown anyway while logged out)
 *   #/register      a new account
 */
export type Route =
  | { name: 'hisab' }
  | { name: 'customers' }
  | { name: 'khata'; customerId: number }
  | { name: 'dashboard' }
  | { name: 'settings' }
  | { name: 'login' }
  | { name: 'register' }

/** The bottom tab a screen belongs to; settings and login have none. */
export type Tab = 'hisab' | 'customers' | 'dashboard' | null

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  if (parts[0] === 'customers') {
    const id = Number(parts[1])
    return parts[1] && Number.isInteger(id) && id > 0 ? { name: 'khata', customerId: id } : { name: 'customers' }
  }
  if (parts[0] === 'dashboard') return { name: 'dashboard' }
  if (parts[0] === 'settings') return { name: 'settings' }
  if (parts[0] === 'login') return { name: 'login' }
  if (parts[0] === 'register') return { name: 'register' }
  return { name: 'hisab' }
}

export const href = {
  hisab: '#/',
  customers: '#/customers',
  khata: (customerId: number) => `#/customers/${customerId}`,
  dashboard: '#/dashboard',
  settings: '#/settings',
  login: '#/login',
  register: '#/register',
}

export function tabOf(route: Route): Tab {
  if (route.name === 'khata') return 'customers'
  if (route.name === 'hisab' || route.name === 'customers' || route.name === 'dashboard') return route.name
  return null
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return route
}
