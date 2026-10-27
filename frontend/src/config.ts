/** Settings from frontend/.env (see .env.example). Vite reads them at build/dev-server start. */

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

// No login yet: the app works with one demo shop.
export const SHOP_ID = Number(import.meta.env.VITE_SHOP_ID ?? 1)

// Below this the AI's guess is shown in the edit form for checking instead of the
// confirmation card. The backend caps confidence at 0.5 when the amount isn't in the sentence.
export const LOW_CONFIDENCE = 0.6
