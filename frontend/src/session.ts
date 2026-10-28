import { useSyncExternalStore } from 'react'
import type { AuthResult, User } from './api/types'

/**
 * Who is logged in: the token from /auth/login or /auth/register, when it expires, and the user
 * (with their shop). Kept in localStorage so a reload stays logged in. If storage is blocked
 * (private mode) the login still works until the page is closed.
 *
 * The token is sent as `Authorization: Bearer ...` on every request (api/client.ts). When it
 * expires, or the backend answers 401, the session is cleared and the login screen shows.
 */
export interface Session {
  token: string
  expiresAt: string
  user: User
}

/** Why the last session ended, shown once on the login screen. */
export type EndReason = 'expired' | 'logout' | 'deleted'

const KEY = 'baki-khata.session'

let current: Session | null = load()
let endReason: EndReason | null = null
const listeners = new Set<() => void>()

function load(): Session | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const session = JSON.parse(raw) as Session
    return session?.token && session.user?.shop ? session : null
  } catch {
    return null
  }
}

function save(session: Session | null) {
  try {
    if (session) localStorage.setItem(KEY, JSON.stringify(session))
    else localStorage.removeItem(KEY)
  } catch {
    // Storage blocked: the session lives in memory only.
  }
}

function notify() {
  for (const listener of listeners) listener()
}

export function getSession(): Session | null {
  return current
}

export function startSession(result: AuthResult) {
  setSession({ token: result.access_token, expiresAt: result.expires_at, user: result.user })
}

export function setSession(session: Session) {
  current = session
  endReason = null
  save(session)
  notify()
}

/** The logged-in user changed (e.g. a setting): keep the same token. */
export function updateUser(user: User) {
  if (current) setSession({ ...current, user })
}

export function endSession(reason: EndReason) {
  if (!current) return
  current = null
  endReason = reason
  save(null)
  notify()
}

/** Why the last session ended (shown on the login screen until the next login). */
export function lastEndReason(): EndReason | null {
  return endReason
}

export function isExpired(session: Session, now = Date.now()): boolean {
  return new Date(session.expiresAt).getTime() <= now
}

/** The logged-in user's shop. Only called from screens shown after login. */
export function currentShopId(): number {
  if (!current) throw new Error('Not logged in')
  return current.user.shop.id
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useSession(): Session | null {
  return useSyncExternalStore(subscribe, getSession)
}
