import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  // Screens live in the URL hash (src/route.ts); every test starts on the Hisab tab.
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
