import { strings } from './strings'

const takaFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

/** 125000 -> "৳1,25,000" (South Asian digit grouping). */
export function formatTaka(amount: number): string {
  return `৳${takaFormat.format(Math.abs(amount))}`
}

/** What a customer's balance means, in words: "Baki ৳300", "Agrim ৳200" or "Hisab clear". */
export function describeBalance(balance: number): string {
  if (balance > 0) return strings.balanceOwes(formatTaka(balance))
  if (balance < 0) return strings.balanceAdvance(formatTaka(balance))
  return strings.balanceClear
}

/** "Aj 2:30 PM", "Gotokal", "3 din age". */
export function formatWhen(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000)
  if (days <= 0) {
    const time = date.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
    return `${strings.today} ${time}`
  }
  if (days === 1) return strings.yesterday
  return strings.daysAgo(days)
}

const BANGLA_DIGITS = '০১২৩৪৫৬৭৮৯'

/** Parse a typed amount: Bangla digits and commas are fine. Returns null if it isn't whole taka. */
export function parseAmount(text: string): number | null {
  const digits = text.replace(/[০-৯]/g, (d) => String(BANGLA_DIGITS.indexOf(d))).replace(/[,\s৳]/g, '')
  if (!/^\d+$/.test(digits)) return null
  const value = Number(digits)
  return value >= 1 && value <= 10_000_000 ? value : null
}

const sameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()

/** For the khata: "Aj 2:30 PM", "Gotokal 6:10 PM", "21 Oct, 2:30 PM", "21 Oct 2025, 2:30 PM". */
export function formatDateTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
  if (sameDay(date, now)) return `${strings.today} ${time}`
  if (sameDay(date, yesterday)) return `${strings.yesterday} ${time}`
  const day = date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
  })
  return `${day}, ${time}`
}

/** A timestamp's date on this phone: "22 Sept". */
export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

/** A shop-local calendar date from the API ("2026-10-27") as "27 Oct". */
export function formatShortDate(day: string): string {
  const [year, month, date] = day.split('-').map(Number)
  return new Date(year, month - 1, date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
