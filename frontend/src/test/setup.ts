import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { endSession, setSession } from '../session'
import { TEST_SESSION } from './mockApi'

beforeEach(() => {
  // Every test starts logged in as the owner of shop 1 (the auth tests log out first).
  setSession(TEST_SESSION)
})

afterEach(() => {
  cleanup()
  endSession('logout')
  try {
    localStorage.clear()
  } catch {
    // jsdom always has storage; nothing to do.
  }
  // Screens live in the URL hash (src/route.ts); every test starts on the Hisab tab.
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
