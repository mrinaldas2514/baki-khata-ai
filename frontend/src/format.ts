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
