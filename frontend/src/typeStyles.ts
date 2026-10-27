import type { TransactionType } from './api/types'
import { strings } from './strings'

/** Baki = red/orange, Joma = green, everywhere in the app. */
export const TYPE_STYLES: Record<
  TransactionType,
  { label: string; hint: string; text: string; badge: string; panel: string }
> = {
  credit: {
    label: strings.typeCredit,
    hint: strings.typeCreditHint,
    text: 'text-red-700',
    badge: 'bg-orange-100 text-red-800 border-orange-300',
    panel: 'bg-orange-50 border-orange-400',
  },
  payment: {
    label: strings.typePayment,
    hint: strings.typePaymentHint,
    text: 'text-green-700',
    badge: 'bg-green-100 text-green-800 border-green-300',
    panel: 'bg-green-50 border-green-500',
  },
}

/** A balance's color: red while the customer owes (baki), green when clear or paid ahead. */
export function balanceTone(balance: number): string {
  return balance > 0 ? 'text-red-700' : 'text-green-700'
}
