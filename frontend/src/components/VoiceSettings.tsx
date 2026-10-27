import { strings } from '../strings'
import { VOICE_LANGUAGES, type VoiceLanguage, type VoiceSettings as Settings } from '../voice/settings'

interface Props {
  settings: Settings
  onChange: (changes: Partial<Settings>) => void
  /** Show the "use the server" choice (the browser can recognize speech and the server can too). */
  canChooseServer: boolean
  /** The browser can't recognize speech itself, so the server is used. */
  serverOnly: boolean
}

/** Language, auto-submit and engine choice, folded away under "Voice: Bangla (Bangladesh)". */
export function VoiceSettings({ settings, onChange, canChooseServer, serverOnly }: Props) {
  return (
    <details className="rounded-2xl bg-white px-4 py-2 text-lg text-stone-800">
      <summary className="min-h-10 cursor-pointer py-1 font-semibold">
        {strings.voice.settingsTitle(strings.voice.languages[settings.language])}
      </summary>
      <div className="flex flex-col gap-3 pt-2 pb-2">
        <label className="flex flex-col gap-1">
          <span>{strings.voice.languageLabel}</span>
          <select
            value={settings.language}
            onChange={(event) => onChange({ language: event.target.value as VoiceLanguage })}
            className="min-h-12 rounded-xl border-2 border-stone-300 bg-white px-3 text-lg"
          >
            {VOICE_LANGUAGES.map((code) => (
              <option key={code} value={code}>
                {strings.voice.languages[code]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-h-10 items-center gap-3">
          <input
            type="checkbox"
            checked={settings.autoSubmit}
            onChange={(event) => onChange({ autoSubmit: event.target.checked })}
            className="size-6 accent-emerald-700"
          />
          {strings.voice.autoSubmit}
        </label>
        {canChooseServer && (
          <label className="flex min-h-10 items-center gap-3">
            <input
              type="checkbox"
              checked={settings.preferServer}
              onChange={(event) => onChange({ preferServer: event.target.checked })}
              className="size-6 accent-emerald-700"
            />
            {strings.voice.preferServer}
          </label>
        )}
        {serverOnly && <p className="text-base text-stone-600">{strings.voice.serverOnly}</p>}
      </div>
    </details>
  )
}
