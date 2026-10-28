import { useState } from 'react'
import type { DaySummary } from '../api/types'
import { formatShortDate, formatTaka } from '../format'
import { strings } from '../strings'

// Validated as a pair (dataviz palette check): different lightness and hue, and never the only
// cue: the legend names them and the selected day's numbers are written out below.
const CREDIT_BAR = 'bg-orange-600'
const PAYMENT_BAR = 'bg-green-600'

/** Last 7 days, new baki vs joma, as paired columns. Tap a day to read its numbers. */
export function WeekChart({ days, today }: { days: DaySummary[]; today: string }) {
  const [selected, setSelected] = useState(days.length - 1)
  const max = Math.max(0, ...days.flatMap((d) => [d.credit, d.payment]))
  const label = (day: DaySummary) =>
    day.date === today ? `${strings.today} (${formatShortDate(day.date)})` : formatShortDate(day.date)
  const detail = (day: DaySummary) => strings.weekDayDetail(label(day), formatTaka(day.credit), formatTaka(day.payment))
  const current = days[selected] ?? days[days.length - 1]

  return (
    <section aria-labelledby="week-title" className="flex flex-col gap-3 rounded-2xl bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="week-title" className="text-xl font-bold text-stone-800">
          {strings.weekTitle}
        </h2>
        <ul className="flex gap-4 text-base text-stone-700" aria-hidden>
          <li className="flex items-center gap-1.5">
            <span className={`size-3 rounded-sm ${CREDIT_BAR}`} />
            {strings.weekLegendCredit}
          </li>
          <li className="flex items-center gap-1.5">
            <span className={`size-3 rounded-sm ${PAYMENT_BAR}`} />
            {strings.weekLegendPayment}
          </li>
        </ul>
      </div>

      {max === 0 ? (
        <p className="text-lg text-stone-600">{strings.weekEmpty}</p>
      ) : (
        <>
          <div aria-hidden className="relative">
            <p className="absolute -top-0.5 left-0 text-xs text-stone-500 tabular-nums">
              {strings.weekMax(formatTaka(max))}
            </p>
            <div className="grid grid-cols-7 gap-1 border-b border-stone-300 pt-5">
              {days.map((day, index) => (
                <button
                  key={day.date}
                  type="button"
                  tabIndex={-1}
                  onClick={() => setSelected(index)}
                  onMouseEnter={() => setSelected(index)}
                  className={`flex h-36 items-end justify-center gap-0.5 rounded-t-lg ${index === selected ? 'bg-stone-100' : ''}`}
                >
                  <Bar className={CREDIT_BAR} value={day.credit} max={max} />
                  <Bar className={PAYMENT_BAR} value={day.payment} max={max} />
                </button>
              ))}
            </div>
          </div>
          <div role="group" aria-label={strings.weekTitle} className="grid grid-cols-7 gap-1">
            {days.map((day, index) => (
              <button
                key={day.date}
                type="button"
                aria-pressed={index === selected}
                aria-label={detail(day)}
                onClick={() => setSelected(index)}
                className={`min-h-12 rounded-lg text-sm tabular-nums ${
                  index === selected ? 'bg-stone-800 font-bold text-white' : 'text-stone-600 active:bg-stone-100'
                }`}
              >
                {day.date === today ? strings.today : Number(day.date.slice(8))}
              </button>
            ))}
          </div>
          <p aria-live="polite" className="text-lg text-stone-800" data-testid="week-detail">
            {detail(current)}
          </p>
        </>
      )}

      {/* sr-only on a wrapper: a table ignores width: 1px and would widen the page. */}
      <div className="sr-only">
        <table>
          <caption>{strings.weekTableCaption}</caption>
          <thead>
            <tr>
              <th scope="col">{strings.weekDay}</th>
              <th scope="col">{strings.weekLegendCredit}</th>
              <th scope="col">{strings.weekLegendPayment}</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.date}>
                <th scope="row">{label(day)}</th>
                <td>{formatTaka(day.credit)}</td>
                <td>{formatTaka(day.payment)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** A column at most 14 px wide, rounded only at its top, growing from the baseline. */
function Bar({ className, value, max }: { className: string; value: number; max: number }) {
  if (value <= 0) return <span className="w-3.5" />
  // Even a small amount stays visible next to a big one.
  const height = Math.max(3, (value / max) * 100)
  return <span className={`w-3.5 rounded-t ${className}`} style={{ height: `${height}%` }} />
}
