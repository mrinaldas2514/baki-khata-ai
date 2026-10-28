import { type AnchorHTMLAttributes, type ComponentProps, type ReactNode, useState } from 'react'
import type { ParserKind, TransactionType } from '../api/types'
import { strings } from '../strings'
import { TYPE_STYLES } from '../typeStyles'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'destructive' | 'whatsapp' | 'credit' | 'payment'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-emerald-700 text-white active:bg-emerald-800 disabled:bg-stone-400',
  secondary: 'bg-white text-stone-900 border-2 border-stone-300 active:bg-stone-100 disabled:text-stone-400',
  ghost: 'bg-transparent text-stone-700 underline-offset-4 active:bg-stone-100',
  danger: 'bg-white text-red-700 border-2 border-red-200 active:bg-red-50',
  // The final "yes, delete it".
  destructive: 'bg-red-700 text-white active:bg-red-800 disabled:bg-stone-400',
  whatsapp: 'bg-[#1a7f4b] text-white active:bg-[#14663c]',
  // "Baki likhun" / "Joma likhun": the same colors as Baki and Joma everywhere else.
  credit: 'bg-orange-700 text-white active:bg-orange-800',
  payment: 'bg-green-700 text-white active:bg-green-800',
}

const BUTTON_BASE = 'min-h-14 rounded-2xl px-5 text-xl font-semibold transition-colors disabled:cursor-not-allowed'

/** A large tap target (at least 56 px high) with big text. */
export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...props
}: ComponentProps<'button'> & { variant?: Variant }) {
  return <button type={type} className={`${BUTTON_BASE} ${VARIANTS[variant]} ${className}`} {...props} />
}

/** A link that looks like a Button (e.g. "WhatsApp-e khulun"). */
export function ButtonLink({
  variant = 'primary',
  className = '',
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant }) {
  return (
    <a
      className={`${BUTTON_BASE} flex items-center justify-center text-center ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}

const ALERT_TONES = {
  error: 'border-red-300 bg-red-50 text-red-900',
  warning: 'border-amber-300 bg-amber-50 text-amber-950',
  info: 'border-emerald-300 bg-emerald-50 text-emerald-950',
}

export function Alert({ tone = 'error', children }: { tone?: keyof typeof ALERT_TONES; children: ReactNode }) {
  return (
    <div
      role={tone === 'info' ? 'status' : 'alert'}
      className={`rounded-2xl border-2 px-4 py-3 text-lg ${ALERT_TONES[tone]}`}
    >
      {children}
    </div>
  )
}

/** "AI" or "AI chhara": who read the sentence on a confirmation card. */
export function ParserLabel({ parser, model }: { parser: ParserKind; model: string }) {
  const isLlm = parser === 'llm'
  return (
    <span
      title={isLlm ? strings.parser.llmTitle(model) : strings.parser.rulesTitle}
      data-testid="parser-label"
      className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-sm font-semibold ${
        isLlm ? 'border-violet-300 bg-violet-50 text-violet-900' : 'border-stone-300 bg-stone-100 text-stone-800'
      }`}
    >
      <span className="sr-only">{strings.parser.readBy} </span>
      {isLlm ? strings.parser.llm : strings.parser.rules}
    </span>
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

export const inputClass =
  'min-h-14 w-full rounded-2xl border-2 border-stone-300 bg-white px-4 text-xl text-stone-900 placeholder:text-stone-500 focus:border-emerald-600 focus:outline-none aria-invalid:border-red-500'

/** A labelled input with its problem underneath: name, phone, note... */
export function Field({
  id,
  label,
  hint,
  problem,
  ...input
}: ComponentProps<'input'> & { id: string; label: string; hint?: string; problem?: string | null }) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-xl font-semibold text-stone-900">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(problem)}
        aria-describedby={problem ? `${id}-problem` : hint ? `${id}-hint` : undefined}
        className={inputClass}
        {...input}
      />
      {hint && !problem && (
        <p id={`${id}-hint`} className="text-base text-stone-600">
          {hint}
        </p>
      )}
      {problem && (
        <p id={`${id}-problem`} className="text-lg text-red-700">
          {problem}
        </p>
      )}
    </div>
  )
}

/** A password box with a big "show / hide" button, so it can be checked before sending. */
export function PasswordInput({
  id,
  label,
  problem,
  ...input
}: ComponentProps<'input'> & { id: string; label: string; problem?: string | null }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-xl font-semibold text-stone-900">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          aria-invalid={Boolean(problem)}
          aria-describedby={problem ? `${id}-problem` : undefined}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          className={`${inputClass} pr-24`}
          {...input}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-pressed={visible}
          aria-controls={id}
          aria-label={strings.auth.showPassword}
          className="absolute top-1/2 right-1 min-h-12 min-w-20 -translate-y-1/2 rounded-xl px-3 text-lg font-semibold text-emerald-800 active:bg-stone-100"
        >
          {visible ? strings.auth.hide : strings.auth.show}
        </button>
      </div>
      {problem && (
        <p id={`${id}-problem`} className="text-lg text-red-700">
          {problem}
        </p>
      )}
    </div>
  )
}

/** A big taka amount box: "৳" in front, numeric keyboard on phones. */
export function AmountInput({
  id,
  value,
  onChange,
  invalid = false,
  autoFocus = false,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  invalid?: boolean
  autoFocus?: boolean
}) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-3xl text-stone-500">৳</span>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode="numeric"
        autoComplete="off"
        autoFocus={autoFocus}
        aria-invalid={invalid}
        className={`${inputClass} pl-11 text-3xl font-bold tabular-nums`}
      />
    </div>
  )
}

/** Baki / Joma as two big radio cards. */
export function TypeToggle({
  name,
  value,
  onChange,
}: {
  name: string
  value: TransactionType
  onChange: (value: TransactionType) => void
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-xl font-semibold text-stone-900">{strings.type}</legend>
      <div className="grid grid-cols-2 gap-3">
        {(['credit', 'payment'] as const).map((type) => {
          const style = TYPE_STYLES[type]
          const checked = value === type
          return (
            <label
              key={type}
              className={`flex min-h-16 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 px-2 text-center has-focus-visible:ring-2 has-focus-visible:ring-stone-900 ${
                checked
                  ? `${style.panel} ring-2 ring-current ${style.text}`
                  : 'border-stone-300 bg-white text-stone-700'
              }`}
            >
              <input
                type="radio"
                name={name}
                value={type}
                checked={checked}
                onChange={() => onChange(type)}
                className="sr-only"
              />
              <span className="text-2xl font-bold">{style.label}</span>
              <span className="text-sm">{style.hint}</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
