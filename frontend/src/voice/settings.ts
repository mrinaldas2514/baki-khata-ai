import { useState } from 'react'

export const VOICE_LANGUAGES = ['bn-BD', 'bn-IN', 'en-IN'] as const
export type VoiceLanguage = (typeof VOICE_LANGUAGES)[number]

export interface VoiceSettings {
  language: VoiceLanguage
  /** Send the sentence to "Hisab korun" as soon as speaking ends, without a chance to fix it. */
  autoSubmit: boolean
  /** Use server-side Whisper even when the browser has its own speech recognition. */
  preferServer: boolean
}

export const DEFAULT_VOICE_SETTINGS: VoiceSettings = { language: 'bn-BD', autoSubmit: false, preferServer: false }

const STORAGE_KEY = 'baki-khata.voice'

/** Saved settings, or the defaults. Storage can be missing or blocked (private mode), so never throw. */
export function loadVoiceSettings(): VoiceSettings {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (!saved || typeof saved !== 'object') return DEFAULT_VOICE_SETTINGS
    return {
      language: VOICE_LANGUAGES.includes(saved.language) ? saved.language : DEFAULT_VOICE_SETTINGS.language,
      autoSubmit: saved.autoSubmit === true,
      preferServer: saved.preferServer === true,
    }
  } catch {
    return DEFAULT_VOICE_SETTINGS
  }
}

function saveVoiceSettings(settings: VoiceSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // Not saved; the choice still applies until the page is closed.
  }
}

export function useVoiceSettings() {
  const [settings, setSettings] = useState(loadVoiceSettings)

  function update(changes: Partial<VoiceSettings>) {
    const next = { ...settings, ...changes }
    setSettings(next)
    saveVoiceSettings(next)
  }

  return [settings, update] as const
}
