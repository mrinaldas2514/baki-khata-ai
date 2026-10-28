import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Customer, ParseConfirmResult, ParsePreview, RecentTransaction } from '../api/types'
import { ConfirmationCard } from '../components/ConfirmationCard'
import { EntryForm } from '../components/EntryForm'
import { MicButton } from '../components/MicButton'
import { RecentTransactions } from '../components/RecentTransactions'
import { SavedMessage } from '../components/SavedMessage'
import { SmartEntry } from '../components/SmartEntry'
import { VoiceSettings } from '../components/VoiceSettings'
import { VoiceStatus } from '../components/VoiceStatus'
import { Alert } from '../components/ui'
import { LOW_CONFIDENCE } from '../config'
import { type CustomerChoice, type Draft, EMPTY_FORM, type FormValues, toConfirmRequest } from '../entry'
import { parseErrorMessage, saveErrorMessage } from '../errors'
import { strings } from '../strings'
import { useVoiceSettings } from '../voice/settings'
import { useVoiceEngine } from '../voice/useVoiceEngine'
import { useVoiceInput } from '../voice/useVoiceInput'

const RECENT_LIMIT = 10
// Same limit as the box and POST /parse.
const MAX_TEXT = 500

/**
 * The "Hisab" tab: write or speak one sentence, check it, save.
 *
 *   idle --submit--> parsing --> confirm --save--> saved
 *                       |           | edit
 *                       |           v
 *                       +-------> form (edit, low confidence, or manual entry after an error)
 */
type Step =
  | { kind: 'idle' }
  | { kind: 'parsing' }
  | { kind: 'confirm'; preview: ParsePreview }
  | {
      kind: 'form'
      rawText: string
      title: string
      initial: FormValues
      suggestions: Customer[]
      notice: string | null
    }
  | { kind: 'saved'; result: ParseConfirmResult }

function formFromPreview(preview: ParsePreview, choice: CustomerChoice | null, notice: string | null): Step {
  const { parsed, match } = preview
  return {
    kind: 'form',
    rawText: preview.raw_text,
    title: strings.editTitle,
    initial: { name: match.suggested_name, choice, amount: parsed.amount, type: parsed.type, item: parsed.item },
    suggestions: match.candidates,
    notice,
  }
}

/**
 * Stays mounted while other tabs are open (only hidden), so a half-written sentence survives a
 * look at the customer list. `active` turns true again when the shopkeeper comes back.
 */
export function HisabScreen({ active, aiEnabled = true }: { active: boolean; aiEnabled?: boolean }) {
  const [text, setText] = useState('')
  const [step, setStep] = useState<Step>({ kind: 'idle' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [recent, setRecent] = useState<RecentTransaction[] | null>(null)
  const [recentFailed, setRecentFailed] = useState(false)
  const [highlightId, setHighlightId] = useState<number | null>(null)
  const topRef = useRef<HTMLDivElement>(null)

  // Voice: the transcript goes into the box, then through the same parse -> confirm -> save flow.
  const [voiceSettings, updateVoiceSettings] = useVoiceSettings()
  const voiceEngine = useVoiceEngine(voiceSettings.preferServer)
  const [heardText, setHeardText] = useState<string | null>(null)
  const voice = useVoiceInput({
    engine: voiceEngine.engine,
    language: voiceSettings.language,
    maxSeconds: voiceEngine.maxSeconds,
    transcribe: (audio, language) => api.transcribe(audio, language).then((result) => result.text),
    onInterim: (heard) => setText(heard.slice(0, MAX_TEXT)),
    onText: (heard) => {
      const sentence = heard.slice(0, MAX_TEXT)
      setText(sentence)
      if (voiceSettings.autoSubmit) {
        handleSubmit(sentence)
      } else {
        setHeardText(sentence)
      }
    },
    onError: (code) => {
      if (code === 'server-off') voiceEngine.disableServer()
    },
  })
  const voiceActive = voice.state === 'listening' || voice.state === 'processing'

  const fetchRecent = useCallback(
    () => api.recentTransactions(RECENT_LIMIT).then(setRecent, () => setRecentFailed(true)),
    [],
  )

  // Again on every return to this tab: entries may have been edited or deleted in a khata.
  useEffect(() => {
    if (active) fetchRecent()
  }, [active, fetchRecent])

  function retryRecent() {
    setRecentFailed(false)
    fetchRecent()
  }

  function goTo(next: Step) {
    setStep(next)
    setSaveError(null)
    topRef.current?.scrollIntoView?.({ block: 'start' })
  }

  async function handleSubmit(sentence: string) {
    setHeardText(null)
    goTo({ kind: 'parsing' })
    try {
      const preview = await api.parse(sentence)
      if (preview.parsed.confidence < LOW_CONFIDENCE) {
        // Not sure enough to show as a confirmation: let the shopkeeper check every field.
        goTo(formFromPreview(preview, null, strings.errors.lowConfidence))
      } else {
        goTo({ kind: 'confirm', preview })
      }
    } catch (error) {
      goTo({
        kind: 'form',
        rawText: sentence,
        title: strings.manualTitle,
        initial: EMPTY_FORM,
        suggestions: [],
        notice: parseErrorMessage(error),
      })
    }
  }

  async function handleSave(rawText: string, draft: Draft) {
    setSaving(true)
    setSaveError(null)
    try {
      const result = await api.confirm(toConfirmRequest(rawText, draft))
      const { transaction, customer } = result
      const row: RecentTransaction = { ...transaction, customer_name: customer.name, customer_note: customer.note }
      setRecent((rows) => [row, ...(rows ?? []).filter((r) => r.id !== row.id)].slice(0, RECENT_LIMIT))
      setHighlightId(transaction.id)
      setText('')
      goTo({ kind: 'saved', result })
    } catch (error) {
      setSaveError(saveErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const showEntry = step.kind === 'idle' || step.kind === 'parsing' || step.kind === 'saved'

  return (
    <div ref={topRef} className="flex scroll-mt-4 flex-col gap-6">
      {step.kind === 'saved' && <SavedMessage result={step.result} onClose={() => goTo({ kind: 'idle' })} />}

      {showEntry && !aiEnabled && <Alert tone="info">{strings.settings.aiOffBanner}</Alert>}

      {showEntry && (
        <SmartEntry
          value={text}
          onChange={setText}
          onSubmit={handleSubmit}
          busy={step.kind === 'parsing' || voiceActive}
          actions={
            voiceEngine.engine !== 'none' && (
              <MicButton
                state={voice.state}
                onStart={voice.start}
                onStop={voice.stop}
                disabled={step.kind === 'parsing'}
              />
            )
          }
          footer={
            voiceEngine.engine !== 'none' && (
              <>
                <VoiceStatus
                  state={voice.state}
                  error={voice.error}
                  showCheckHint={heardText !== null && heardText === text}
                  showHoldHint={!text && step.kind === 'idle'}
                />
                <VoiceSettings
                  settings={voiceSettings}
                  onChange={updateVoiceSettings}
                  canChooseServer={voiceEngine.canChooseServer}
                  serverOnly={voiceEngine.serverOnly}
                />
              </>
            )
          }
        />
      )}

      {step.kind === 'parsing' && (
        <div role="status" className="flex items-center gap-3 rounded-2xl bg-white p-4 text-xl text-stone-700">
          <span
            className="size-6 animate-spin rounded-full border-4 border-emerald-200 border-t-emerald-700"
            aria-hidden
          />
          {strings.parsing}
        </div>
      )}

      {step.kind === 'confirm' && (
        <ConfirmationCard
          key={step.preview.raw_text}
          preview={step.preview}
          saving={saving}
          error={saveError}
          onSave={(draft) => handleSave(step.preview.raw_text, draft)}
          onEdit={(choice) => goTo(formFromPreview(step.preview, choice, null))}
          onCancel={() => goTo({ kind: 'idle' })}
        />
      )}

      {step.kind === 'form' && (
        <EntryForm
          title={step.title}
          rawText={step.rawText}
          initial={step.initial}
          suggestions={step.suggestions}
          notice={step.notice}
          saving={saving}
          error={saveError}
          onSave={(draft) => handleSave(step.rawText, draft)}
          onCancel={() => goTo({ kind: 'idle' })}
        />
      )}

      <RecentTransactions transactions={recent} failed={recentFailed} onRetry={retryRecent} highlightId={highlightId} />
    </div>
  )
}
