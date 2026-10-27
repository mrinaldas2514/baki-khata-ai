import { useEffect, useState } from 'react'

/**
 * Where the app is, kept in the URL hash so the phone's back button works:
 *
 *   #/              Hisab (the entry screen)
 *   #/customers     the customer list
 *   #/customers/7   one customer's khata
 *   #/dashboard     the dashboard
 */
export type Route =
  { name: 'hisab' } | { name: 'customers' } | { name: 'khata'; customerId: number } | { name: 'dashboard' }

export type Tab = 'hisab' | 'customers' | 'dashboard'

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  if (parts[0] === 'customers') {
    const id = Number(parts[1])
    return parts[1] && Number.isInteger(id) && id > 0 ? { name: 'khata', customerId: id } : { name: 'customers' }
  }
  if (parts[0] === 'dashboard') return { name: 'dashboard' }
  return { name: 'hisab' }
}

export const href = {
  hisab: '#/',
  customers: '#/customers',
  khata: (customerId: number) => `#/customers/${customerId}`,
  dashboard: '#/dashboard',
}

export function tabOf(route: Route): Tab {
  return route.name === 'khata' ? 'customers' : route.name
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
