import { useSyncExternalStore } from 'react'

/**
 * Whether the phone says it has a connection. "Online" isn't a promise the server answers
 * (a weak signal can still fail), so a request that fails without an answer is treated the
 * same way where it matters (saving queues the entry).
 */
export const isOnline = () => (typeof navigator === 'undefined' ? true : navigator.onLine)

function subscribe(onChange: () => void) {
  window.addEventListener('online', onChange)
  window.addEventListener('offline', onChange)
  return () => {
    window.removeEventListener('online', onChange)
    window.removeEventListener('offline', onChange)
  }
}

export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, isOnline, () => true)
}
