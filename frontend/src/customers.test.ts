import { describe, expect, it } from 'vitest'
import { daysOwed, matchesSearch, searchKey, sortCustomers } from './customers'
import { listItem } from './test/mockApi'

describe('searchKey', () => {
  it('writes Bangla script in English letters and irons out Banglish spellings', () => {
    expect(searchKey('রহিম')).toBe(searchKey('Rahim'))
    expect(searchKey('Rohim')).toBe(searchKey('rahim'))
    expect(searchKey('সালমা')).toBe(searchKey('Shalma'))
    expect(searchKey('আয়েশা')).toBe(searchKey('Ayesha'))
    expect(searchKey('Kareem')).toBe(searchKey('করিম'))
  })
})

describe('matchesSearch', () => {
  const rahim = listItem(1, 'Rahim', 300, { note: 'Bazar road', phone: '01711-000001' })
  const ayesha = listItem(2, 'আয়েশা', 750)

  it.each([
    ['rahim', rahim],
    ['RAH', rahim],
    ['rohim', rahim],
    ['রহিম', rahim],
    ['রহি', rahim],
    ['bazar', rahim],
    ['01711', rahim],
    ['০১৭১১ ০০০০০১', rahim],
    ['ayesha', ayesha],
    ['আয়ে', ayesha],
    ['', rahim],
  ])('%j finds the customer', (query, who) => {
    expect(matchesSearch(who, query)).toBe(true)
  })

  it.each([
    ['salma', rahim],
    ['karim', rahim],
    ['01811', rahim],
    ['rahim', ayesha],
  ])('%j does not', (query, who) => {
    expect(matchesSearch(who, query)).toBe(false)
  })
})

describe('sortCustomers', () => {
  const customers = [
    listItem(1, 'Rahim', 300, { owedSince: '2026-09-10T00:00:00Z' }),
    listItem(2, 'Salma', 0),
    listItem(3, 'Jasim', 1500, { owedSince: '2026-10-20T00:00:00Z' }),
    listItem(4, 'Abul', -200),
    listItem(5, 'আয়েশা', 750, { owedSince: '2026-08-01T00:00:00Z' }),
    listItem(6, 'Nasima', 300, { owedSince: '2026-10-01T00:00:00Z' }),
  ]
  const names = (sorted: typeof customers) => sorted.map((c) => c.name)

  it('most owed first, ties by name, the settled at the end by name', () => {
    expect(names(sortCustomers(customers, 'most-owed'))).toEqual([
      'Jasim',
      'আয়েশা',
      'Nasima',
      'Rahim',
      'Abul',
      'Salma',
    ])
  })

  it('oldest unpaid baki first, the settled at the end by name', () => {
    expect(names(sortCustomers(customers, 'oldest-owed'))).toEqual([
      'আয়েশা',
      'Rahim',
      'Nasima',
      'Jasim',
      'Abul',
      'Salma',
    ])
  })

  it('by name, English and Bangla names together', () => {
    expect(names(sortCustomers(customers, 'name'))).toEqual(['Abul', 'Jasim', 'Nasima', 'Rahim', 'Salma', 'আয়েশা'])
  })

  it('does not change the list it was given', () => {
    const before = names(customers)
    sortCustomers(customers, 'name')
    expect(names(customers)).toEqual(before)
  })
})

describe('daysOwed', () => {
  it('counts whole days since the oldest unpaid credit', () => {
    const now = new Date('2026-10-27T10:00:00Z')
    expect(daysOwed(listItem(1, 'R', 100, { owedSince: '2026-09-27T09:00:00Z' }), now)).toBe(30)
    expect(daysOwed(listItem(1, 'R', 100, { owedSince: '2026-10-27T09:00:00Z' }), now)).toBe(0)
    expect(daysOwed(listItem(1, 'R', 0), now)).toBeNull()
  })
})
