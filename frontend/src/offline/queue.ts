import { useSyncExternalStore } from 'react'
import { ApiError, api } from '../api/client'
import type { ParseConfirm, ParseConfirmManyResult } from '../api/types'
import type { EntryTiming } from '../entrySpeed'
import { saveErrorMessage } from '../errors'
import { isOnline } from './online'
import { get, getAll, put, remove } from './store'

/**
 * Entries saved on the phone while there was no internet ("Pending sync"), sent to the server
 * by themselves, oldest first, when the connection is back.
 *
 * Each save has an Idempotency-Key from the moment the shopkeeper pressed Save. The same key
 * goes with every try, so a try that reached the server but whose answer was lost isn't saved
 * a second time: the server answers what it saved the first time.
 */
export interface QueuedSave {
  /** The Idempotency-Key; also the id in storage. */
  key: string
  shopId: number
  /** Order of saving on this phone. */
  seq: number
  /** When it was saved on the phone (also each entry's created_at, so the khata has the real time). */
  savedAt: string
  rawText: string
  /**
   * Where the first try went. A retry must go there too: the server ties the key to the
   * endpoint and data, so the same key on the other endpoint would be refused.
   */
  endpoint: 'confirm' | 'confirm-many'
  entries: ParseConfirm[]
  /** For the "Pending sync" list: who, how much, baki or joma (entries may only have an id). */
  summary: { name: string; amount: number; type: ParseConfirm['type'] }[]
  timing?: EntryTiming
  status: 'pending' | 'failed'
  /** Why the server refused it (status 'failed'), in the shopkeeper's words. */
  error?: string
}

export interface QueueState {
  items: QueuedSave[]
  syncing: boolean
}

// Answers that mean "try again later" rather than "this entry is wrong".
const RETRY_LATER = new Set([401, 403, 408, 425, 429])
const RETRY_EVERY_MS = 20_000

let state: QueueState = { items: [], syncing: false }
const listeners = new Set<() => void>()
const syncedListeners = new Set<(results: ParseConfirmManyResult) => void>()
let seqCounter = 0

function setState(next: Partial<QueueState>) {
  state = { ...state, ...next }
  for (const listener of listeners) listener()
}

const byOrder = (a: QueuedSave, b: QueuedSave) => a.seq - b.seq

async function reload(shopId: number) {
  const all = await getAll<QueuedSave>('queue').catch(() => [] as QueuedSave[])
  setState({ items: all.filter((item) => item.shopId === shopId).sort(byOrder) })
}

/** A new random key for one save. */
export function newSaveKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

/** Keep the save on the phone; it's sent as soon as there is internet. */
export async function enqueue(
  shopId: number,
  save: Pick<QueuedSave, 'key' | 'rawText' | 'endpoint' | 'entries' | 'summary' | 'timing'>,
): Promise<QueuedSave> {
  const savedAt = new Date().toISOString()
  const item: QueuedSave = {
    ...save,
    shopId,
    seq: Date.now() * 1000 + (seqCounter++ % 1000),
    savedAt,
    entries: save.entries.map((entry) => ({ ...entry, created_at: entry.created_at ?? savedAt })),
    status: 'pending',
  }
  await put('queue', item)
  await reload(shopId)
  if (isOnline()) void syncQueue(shopId)
  return item
}

/** Throw a waiting save away (Undo, or "Bad din" on one the server refused). */
export async function discard(shopId: number, key: string): Promise<void> {
  await remove('queue', key)
  await reload(shopId)
}

/** The account was deleted: nothing of the shop stays on the phone. */
export async function forgetShop(shopId: number): Promise<void> {
  const all = await getAll<QueuedSave>('queue').catch(() => [] as QueuedSave[])
  await Promise.all(all.filter((item) => item.shopId === shopId).map((item) => remove('queue', item.key)))
  await remove('kv', createdKey(shopId)).catch(() => {})
  await reload(shopId)
}

// --- Customers the queue itself created ----------------------------------------------------

type Created = Record<string, number>
const createdKey = (shopId: number) => `queue-created:${shopId}`
const customerKey = (name: string, note?: string | null) =>
  `${name.trim().toLowerCase()}|${(note ?? '').trim().toLowerCase()}`

/**
 * "tanvir 50 baki" and later "tanvir 20 dilo", both offline: both say "new customer Tanvir".
 * The first one to reach the server creates Tanvir; the later ones go to that customer.
 */
async function withCreatedCustomers(shopId: number, entries: ParseConfirm[]): Promise<ParseConfirm[]> {
  const created = (await get<Created>('kv', createdKey(shopId)).catch(() => undefined)) ?? {}
  return entries.map((entry) => {
    const id = entry.new_customer && created[customerKey(entry.new_customer.name, entry.new_customer.note)]
    if (!id) return entry
    const { new_customer: _new, ...rest } = entry
    return { ...rest, customer_id: id }
  })
}

async function rememberCreated(shopId: number, entries: ParseConfirm[], answer: ParseConfirmManyResult) {
  const created = (await get<Created>('kv', createdKey(shopId)).catch(() => undefined)) ?? {}
  answer.results.forEach((result, i) => {
    const asked = entries[i]?.new_customer
    if (result.customer_created && asked) created[customerKey(asked.name, asked.note)] = result.customer.id
  })
  await put('kv', created, createdKey(shopId))
}

// --- Sending -------------------------------------------------------------------------------

/**
 * Send every waiting save, oldest first. Stops at the first one that gets no answer (still
 * offline, server asleep): the rest wait for the next try. One the server refuses (a name that
 * clashes, say) is marked failed with the reason, and the others go on.
 */
export async function syncQueue(shopId: number): Promise<void> {
  if (state.syncing) return
  setState({ syncing: true })
  try {
    await reload(shopId)
    for (const item of state.items.filter((i) => i.status === 'pending')) {
      let answer: ParseConfirmManyResult
      try {
        const entries = await withCreatedCustomers(shopId, item.entries)
        answer =
          item.endpoint === 'confirm'
            ? { results: [await api.confirm(entries[0], item.timing, item.key)] }
            : await api.confirmMany(entries, item.timing, item.key)
        await rememberCreated(shopId, entries, answer)
      } catch (error) {
        const refused =
          error instanceof ApiError &&
          error.kind === 'http' &&
          error.status !== null &&
          error.status >= 400 &&
          error.status < 500 &&
          !RETRY_LATER.has(error.status)
        if (!refused) break
        await put('queue', { ...item, status: 'failed', error: saveErrorMessage(error) })
        await reload(shopId)
        continue
      }
      await remove('queue', item.key)
      await reload(shopId)
      for (const listener of syncedListeners) listener(answer)
    }
  } finally {
    setState({ syncing: false })
  }
}

/**
 * While logged in: send waiting saves now, whenever the phone comes back online, and every
 * 20 seconds while some are waiting. Returns the function that stops it (logout).
 */
export function startAutoSync(shopId: number): () => void {
  const sync = () => {
    if (isOnline()) void syncQueue(shopId)
  }
  void reload(shopId).then(sync)
  const timer = setInterval(() => {
    if (state.items.some((item) => item.status === 'pending')) sync()
  }, RETRY_EVERY_MS)
  window.addEventListener('online', sync)
  return () => {
    clearInterval(timer)
    window.removeEventListener('online', sync)
  }
}

/** Called after each waiting save reaches the server (the Hisab screen reloads its list). */
export function onSynced(listener: (results: ParseConfirmManyResult) => void): () => void {
  syncedListeners.add(listener)
  return () => syncedListeners.delete(listener)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useQueue(): QueueState {
  return useSyncExternalStore(subscribe, () => state)
}

export function resetQueueForTests() {
  state = { items: [], syncing: false }
  syncedListeners.clear()
}
