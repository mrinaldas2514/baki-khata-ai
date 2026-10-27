import type { ReactNode } from 'react'
import { type Tab, href } from '../route'
import { strings } from '../strings'

const icon = (path: ReactNode) => (
  <svg
    viewBox="0 0 24 24"
    className="size-7"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    {path}
  </svg>
)

const TABS: { tab: Tab; href: string; label: string; icon: ReactNode }[] = [
  {
    tab: 'hisab',
    href: href.hisab,
    label: strings.nav.hisab,
    icon: icon(
      <>
        <path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z" />
        <path d="m13.5 6.5 4 4" />
      </>,
    ),
  },
  {
    tab: 'customers',
    href: href.customers,
    label: strings.nav.customers,
    icon: icon(
      <>
        <circle cx="9" cy="8" r="3.5" />
        <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
        <path d="M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.5A6.5 6.5 0 0 1 21.5 20" />
      </>,
    ),
  },
  {
    tab: 'dashboard',
    href: href.dashboard,
    label: strings.nav.dashboard,
    icon: icon(
      <>
        <path d="M4 20V10M10 20V4M16 20v-7M21 20H3" />
      </>,
    ),
  },
]

/** Three big tabs at the bottom, in thumb reach. Fits a 360 px wide phone. */
export function BottomNav({ active }: { active: Tab }) {
  return (
    <nav
      aria-label={strings.nav.label}
      className="fixed inset-x-0 bottom-0 z-30 border-t border-stone-200 bg-white pb-[env(safe-area-inset-bottom)] shadow-[0_-2px_8px_rgba(0,0,0,0.06)]"
    >
      <ul className="mx-auto grid max-w-md grid-cols-3">
        {TABS.map((item) => {
          const current = item.tab === active
          return (
            <li key={item.tab}>
              <a
                href={item.href}
                aria-current={current ? 'page' : undefined}
                className={`relative flex min-h-16 flex-col items-center justify-center gap-0.5 px-1 text-base font-semibold transition-colors ${
                  current ? 'bg-emerald-50 text-emerald-800' : 'text-stone-600 active:bg-stone-100'
                }`}
              >
                {current && <span className="absolute inset-x-6 top-0 h-1 rounded-b-full bg-emerald-700" aria-hidden />}
                {item.icon}
                <span>{item.label}</span>
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
