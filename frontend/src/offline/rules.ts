/**
 * The rule-based parser, in the browser, for entries written while offline ("AI chhara").
 *
 * A line-by-line port of the backend's backend/app/services/number_words.py (spoken amounts to
 * digits) and backend/app/llm/rule_based.py (name, amount, type and item from one sentence).
 * rulesParity.json holds the Python parser's answers for ~250 sentences and the tests check
 * this one gives exactly the same; after changing the Python rules, regenerate it with
 * `python -m eval.rules_parity` (in backend/) and port the change here.
 */

const nfc = (text: string) => text.normalize('NFC')

// --- Spoken amounts to digits (number_words.py) -------------------------------------------

const BANGLA_DIGITS = '০১২৩৪৫৬৭৮৯'

function words(mapping: [number, string[]][]): Map<string, number> {
  return new Map(mapping.flatMap(([value, list]) => list.map((w) => [nfc(w), value] as [string, number])))
}

// prettier-ignore
const BASE = words([
  [1, ['ek', 'aek', 'এক']], [2, ['dui', 'du', 'দুই', 'দু']], [3, ['tin', 'teen', 'তিন']],
  [4, ['char', 'chaar', 'চার']], [5, ['pach', 'panch', 'paach', 'paanch', 'পাঁচ', 'পাচ']],
  [6, ['choy', 'chhoy', 'choi', 'chhoi', 'ছয়']], [7, ['sat', 'saat', 'সাত']],
  [8, ['at', 'aat', 'ath', 'aath', 'আট']], [9, ['noy', 'nou', 'noi', 'নয়']], [10, ['dosh', 'dos', 'দশ']],
  [11, ['egaro', 'এগারো']], [12, ['baro', 'বারো']], [13, ['tero', 'তেরো']], [14, ['choddo', 'চৌদ্দ']],
  [15, ['ponero', 'pondro', 'পনেরো', 'পনের']], [16, ['sholo', 'ষোলো', 'ষোল']], [17, ['sotero', 'সতেরো']],
  [18, ['atharo', 'আঠারো']], [19, ['unish', 'উনিশ']], [20, ['bish', 'kuri', 'বিশ', 'কুড়ি']],
  [25, ['pochish', 'pochis', 'পঁচিশ']], [30, ['tirish', 'tiris', 'ত্রিশ']], [40, ['chollish', 'chollis', 'চল্লিশ']],
  [50, ['ponchash', 'ponchas', 'pachas', 'পঞ্চাশ']], [60, ['shat', 'shaat', 'ষাট']],
  [70, ['sottor', 'sattor', 'সত্তর']], [80, ['ashi', 'আশি']], [90, ['nobboi', 'নব্বই']],
  [1, ['one']], [2, ['two']], [3, ['three']], [4, ['four']], [5, ['five']], [6, ['six']],
  [7, ['seven']], [8, ['eight']], [9, ['nine']], [10, ['ten']], [20, ['twenty']], [50, ['fifty']],
])
const SOWA = ['sowa', 'shoa', 'showa', 'soa', 'soya', 'shuwa', 'সোয়া', 'সওয়া']
// Used on their own before a multiplier: "dedh hajar" = 1500, "arai sho" = 250, "sowa sho" = 125.
const FRACTION = words([
  [1.25, SOWA],
  [1.5, ['dedh', 'der', 'derh', 'দেড়']],
  [2.5, ['arai', 'adai', 'আড়াই']],
])
// Modify the next number: "sare tin sho" = 350, "poune dui hajar" = 1750, "sowa tin sho" = 325.
const MODIFIERS = words([
  [0.5, ['sare', 'share', 'sade', 'saade', 'সাড়ে']],
  [0.25, SOWA],
  [-0.25, ['poune', 'paune', 'pone', 'পৌনে']],
])
const MULTIPLIER = words([
  [100, ['sho', 'shoo', 'sow', 'shoto', 'sau', 'so', 'hundred', 'শো', 'শ', 'শত']],
  [1000, ['hajar', 'hazar', 'hajaar', 'hazaar', 'thousand', 'হাজার']],
  [100000, ['lakh', 'lac', 'lakhs', 'লাখ', 'লক্ষ']],
])
// "so" is also an English word, so "500 so" must not become 50000; only "pach so" counts.
const WORD_ONLY_MULTIPLIERS = new Set(['so'])
// A multiplier that may stand alone at the start of an amount: "hajar taka dilo" = 1000.
const STANDALONE_MULTIPLIERS = new Set([...MULTIPLIER].filter(([, v]) => v >= 1000).map(([w]) => w))
const NUMBER_CURRENCY = new Set(['taka', 'takar', 'tk', 'rs', 'rupee', 'rupees', 'টাকা', 'টাকার'].map(nfc))
// Multiplier suffixes that are often written joined: "pachsho", "পাঁচশো", "দেড়শ".
const JOINED_SUFFIXES = [...MULTIPLIER.keys()]
  .filter((w) => !WORD_ONLY_MULTIPLIERS.has(w))
  .sort((a, b) => b.length - a.length)

const NUMBER_TOKEN_RE = /\d+(?:\.\d+)?|[A-Za-zঀ-৿]+/g
// "2,500" and Indian-style "1,25,000".
const THOUSANDS_SEP_RE = /(?<=\d),(?=\d{2,3}(?!\d))/g

interface Span {
  start: number
  end: number
  text: string
}

const isDigits = (text: string) => /^\d+$/.test(text)

function splitJoined(word: string): string[] {
  if (MULTIPLIER.has(word)) return [word]
  for (const suffix of JOINED_SUFFIXES) {
    if (word.endsWith(suffix) && word !== suffix) {
      const prefix = word.slice(0, -suffix.length)
      if (BASE.has(prefix) || FRACTION.has(prefix)) return [prefix, suffix]
    }
  }
  return [word]
}

function tokenize(text: string): Span[] {
  const spans: Span[] = []
  for (const m of text.matchAll(NUMBER_TOKEN_RE)) {
    const start = m.index
    for (const part of splitJoined(m[0].toLowerCase())) spans.push({ start, end: start + m[0].length, text: part })
  }
  return spans
}

function baseValue(text: string): number | null {
  if (BASE.has(text)) return BASE.get(text)!
  if (/^\d/.test(text)) return Number(text)
  return null
}

/** One "<number> <multiplier>" group starting at tokens[i]: [value, index after it]. */
function parseGroup(tokens: Span[], i: number, first: boolean): [number, number] | null {
  const n = tokens.length
  const text = tokens[i].text
  let value: number
  let j: number
  if (MODIFIERS.has(text) && i + 1 < n && BASE.has(tokens[i + 1].text)) {
    value = BASE.get(tokens[i + 1].text)! + MODIFIERS.get(text)!
    j = i + 2
  } else if (FRACTION.has(text)) {
    value = FRACTION.get(text)!
    j = i + 1
  } else if (MODIFIERS.has(text)) {
    return null
  } else if (first && STANDALONE_MULTIPLIERS.has(text)) {
    return [MULTIPLIER.get(text)!, i + 1]
  } else {
    const base = baseValue(text)
    if (base === null) return null
    value = base
    j = i + 1
  }
  if (j >= n || !MULTIPLIER.has(tokens[j].text)) return null
  if (WORD_ONLY_MULTIPLIERS.has(tokens[j].text) && /^\d/.test(text)) return null
  return [value * MULTIPLIER.get(tokens[j].text)!, j + 1]
}

/** A whole spoken amount starting at tokens[i], e.g. 'dui hajar pach sho ponchash'. */
function parseAmount(tokens: Span[], i: number): [number, number] | null {
  let total = 0
  let j = i
  let group: [number, number] | null
  while (j < tokens.length && (group = parseGroup(tokens, j, j === i))) {
    total += group[0]
    j = group[1]
  }
  // A small number word either ends the amount ("dui hajar pach sho ponchash taka") or is
  // the whole amount ("bish taka"). Digits are left alone; they need no conversion.
  if (j < tokens.length && BASE.has(tokens[j].text)) {
    const next = j + 1 < tokens.length ? tokens[j + 1].text : null
    if ((next !== null && NUMBER_CURRENCY.has(next)) || (total && next === null)) {
      total += BASE.get(tokens[j].text)!
      j += 1
    }
  }
  if (j === i || !Number.isInteger(total)) return null
  return [total, j]
}

/** Bangla digits and spoken amounts as plain digits: "salma pach sho taka" -> "salma 500 taka". */
export function normalizeNumbers(input: string): string {
  const text = nfc(input)
    .replace(/[০-৯]/g, (d) => String(BANGLA_DIGITS.indexOf(d)))
    .replace(THOUSANDS_SEP_RE, '')
  const tokens = tokenize(text)
  const pieces: string[] = []
  let lastEnd = 0
  let i = 0
  while (i < tokens.length) {
    const parsed = parseAmount(tokens, i)
    if (parsed === null) {
      i += 1
      continue
    }
    const [value, j] = parsed
    pieces.push(text.slice(lastEnd, tokens[i].start), String(value))
    lastEnd = tokens[j - 1].end
    i = j
  }
  pieces.push(text.slice(lastEnd))
  return pieces.join('')
}

// --- Honorifics (name_matching.py) --------------------------------------------------------

// prettier-ignore
const HONORIFICS = new Set([
  'bhai', 'bhaia', 'bhaiya', 'bhaiyya', 'vai', 'vaia', 'vaiya', 'bhaijan', 'vaijan',
  'apa', 'appa', 'aapa', 'apu', 'afa', 'da', 'dada', 'di', 'didi',
  'kaka', 'kaku', 'mama', 'mami', 'chacha', 'chachi', 'khala', 'khalu',
  'fupu', 'phupu', 'bhabi', 'vabi', 'boudi', 'bou',
  'sir', 'saheb', 'shaheb', 'sahib', 'ji', 'uncle', 'aunty', 'auntie', 'bro', 'mr', 'mrs',
  'ভাই', 'ভাইয়া', 'ভাইজান', 'আপা', 'আপু', 'দা', 'দাদা', 'দি', 'দিদি',
  'কাকা', 'কাকু', 'মামা', 'মামি', 'চাচা', 'চাচি', 'খালা', 'খালু',
  'ভাবি', 'বৌদি', 'সাহেব', 'স্যার', 'জি',
].map(nfc))
// Honorifics sometimes written joined to the name: "rahimbhai", "রহিমভাই".
const JOINED_HONORIFICS = ['bhaiya', 'bhai', 'vai', 'ভাই']

export const isHonorific = (word: string) => HONORIFICS.has(nfc(word.toLowerCase()))

/** The words of a name without honorifics, lowercased ("Rahim bhai" -> ["rahim"]). */
export function nameWords(name: string): string[] {
  const all = (nfc(name).match(/[A-Za-zঀ-৿]+/g) ?? []).map((w) => w.toLowerCase())
  const kept = all
    .filter((w) => !HONORIFICS.has(w))
    .map((w) => {
      for (const suffix of JOINED_HONORIFICS) {
        if (w.endsWith(suffix) && w.length - suffix.length >= 3) return w.slice(0, -suffix.length)
      }
      return w
    })
  return kept.length ? kept : all
}

/** "rahim bhai" -> "Rahim": the name a new customer gets (like the backend's clean_name). */
export function cleanName(name: string): string {
  const cleaned = nameWords(name)
    .map((w) => (/^\p{ASCII}+$/u.test(w) ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ')
  return cleaned || name.trim()
}

// --- The rule-based parser (rule_based.py) ------------------------------------------------

const set = (...list: string[]) => new Set(list.map(nfc))

// prettier-ignore
const CREDIT = set(
  'baki', 'baaki', 'bakee', 'nilo', 'nilen', 'nise', 'nisen', 'niyeche', 'niyechhe',
  'dhar', 'udhar', 'took', 'owes', 'due', 'credit', 'rakhlo', 'rakhlen', 'rakhse',
  'বাকি', 'বাকী', 'নিল', 'নিলো', 'নিলেন', 'নিয়েছে', 'ধার', 'রাখল', 'রাখলো',
)
// prettier-ignore
const PAYMENT = set(
  'dilo', 'dilen', 'dise', 'disen', 'diyeche', 'diyechhe', 'jama', 'joma', 'shodh',
  'sodh', 'porishodh', 'paid', 'gave', 'returned', 'payment',
  'দিল', 'দিলো', 'দিলেন', 'দিয়েছে', 'জমা', 'শোধ', 'পরিশোধ',
)
// prettier-ignore
const CURRENCY = set(
  'taka', 'takar', 'takay', 'tk', 'tka', 'rs', 'rupee', 'rupees', 'inr', 'bdt', '৳',
  'টাকা', 'টাকার', 'টাকায়',
)
// prettier-ignore
const UNITS = set(
  'kg', 'kilo', 'g', 'gm', 'gram', 'ta', 'ti', 'pc', 'pcs', 'piece', 'pieces', 'packet',
  'pkt', 'liter', 'litre', 'ltr', 'l', 'dozen', 'hali', 'bosta', 'cup', 'bottle',
  'কেজি', 'গ্রাম', 'টা', 'টি', 'প্যাকেট', 'লিটার', 'হালি', 'ডজন', 'বস্তা',
)
// Joins items: "dal r tel", "dal, tel".
const SEPARATORS = set('r', 'ar', 'and', 'o', 'আর', 'ও', ',', ';', '/', '.')
// Small words that are neither name nor item.
// prettier-ignore
const FILLER = set(
  'er', 'ke', 'theke', 'aj', 'ajke', 'today', 'kal', 'gotokal', 'yesterday', 'the', 'of',
  'for', 'worth', 'amount', 'korlo', 'korlen', 'korse', 'kore',
  'আজ', 'আজকে', 'গতকাল', 'কাল', 'কে', 'এর', 'করল', 'করলো', 'করলেন',
)

// "৳" sits inside the Bangla Unicode block, so it is matched before Bangla letters.
const TOKEN_RE = /৳|\d+|[A-Za-zঀ-৲৴-৿]+|[,;/.]/g
const ENTRY_SEPARATOR_RE = /[,;\n]/
const MAX_ENTRIES = 10
const MAX_ITEM_LENGTH = 200

export interface RulesEntry {
  customer_name: string
  amount: number
  type: 'credit' | 'payment'
  item: string | null
  confidence: number
}
/** The same JSON the backend's rule-based parser answers. */
export type RulesAnswer = RulesEntry | { entries: RulesEntry[] } | { error: string }

class Token {
  readonly text: string
  readonly key: string
  constructor(text: string) {
    this.text = text
    this.key = text.toLowerCase()
  }
  get isNumber() {
    return isDigits(this.text)
  }
  get isKeyword() {
    return CREDIT.has(this.key) || PAYMENT.has(this.key)
  }
  get isWord() {
    return !this.isNumber && !SEPARATORS.has(this.key) && this.text !== '৳'
  }
}

const isUpper = (text: string) => /^\p{Lu}/u.test(text)

/** The whole sentence: one entry, or {entries: [...]} when it lists several customers. */
export function parseText(sentence: string): RulesAnswer {
  // Numbers first, so "2,500" isn't split at its comma.
  const parts = normalizeNumbers(sentence)
    .split(ENTRY_SEPARATOR_RE)
    .filter((p) => p.trim())
  if (parts.length > 1 && parts.length <= MAX_ENTRIES) {
    const entries = parts.map(parseSentence)
    if (entries.every((entry) => !('error' in entry))) return { entries: entries as RulesEntry[] }
  }
  return parseSentence(sentence)
}

export function parseSentence(sentence: string): RulesEntry | { error: string } {
  const tokens = [...normalizeNumbers(sentence).matchAll(TOKEN_RE)].map((m) => new Token(m[0]))
  const nameIdx = nameTokens(tokens)
  if (!nameIdx.length) return { error: 'no customer name' }
  const amount = amountToken(tokens)
  if (amount === null) return { error: 'no amount' }
  const [amountIdx, amountSure] = amount

  const keys = new Set(tokens.map((t) => t.key))
  const has = (words: Set<string>) => [...keys].some((k) => words.has(k))
  let type: RulesEntry['type'] = 'credit'
  let typeSure = false
  if (has(PAYMENT)) [type, typeSure] = ['payment', true]
  else if (has(CREDIT)) [type, typeSure] = ['credit', true]
  // Otherwise: goods with no payment word count as credit, the same rule as the prompt.

  const item = type === 'credit' ? itemOf(tokens, new Set([...nameIdx, amountIdx])) : null
  return {
    customer_name: nameIdx.map((i) => tokens[i].text).join(' '),
    amount: parseInt(tokens[amountIdx].text, 10),
    type,
    item,
    confidence: typeSure && amountSure ? 0.8 : 0.55,
  }
}

function couldBeName(token: Token): boolean {
  return (
    token.isWord &&
    !token.isKeyword &&
    !isHonorific(token.text) &&
    !CURRENCY.has(token.key) &&
    !UNITS.has(token.key) &&
    !FILLER.has(token.key)
  )
}

/** The first real word, plus a second one when both are capitalized ("Rahim Uddin"). */
function nameTokens(tokens: Token[]): number[] {
  let i = 0
  while (
    i < tokens.length &&
    (FILLER.has(tokens[i].key) || SEPARATORS.has(tokens[i].key) || isHonorific(tokens[i].text))
  )
    i += 1
  if (i >= tokens.length || !couldBeName(tokens[i])) return []
  const found = [i]
  const next = tokens[i + 1]
  if (next && couldBeName(next) && isUpper(tokens[i].text) && isUpper(next.text)) found.push(i + 1)
  return found
}

/** Index of the money amount, and whether it is clear (next to "taka", or the only number). */
function amountToken(tokens: Token[]): [number, boolean] | null {
  let best: [number, number, number] | null = null // score, value, index
  let count = 0
  for (const [i, token] of tokens.entries()) {
    if (!token.isNumber || parseInt(token.text, 10) === 0) continue
    const before = i > 0 ? tokens[i - 1].key : ''
    const after = i + 1 < tokens.length ? tokens[i + 1].key : ''
    let score: number
    if (CURRENCY.has(after) || CURRENCY.has(before)) score = 2
    else if (UNITS.has(after))
      continue // a quantity, like "2 kg"
    else score = 1
    count += 1
    const value = parseInt(token.text, 10)
    if (best === null || score > best[0] || (score === best[0] && value > best[1])) best = [score, value, i]
  }
  if (best === null) return null
  const [score, , index] = best
  return [index, score === 2 || count === 1]
}

/** What's left once name, amount, keywords and filler are removed, grouped into items. */
function itemOf(tokens: Token[], used: Set<number>): string | null {
  const groups: string[][] = [[]]
  tokens.forEach((token, i) => {
    const skip =
      used.has(i) ||
      token.isKeyword ||
      CURRENCY.has(token.key) ||
      FILLER.has(token.key) ||
      SEPARATORS.has(token.key) ||
      token.text === '৳' ||
      isHonorific(token.text)
    if (skip) {
      if (groups[groups.length - 1].length) groups.push([])
    } else groups[groups.length - 1].push(token.text)
  })
  const items = groups.filter((g) => g.length).map((g) => g.join(' '))
  return [...items.join(', ')].slice(0, MAX_ITEM_LENGTH).join('') || null
}
