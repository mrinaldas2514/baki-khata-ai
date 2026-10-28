import '@testing-library/jest-dom/vitest'
import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { resetCustomerCacheForTests } from '../offline/customerCache'
import { resetQueueForTests } from '../offline/queue'
import { resetStoreForTests } from '../offline/store'
import { endSession, setSession } from '../session'
import { TEST_SESSION } from './mockApi'

beforeEach(() => {
  // A fresh, empty phone storage (IndexedDB) for every test.
  globalThis.indexedDB = new IDBFactory()
  resetStoreForTests()
  resetQueueForTests()
  resetCustomerCacheForTests()
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
  // Tests that go offline override navigator.onLine; back to the real one.
  Reflect.deleteProperty(navigator, 'onLine')
  vi.restoreAllMocks()
})
