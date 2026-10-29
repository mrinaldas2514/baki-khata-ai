/** Settings from frontend/.env (see .env.example). Vite reads them at build/dev-server start. */

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

// The demo login made by the backend (app/seed.py, or SEED_DEMO_ON_START). Must match it.
export const DEMO_LOGIN = { phone: '01700000000', password: 'demo1234' }

/** VITE_SHOW_DEMO_LOGIN=true: the login screen shows the demo login (public demo site only). */
export function showDemoLogin(): boolean {
  return import.meta.env.VITE_SHOW_DEMO_LOGIN === 'true'
}

// Below this the AI's guess is shown in the edit form for checking instead of the
// confirmation card. The backend caps confidence at 0.5 when the amount isn't in the sentence.
export const LOW_CONFIDENCE = 0.6

/**
 * The privacy note's version (the text is `strings.consent`). Must match CONSENT_VERSION in
 * backend/app/privacy.py; change both when the note's meaning changes.
 */
export const CONSENT_VERSION = '2026-10'
