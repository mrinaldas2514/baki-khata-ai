/**
 * Searching and sorting the customer list, all on the phone (the list is already loaded).
 *
 * Search works across scripts: "rahim", "Rohim" and "রহিম" all find the same customer. Like
 * the backend's name matching (backend/app/services/name_matching.py), Bangla script is
 * written in English letters and common Banglish spelling differences are ignored.
 */
import type { CustomerListItem } from './api/types'

export type CustomerSort = 'most-owed' | 'oldest-owed' | 'name'

// --- Bangla script -> English letters (rough, only used for matching) --------------------

// prettier-ignore
const INDEPENDENT_VOWELS: Record<string, string> = {
  অ: 'a', আ: 'a', ই: 'i', ঈ: 'i', উ: 'u', ঊ: 'u', ঋ: 'ri', এ: 'e', ঐ: 'oi', ও: 'o', ঔ: 'ou',
}
// prettier-ignore
const VOWEL_SIGNS: Record<string, string> = {
  'া': 'a', 'ি': 'i', 'ী': 'i', 'ু': 'u', 'ূ': 'u', 'ৃ': 'ri', 'ে': 'e', 'ৈ': 'oi', 'ো': 'o', 'ৌ': 'ou',
}
// prettier-ignore
const CONSONANTS: Record<string, string> = {
  ক: 'k', খ: 'kh', গ: 'g', ঘ: 'gh', ঙ: 'ng', চ: 'ch', ছ: 'chh', জ: 'j', ঝ: 'jh', ঞ: 'n',
  ট: 't', ঠ: 'th', ড: 'd', ঢ: 'dh', ণ: 'n', ত: 't', থ: 'th', দ: 'd', ধ: 'dh', ন: 'n',
  প: 'p', ফ: 'f', ব: 'b', ভ: 'bh', ম: 'm', য: 'j', র: 'r', ল: 'l', শ: 'sh', ষ: 'sh', স: 's', হ: 'h',
}
// Consonant + nukta (how NFC spells ড় ঢ় য়).
const NUKTA_CONSONANTS: Record<string, string> = { ড: 'r', ঢ: 'rh', য: 'y' }
const OTHER: Record<string, string> = { ৎ: 't', 'ং': 'ng', 'ঃ': 'h', 'ঁ': '' }
const NUKTA = String.fromCharCode(0x09bc)
const HASANT = String.fromCharCode(0x09cd)
const BANGLA_DIGITS = '০১২৩৪৫৬৭৮৯'

function transliterateWord(word: string): string {
  const out: string[] = []
  const chars = [...word]
  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i]
    if (ch in CONSONANTS) {
      let sound = CONSONANTS[ch]
      if (chars[i + 1] === NUKTA) {
        sound = NUKTA_CONSONANTS[ch] ?? sound
        i++
      }
      const next = chars[i + 1] ?? ''
      if (next in VOWEL_SIGNS) {
        out.push(sound + VOWEL_SIGNS[next])
        i++
      } else if (next === HASANT) {
        out.push(sound)
        i++
      } else {
        // Inherent vowel: dropped at the end of a word, and before a consonant that carries
        // its own vowel sign (except on the first letter): সালমা -> salma.
        const after = chars[i + 2] ?? ''
        const drops = !next || (out.length > 0 && next in CONSONANTS && after in VOWEL_SIGNS)
        out.push(drops ? sound : sound + 'a')
      }
    } else if (ch in INDEPENDENT_VOWELS) out.push(INDEPENDENT_VOWELS[ch])
    else if (ch in VOWEL_SIGNS) out.push(VOWEL_SIGNS[ch])
    else if (ch in OTHER) out.push(OTHER[ch])
    else if (BANGLA_DIGITS.includes(ch)) out.push(String(BANGLA_DIGITS.indexOf(ch)))
    else if (ch <= '\u007f') out.push(ch)
  }
  return out.join('')
}

// prettier-ignore
const PHONETIC_RULES: [string, string][] = [
  ['chh', 'c'], ['ch', 'c'], ['ph', 'f'], ['bh', 'b'], ['kh', 'k'], ['gh', 'g'],
  ['jh', 'j'], ['th', 't'], ['dh', 'd'], ['sh', 's'], ['rh', 'r'],
  ['ee', 'i'], ['oo', 'u'], ['q', 'k'], ['z', 'j'], ['v', 'b'], ['w', 'o'], ['y', 'i'],
  // Bangla's inherent vowel is written as either "a" or "o": Rahim / Rohim.
  ['o', 'a'],
]

function phonetic(word: string): string {
  let key = word
  for (const [from, to] of PHONETIC_RULES) key = key.replaceAll(from, to)
  return key.replace(/(.)\1+/g, '$1')
}

/** "Rohim Bhai" / "রহিম ভাই" -> "rahim bai": romanized, spelling differences ironed out. */
export function searchKey(text: string): string {
  const words =
    text
      .normalize('NFC')
      .toLowerCase()
      .match(/[a-z0-9ঀ-৿]+/g) ?? []
  return words
    .map((word) => phonetic(transliterateWord(word)))
    .filter(Boolean)
    .join(' ')
}

const digitsOf = (text: string) => text.replace(/[০-৯]/g, (d) => String(BANGLA_DIGITS.indexOf(d))).replace(/\D/g, '')

/** Does the customer's name, area/note or phone match what was typed in the search box? */
export function matchesSearch(customer: CustomerListItem, query: string): boolean {
  const key = searchKey(query)
  if (!key) return true
  const digits = digitsOf(query)
  if (digits.length >= 3 && digits.length === query.replace(/[\s\-+]/g, '').length) {
    return digitsOf(customer.phone ?? '').includes(digits)
  }
  return [customer.name, customer.note ?? ''].some((text) => searchKey(text).includes(key))
}

const collator = new Intl.Collator(['en', 'bn'], { sensitivity: 'base', numeric: true })
const byName = (a: CustomerListItem, b: CustomerListItem) => collator.compare(a.name, b.name) || a.id - b.id

/**
 * most-owed: biggest baki first. oldest-owed: the baki that has waited longest first (by its
 * oldest unpaid credit). Customers who owe nothing come last in both, by name.
 */
export function sortCustomers(customers: CustomerListItem[], sort: CustomerSort): CustomerListItem[] {
  const sorted = [...customers]
  if (sort === 'name') return sorted.sort(byName)
  return sorted.sort((a, b) => {
    const aOwes = a.balance > 0
    const bOwes = b.balance > 0
    if (aOwes !== bOwes) return aOwes ? -1 : 1
    if (!aOwes) return byName(a, b)
    if (sort === 'most-owed') return b.balance - a.balance || byName(a, b)
    const since = (c: CustomerListItem) => (c.owed_since ? Date.parse(c.owed_since) : Infinity)
    return since(a) - since(b) || b.balance - a.balance || byName(a, b)
  })
}

/** Whole days since the customer's oldest unpaid credit, or null if nothing is owed. */
export function daysOwed(customer: CustomerListItem, now: Date = new Date()): number | null {
  if (!customer.owed_since || customer.balance <= 0) return null
  return Math.max(0, Math.floor((now.getTime() - Date.parse(customer.owed_since)) / 86_400_000))
}
