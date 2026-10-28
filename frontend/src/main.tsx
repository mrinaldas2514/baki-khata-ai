// Noto Sans Bengali covers both Bangla script and Latin (Banglish), bundled with the app
// so it works without Google Fonts. The browser only downloads the subsets a page uses.
import '@fontsource/noto-sans-bengali/400.css'
import '@fontsource/noto-sans-bengali/600.css'
import '@fontsource/noto-sans-bengali/700.css'
import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Installable, and opens without internet (pwa/sw.js). Not in development: Vite serves fresh files.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // No service worker (e.g. a private window): the app works, just not offline.
    })
  })
}
