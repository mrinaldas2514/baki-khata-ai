/**
 * The phone's own storage for working offline (IndexedDB): entries waiting to be sent, and the
 * last customer list. Where IndexedDB is missing or blocked (some private modes) it falls back
 * to memory, so the app still works, but waiting entries don't survive closing the page.
 */

const DB_NAME = 'baki-khata'
const VERSION = 1
export type StoreName = 'queue' | 'kv'

let opening: Promise<IDBDatabase | null> | null = null
const memory: Record<StoreName, Map<string, unknown>> = { queue: new Map(), kv: new Map() }

function open(): Promise<IDBDatabase | null> {
  opening ??= new Promise((resolve) => {
    try {
      const request = indexedDB.open(DB_NAME, VERSION)
      request.onupgradeneeded = () => {
        // Values carry their own key: queue items by `key` (the save's Idempotency-Key).
        request.result.createObjectStore('queue', { keyPath: 'key' })
        request.result.createObjectStore('kv')
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => resolve(null)
      request.onblocked = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
  return opening
}

function run<T>(store: StoreName, mode: IDBTransactionMode, action: (s: IDBObjectStore) => IDBRequest<T>) {
  return open().then(
    (db) =>
      db &&
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(store, mode)
        const request = action(tx.objectStore(store))
        tx.oncomplete = () => resolve(request.result)
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
      }),
  )
}

/** Every value in the store. */
export async function getAll<T>(store: StoreName): Promise<T[]> {
  const db = await open()
  if (!db) return [...memory[store].values()] as T[]
  return (await run(store, 'readonly', (s) => s.getAll())) as T[]
}

export async function get<T>(store: StoreName, key: string): Promise<T | undefined> {
  const db = await open()
  if (!db) return memory[store].get(key) as T | undefined
  return (await run(store, 'readonly', (s) => s.get(key))) as T | undefined
}

/** For 'queue' the key is the value's own `key`; for 'kv' give it. */
export async function put(store: StoreName, value: unknown, key?: string): Promise<void> {
  const db = await open()
  if (!db) {
    memory[store].set(key ?? (value as { key: string }).key, value)
    return
  }
  await run(store, 'readwrite', (s) => (key === undefined ? s.put(value) : s.put(value, key)))
}

export async function remove(store: StoreName, key: string): Promise<void> {
  const db = await open()
  if (!db) {
    memory[store].delete(key)
    return
  }
  await run(store, 'readwrite', (s) => s.delete(key))
}

/** Tests: forget the open database (each test gets a fresh fake IndexedDB). */
export function resetStoreForTests() {
  opening = null
  memory.queue.clear()
  memory.kv.clear()
}
