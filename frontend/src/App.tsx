import { useEffect, useRef, useState } from 'react'
import { BottomNav } from './components/BottomNav'
import { type CustomerSort } from './customers'
import { tabOf, useRoute } from './route'
import { CustomersScreen } from './screens/CustomersScreen'
import { DashboardScreen } from './screens/DashboardScreen'
import { HisabScreen } from './screens/HisabScreen'
import { KhataScreen } from './screens/KhataScreen'
import { strings } from './strings'

/** The app shell: a title bar, the current screen, and the three tabs at the bottom. */
export default function App() {
  const route = useRoute()
  const tab = tabOf(route)
  const topRef = useRef<HTMLDivElement>(null)
  // Kept here so search and sort survive opening a khata and coming back.
  const [listSearch, setListSearch] = useState('')
  const [listSort, setListSort] = useState<CustomerSort>('most-owed')

  useEffect(() => {
    topRef.current?.scrollIntoView?.({ block: 'start' })
  }, [route])

  return (
    <div ref={topRef} className="min-h-dvh bg-stone-100 pb-[calc(5rem+env(safe-area-inset-bottom))]">
      <header className="bg-emerald-800 px-4 py-3 text-white">
        <h1 className="mx-auto max-w-md text-2xl font-bold">{strings.appTitle}</h1>
      </header>
      <main className="mx-auto max-w-md px-4 py-5">
        <div hidden={tab !== 'hisab'}>
          <HisabScreen active={tab === 'hisab'} />
        </div>
        {route.name === 'customers' && (
          <CustomersScreen search={listSearch} onSearch={setListSearch} sort={listSort} onSort={setListSort} />
        )}
        {route.name === 'khata' && <KhataScreen key={route.customerId} customerId={route.customerId} />}
        {route.name === 'dashboard' && <DashboardScreen />}
      </main>
      <BottomNav active={tab} />
    </div>
  )
}
