import type { Customer } from '../api/types'
import { get, put, remove } from './store'

/**
 * The shop's last customer list, kept on the phone so an entry written offline can still find
 * "Rahim (Bazar road)". Refreshed whenever the list is loaded from the server.
 */
const loaded = new Map<number, Customer[]>()

const keyOf = (shopId: number) => `customers:${shopId}`

/** Read the stored list into memory (once per login), so offline matching needs no waiting. */
export async function loadCustomerCache(shopId: number): Promise<void> {
  if (loaded.has(shopId)) return
  const stored = await get<Customer[]>('kv', keyOf(shopId)).catch(() => undefined)
  if (stored && !loaded.has(shopId)) loaded.set(shopId, stored)
}

export function cachedCustomers(shopId: number): Customer[] {
  return loaded.get(shopId) ?? []
}

export function cacheCustomers(shopId: number, customers: Customer[]): void {
  loaded.set(shopId, customers)
  put('kv', customers, keyOf(shopId)).catch(() => {})
}

export async function forgetCustomers(shopId: number): Promise<void> {
  loaded.delete(shopId)
  await remove('kv', keyOf(shopId)).catch(() => {})
}

export function resetCustomerCacheForTests() {
  loaded.clear()
}
