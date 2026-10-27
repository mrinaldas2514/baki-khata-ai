import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { TransactionType } from '../api/types'
import { TYPE_STYLES } from '../typeStyles'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-emerald-700 text-white active:bg-emerald-800 disabled:bg-stone-400',
  secondary: 'bg-white text-stone-900 border-2 border-stone-300 active:bg-stone-100 disabled:text-stone-400',
  ghost: 'bg-transparent text-stone-700 underline-offset-4 active:bg-stone-100',
  danger: 'bg-white text-red-700 border-2 border-red-200 active:bg-red-50',
}

/** A large tap target (at least 56 px high) with big text. */
export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`min-h-14 rounded-2xl px-5 text-xl font-semibold transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}

export function Alert({ tone = 'error', children }: { tone?: 'error' | 'warning'; children: ReactNode }) {
  const style =
    tone === 'error' ? 'border-red-300 bg-red-50 text-red-900' : 'border-amber-300 bg-amber-50 text-amber-950'
  return (
    <div role="alert" className={`rounded-2xl border-2 px-4 py-3 text-lg ${style}`}>
      {children}
    </div>
  )
}

export function TypeBadge({ type }: { type: TransactionType }) {
  const style = TYPE_STYLES[type]
  return (
    <span className={`inline-block rounded-full border px-3 py-0.5 text-base font-bold ${style.badge}`}>
      {style.label}
    </span>
  )
}
