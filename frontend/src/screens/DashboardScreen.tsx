import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { CustomerBalanceSummary, Dashboard } from '../api/types'
import { WeekChart } from '../components/WeekChart'
import { Button } from '../components/ui'
import { formatDay, formatTaka } from '../format'
import { href } from '../route'
import { strings } from '../strings'

/** The shop at a glance: what's owed, today's money, who owes most, and old baki to chase. */
export function DashboardScreen() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [failed, setFailed] = useState(false)

  const load = useCallback(() => api.dashboard().then(setData, () => setFailed(true)), [])

  useEffect(() => {
    load()
  }, [load])

  if (failed) {
    return (
      <div className="flex flex-col gap-3 rounded-2xl bg-white p-4">
        <p className="text-lg text-stone-700">{strings.dashboardFailed}</p>
        <Button
          variant="secondary"
          onClick={() => {
            setFailed(false)
            load()
          }}
        >
          {strings.retry}
        </Button>
      </div>
    )
  }
  if (!data) {
    return (
      <p role="status" className="text-lg text-stone-600">
        {strings.loading}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <h2 className="sr-only">{strings.dashboardTitle}</h2>
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          className="col-span-2"
          label={strings.totalBaki}
          value={formatTaka(data.total_outstanding)}
          tone="text-red-700"
          size="text-5xl"
          detail={strings.totalBakiFrom(data.customers_with_baki)}
          testId="stat-total"
        />
        <StatCard
          label={strings.todayPayment}
          value={formatTaka(data.today_collection)}
          tone="text-green-700"
          testId="stat-today-payment"
        />
        <StatCard
          label={strings.todayNewCredit}
          value={formatTaka(data.today_new_credit)}
          tone="text-red-700"
          testId="stat-today-credit"
        />
      </div>

      <WeekChart days={data.last_7_days} today={data.today} />

      <CustomerList
        id="top"
        title={strings.topTitle}
        empty={strings.topEmpty}
        customers={data.top_customers}
        detail={(c) => c.note}
      />

      <CustomerList
        id="overdue"
        title={`⚠ ${strings.overdueTitle(data.overdue_days)}`}
        empty={strings.overdueEmpty(data.overdue_days)}
        customers={data.overdue_customers}
        detail={(c) =>
          [c.note, `${strings.overdueSince(c.days_outstanding)} (${formatDay(c.owed_since)} theke)`]
            .filter(Boolean)
            .join(' · ')
        }
        warning
      />
    </div>
  )
}

function StatCard({
  label,
  value,
  tone,
  detail,
  size = 'text-3xl',
  className = '',
  testId,
}: {
  label: string
  value: string
  tone: string
  detail?: string
  size?: string
  className?: string
  testId: string
}) {
  return (
    <div className={`flex flex-col gap-1 rounded-2xl bg-white p-4 ${className}`} data-testid={testId}>
      <p className="text-lg font-semibold text-stone-700">{label}</p>
      <p className={`${size} font-bold break-all tabular-nums ${tone}`}>{value}</p>
      {detail && <p className="text-base text-stone-600">{detail}</p>}
    </div>
  )
}

function CustomerList<T extends CustomerBalanceSummary>({
  id,
  title,
  empty,
  customers,
  detail,
  warning = false,
}: {
  id: string
  title: string
  empty: string
  customers: T[]
  detail: (customer: T) => string | null
  warning?: boolean
}) {
  return (
    <section aria-labelledby={`${id}-title`} className="flex flex-col gap-3">
      <h2 id={`${id}-title`} className={`text-xl font-bold ${warning ? 'text-amber-900' : 'text-stone-800'}`}>
        {title}
      </h2>
      {customers.length === 0 ? (
        <p className="rounded-2xl bg-white p-4 text-lg text-stone-600">{empty}</p>
      ) : (
        <ul
          aria-labelledby={`${id}-title`}
          className={`flex flex-col divide-y overflow-hidden rounded-2xl bg-white ${
            warning ? 'divide-amber-200 border-2 border-amber-300' : 'divide-stone-200'
          }`}
        >
          {customers.map((customer) => {
            const text = detail(customer)
            return (
              <li key={customer.id}>
                <a
                  href={href.khata(customer.id)}
                  className="flex min-h-16 items-center justify-between gap-3 px-4 py-3 active:bg-stone-100"
                >
                  <div className="min-w-0">
                    <p className="truncate text-lg font-semibold text-stone-900">{customer.name}</p>
                    {text && <p className="text-base text-stone-600">{text}</p>}
                  </div>
                  <span className="shrink-0 text-xl font-bold text-red-700 tabular-nums">
                    {formatTaka(customer.balance)}
                  </span>
                </a>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
