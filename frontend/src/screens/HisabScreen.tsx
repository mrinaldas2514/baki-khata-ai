import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Customer, ParseConfirm, ParseConfirmResult, ParsePreview, RecentTransaction } from '../api/types'
import { ConfirmationCard } from '../components/ConfirmationCard'
import { EntryForm } from '../components/EntryForm'
import { MicButton } from '../components/MicButton'
import { MultiConfirm } from '../components/MultiConfirm'
import { PendingList } from '../components/PendingList'
import { RecentTransactions } from '../components/RecentTransactions'
import { QueuedMessage, SavedMessage } from '../components/SavedMessage'
import { SmartEntry } from '../components/SmartEntry'
import { VoiceSettings } from '../components/VoiceSettings'
import { VoiceStatus } from '../components/VoiceStatus'
import { Alert } from '../components/ui'
import { LOW_CONFIDENCE } from '../config'
import {
  type CustomerChoice,
  type Draft,
  EMPTY_FORM,
  type FormValues,
  type MultiItem,
  type ReadBy,
  toConfirmRequest,
  toDraft,
  toMultiItems,
} from '../entry'
import { useEntryTimer } from '../entrySpeed'
import { parseErrorMessage, saveErrorMessage } from '../errors'
import { cachedCustomers } from '../offline/customerCache'
import { localPreview } from '../offline/localPreview'
import { isOnline } from '../offline/online'
import { type QueuedSave, discard, enqueue, newSaveKey, onSynced, useQueue } from '../offline/queue'
import { currentShopId } from '../session'
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
 *   idle --submit--> parsing --> confirm --save--> saved (Undo for 10 s)
 *                       |  |        | edit
 *                       |  |        v
 *                       +--|----> form (edit, low confidence, or manual entry after an error)
 *                          +----> multi (several customers: a card each) --save all--> saved
 *
 * Offline (or when the server can't be reached) the sentence is read on the phone by the same
 * rules as "AI chhara" (offline/rules.ts), and Save keeps the entry on the phone ("queued")
 * until it can be sent (offline/queue.ts).
 */
type Step =
  | { kind: 'idle' }
  | { kind: 'parsing' }
  | { kind: 'confirm'; preview: ParsePreview; notice: string | null }
  | { kind: 'multi'; rawText: string; items: MultiItem[]; readBy: ReadBy; notice: string | null }
  | {
      kind: 'form'
      rawText: string
      title: string
      initial: FormValues
      suggestions: Customer[]
      notice: string | null
    }
  | { kind: 'saved'; rawText: string; results: ParseConfirmResult[] }
  | { kind: 'queued'; rawText: string; item: QueuedSave }

/** Who an entry is for, as the pending list shows it. */
function summaryOf(draft: Draft): QueuedSave['summary'][number] {
  const name = draft.choice.kind === 'existing' ? draft.choice.customer.name : draft.choice.name
  return { name, amount: draft.amount, type: draft.type }
}

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
  const [undoNotice, setUndoNotice] = useState(false)
  const topRef = useRef<HTMLDivElement>(null)
  // "Gore ekta hisab: X second" on the dashboard: first keystroke or mic press until saved.
  const timer = useEntryTimer()

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

  // An entry kept on the phone reached the server: it belongs in the list now.
  const queue = useQueue()
  useEffect(() => onSynced(() => void fetchRecent()), [fetchRecent])

  function retryRecent() {
    setRecentFailed(false)
    fetchRecent()
  }

  function goTo(next: Step) {
    setStep(next)
    setSaveError(null)
    setUndoNotice(false)
    topRef.current?.scrollIntoView?.({ block: 'start' })
  }

  function showPreview(preview: ParsePreview, notice: string | null) {
    if (preview.entries && preview.entries.length > 1) {
      goTo({
        kind: 'multi',
        rawText: preview.raw_text,
        items: toMultiItems(preview.entries),
        readBy: { parser: preview.parser, model: preview.model },
        notice,
      })
    } else if (preview.parsed.confidence < LOW_CONFIDENCE) {
      // Not sure enough to show as a confirmation: let the shopkeeper check every field.
      goTo(
        formFromPreview(
          preview,
          null,
          notice ? `${notice} ${strings.errors.lowConfidence}` : strings.errors.lowConfidence,
        ),
      )
    } else {
      goTo({ kind: 'confirm', preview, notice })
    }
  }

  function manualForm(rawText: string, notice: string) {
    goTo({ kind: 'form', rawText, title: strings.manualTitle, initial: EMPTY_FORM, suggestions: [], notice })
  }

  /** No server: read it on the phone with the rules and the last customer list. */
  function readOnPhone(sentence: string, notice: string) {
    const preview = localPreview(sentence, cachedCustomers(currentShopId()))
    if (preview) showPreview(preview, notice)
    else manualForm(sentence, strings.offline.cantRead)
  }

  async function handleSubmit(sentence: string) {
    setHeardText(null)
    if (!isOnline()) {
      readOnPhone(sentence, strings.offline.readOnPhone)
      return
    }
    goTo({ kind: 'parsing' })
    try {
      const preview = await api.parse(sentence)
      showPreview(preview, preview.notice ?? null)
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'network') {
        readOnPhone(sentence, strings.offline.readAfterNetworkError)
      } else {
        manualForm(sentence, parseErrorMessage(error))
      }
    }
  }

  function showSaved(rawText: string, results: ParseConfirmResult[]) {
    // Newest on top: the last entry of the sentence first. (Reversed here, not inside the
    // state updater: React may run an updater twice.)
    const rows: RecentTransaction[] = results
      .map(({ transaction, customer }) => ({
        ...transaction,
        customer_name: customer.name,
        customer_note: customer.note,
      }))
      .reverse()
    const ids = new Set(rows.map((row) => row.id))
    setRecent((current) => [...rows, ...(current ?? []).filter((r) => !ids.has(r.id))].slice(0, RECENT_LIMIT))
    setHighlightId(results[results.length - 1].transaction.id)
    timer.reset()
    setText('')
    goTo({ kind: 'saved', rawText, results })
  }

  /** Keep it on the phone, to be sent with the same Idempotency-Key when there is internet. */
  async function saveOnPhone(save: Parameters<typeof enqueue>[1]) {
    const item = await enqueue(currentShopId(), save)
    timer.reset()
    setText('')
    goTo({ kind: 'queued', rawText: save.rawText, item })
  }

  /**
   * Save one entry (/parse/confirm) or several (/parse/confirm-many). Offline, or when the
   * request gets no answer at all, the entry is kept on the phone instead, with the same key:
   * if the request did reach the server, the retry is answered without saving it twice.
   */
  async function persist(rawText: string, drafts: Draft[]) {
    const entries: ParseConfirm[] = drafts.map((draft) => toConfirmRequest(rawText, draft))
    const save = {
      key: newSaveKey(),
      rawText,
      endpoint: entries.length === 1 ? ('confirm' as const) : ('confirm-many' as const),
      entries,
      summary: drafts.map(summaryOf),
      timing: timer.current(),
    }
    setSaving(true)
    setSaveError(null)
    try {
      if (!isOnline()) {
        await saveOnPhone(save)
      } else if (save.endpoint === 'confirm') {
        showSaved(rawText, [await api.confirm(entries[0], save.timing, save.key)])
      } else {
        showSaved(rawText, (await api.confirmMany(entries, save.timing, save.key)).results)
      }
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'network') await saveOnPhone(save)
      else setSaveError(saveErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const handleSave = (rawText: string, draft: Draft) => persist(rawText, [draft])

  function handleSaveAll(rawText: string, items: MultiItem[]) {
    const drafts = items.map(toDraft)
    if (drafts.some((draft) => draft === null)) return
    return persist(rawText, drafts as Draft[])
  }

  /** Undo of an entry still on the phone: throw it away (too late once it was sent). */
  async function undoQueued(rawText: string, item: QueuedSave) {
    if (!queue.items.some((waiting) => waiting.key === item.key)) throw new Error('already sent')
    await discard(currentShopId(), item.key)
    setText(rawText)
    goTo({ kind: 'idle' })
    setUndoNotice(true)
  }

  /** "Bhul hoyeche? Undo": delete what was just saved, and any customer it created. */
  async function undo(rawText: string, results: ParseConfirmResult[]) {
    for (const { transaction } of results) await api.deleteTransaction(transaction.id)
    const created = new Set(results.filter((r) => r.customer_created).map((r) => r.customer.id))
    for (const id of created) {
      // 409: the customer got another entry meanwhile, so they stay.
      await api.deleteCustomer(id).catch(() => {})
    }
    const ids = new Set(results.map((r) => r.transaction.id))
    setRecent((rows) => rows && rows.filter((row) => !ids.has(row.id)))
    setHighlightId(null)
    setText(rawText)
    goTo({ kind: 'idle' })
    setUndoNotice(true)
    fetchRecent()
  }

  const showEntry = step.kind === 'idle' || step.kind === 'parsing' || step.kind === 'saved' || step.kind === 'queued'

  return (
    <div ref={topRef} className="flex scroll-mt-4 flex-col gap-6">
      {step.kind === 'saved' && (
        <SavedMessage
          results={step.results}
          onClose={() => goTo({ kind: 'idle' })}
          onUndo={() => undo(step.rawText, step.results)}
        />
      )}
      {step.kind === 'queued' && (
        <QueuedMessage
          item={step.item}
          onClose={() => goTo({ kind: 'idle' })}
          onUndo={() => undoQueued(step.rawText, step.item)}
        />
      )}
      {undoNotice && (
        <p role="status" className="rounded-2xl border-2 border-amber-400 bg-amber-50 px-4 py-3 text-lg text-amber-950">
          ↶ {strings.undo.done}
        </p>
      )}

      {showEntry && !aiEnabled && <Alert tone="info">{strings.settings.aiOffBanner}</Alert>}

      {showEntry && (
        <SmartEntry
          value={text}
          onChange={(typed) => {
            timer.typed(typed)
            setText(typed)
          }}
          onSubmit={handleSubmit}
          busy={step.kind === 'parsing' || voiceActive}
          actions={
            voiceEngine.engine !== 'none' && (
              <MicButton
                state={voice.state}
                onStart={() => {
                  timer.micPressed()
                  voice.start()
                }}
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

      {(step.kind === 'confirm' || step.kind === 'multi') && step.notice && (
        <Alert tone="warning">
          <p>{step.notice}</p>
          <p className="mt-1 text-base">{strings.offline.staleBalance}</p>
        </Alert>
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

      {step.kind === 'multi' && (
        <MultiConfirm
          rawText={step.rawText}
          items={step.items}
          readBy={step.readBy}
          onChange={(items) => (items.length ? setStep({ ...step, items }) : goTo({ kind: 'idle' }))}
          onSaveAll={() => handleSaveAll(step.rawText, step.items)}
          onCancel={() => goTo({ kind: 'idle' })}
          saving={saving}
          error={saveError}
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

      <PendingList shopId={currentShopId()} />
      <RecentTransactions transactions={recent} failed={recentFailed} onRetry={retryRecent} highlightId={highlightId} />
    </div>
  )
}
