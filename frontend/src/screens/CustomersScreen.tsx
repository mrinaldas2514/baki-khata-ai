import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { CustomerListItem } from '../api/types'
import { Button, inputClass } from '../components/ui'
import { type CustomerSort, daysOwed, matchesSearch, sortCustomers } from '../customers'
import { describeBalance, formatTaka } from '../format'
import { href } from '../route'
import { strings } from '../strings'
import { balanceTone } from '../typeStyles'

const SORTS: CustomerSort[] = ['most-owed', 'oldest-owed', 'name']

interface Props {
  search: string
  onSearch: (search: string) => void
  sort: CustomerSort
  onSort: (sort: CustomerSort) => void
}

/** Every customer with their balance. Search by name (either script), area or phone; tap to open the khata. */
export function CustomersScreen({ search, onSearch, sort, onSort }: Props) {
  const [customers, setCustomers] = useState<CustomerListItem[] | null>(null)
  const [failed, setFailed] = useState(false)

  const load = useCallback(() => api.customers().then(setCustomers, () => setFailed(true)), [])

  useEffect(() => {
    load()
  }, [load])

  const shown = useMemo(
    () =>
      customers
        ? sortCustomers(
            customers.filter((c) => matchesSearch(c, search)),
            sort,
          )
        : [],
    [customers, search, sort],
  )
  const owing = customers?.filter((c) => c.balance > 0) ?? []
  const totalOwed = owing.reduce((sum, c) => sum + c.balance, 0)

  return (
    <section aria-labelledby="customers-title" className="flex flex-col gap-4">
      <div>
        <h2 id="customers-title" className="text-2xl font-bold text-stone-900">
          {strings.customersTitle}
        </h2>
        {customers && customers.length > 0 && (
          <p className="text-lg text-stone-700">
            {owing.length > 0
              ? strings.customersWithBaki(owing.length, formatTaka(totalOwed))
              : strings.customerCount(customers.length)}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <label htmlFor="customer-search" className="sr-only">
          {strings.searchLabel}
        </label>
        <div className="relative">
          <input
            id="customer-search"
            type="search"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder={strings.searchPlaceholder}
            autoComplete="off"
            enterKeyHint="search"
            className={`${inputClass} pr-14 [&::-webkit-search-cancel-button]:hidden`}
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearch('')}
              aria-label={strings.clearSearch}
              className="absolute top-1/2 right-1 flex size-12 -translate-y-1/2 items-center justify-center rounded-full text-3xl text-stone-500 active:bg-stone-100"
            >
              ×
            </button>
          )}
        </div>

        <div role="group" aria-label={strings.sortLabel} className="flex gap-2">
          {SORTS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={sort === value}
              onClick={() => onSort(value)}
              className={`min-h-12 flex-auto rounded-xl border-2 px-2 text-base font-semibold whitespace-nowrap transition-colors ${
                sort === value
                  ? 'border-emerald-700 bg-emerald-700 text-white'
                  : 'border-stone-300 bg-white text-stone-700 active:bg-stone-100'
              }`}
            >
              {strings.sort[value]}
            </button>
          ))}
        </div>
      </div>

      {failed ? (
        <div className="flex flex-col gap-3 rounded-2xl bg-white p-4">
          <p className="text-lg text-stone-700">{strings.customersFailed}</p>
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
      ) : customers === null ? (
        <p role="status" className="text-lg text-stone-600">
          {strings.loading}
        </p>
      ) : customers.length === 0 ? (
        <p className="rounded-2xl bg-white p-4 text-lg text-stone-600">{strings.customersEmpty}</p>
      ) : shown.length === 0 ? (
        <p className="rounded-2xl bg-white p-4 text-lg text-stone-600">{strings.noSearchResult(search.trim())}</p>
      ) : (
        <ul
          aria-label={strings.customersTitle}
          className="flex flex-col divide-y divide-stone-200 overflow-hidden rounded-2xl bg-white"
        >
          {shown.map((customer) => (
            <CustomerRow key={customer.id} customer={customer} />
          ))}
        </ul>
      )}
    </section>
  )
}

function CustomerRow({ customer }: { customer: CustomerListItem }) {
  const days = daysOwed(customer)
  const detail = [customer.note, days !== null ? strings.owedForDays(days) : null].filter(Boolean).join(' · ')
  return (
    <li>
      <a
        href={href.khata(customer.id)}
        className="flex min-h-18 items-center justify-between gap-3 px-4 py-3 active:bg-stone-100"
      >
        <div className="min-w-0">
          <p className="truncate text-xl font-semibold text-stone-900">{customer.name}</p>
          {detail && <p className="truncate text-base text-stone-600">{detail}</p>}
        </div>
        <span
          className={`shrink-0 text-right text-xl font-bold tabular-nums ${balanceTone(customer.balance)}`}
          data-testid="customer-balance"
        >
          {customer.balance === 0 ? `✓ ${strings.balanceClearShort}` : describeBalance(customer.balance)}
        </span>
      </a>
    </li>
  )
}
