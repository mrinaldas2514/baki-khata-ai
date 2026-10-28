/**
 * Mobile numbers from Bangladesh and India, written the way the backend stores them
 * (backend/app/services/phones.py has the same rules; the backend has the final say):
 *
 *   01711-000001, +880 1711 000001  -> +8801711000001
 *   +91 98765 43210, 09876543210     -> +919876543210
 */
const BD = /^1[3-9]\d{8}$/
const IN = /^[6-9]\d{9}$/

/** The number in +880… / +91… form, or null if it isn't a Bangladesh or India mobile. */
export function normalizeMobile(text: string): string | null {
  const trimmed = text.trim()
  if (!/^\+?[\d\s\-().]+$/.test(trimmed)) return null
  let digits = trimmed.replace(/\D/g, '')
  const international = trimmed.startsWith('+') || digits.startsWith('00')
  if (digits.startsWith('00')) digits = digits.slice(2)

  if (international || digits.length === 12 || digits.length === 13) {
    if (digits.startsWith('880') && BD.test(digits.slice(3))) return `+880${digits.slice(3)}`
    if (digits.startsWith('91') && IN.test(digits.slice(2))) return `+91${digits.slice(2)}`
    if (international) return null
  }
  const local = digits.startsWith('0') ? digits.slice(1) : digits
  if (BD.test(local)) return `+880${local}`
  if (IN.test(local)) return `+91${local}`
  return null
}

/** For showing: +8801711000001 -> "01711-000001", +919876543210 -> "+91 98765 43210". */
export function formatPhone(phone: string): string {
  if (/^\+880\d{10}$/.test(phone)) return `0${phone.slice(4, 8)}-${phone.slice(8)}`
  if (/^\+91\d{10}$/.test(phone)) return `+91 ${phone.slice(3, 8)} ${phone.slice(8)}`
  return phone
}
