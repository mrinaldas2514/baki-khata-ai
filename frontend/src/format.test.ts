import { describe, expect, it } from 'vitest'
import { describeBalance, formatTaka, formatWhen, moveToDate, parseAmount, toDateInput } from './format'

describe('formatTaka', () => {
  it('uses the taka sign and South Asian grouping', () => {
    expect(formatTaka(500)).toBe('৳500')
    expect(formatTaka(125000)).toBe('৳1,25,000')
    expect(formatTaka(-200)).toBe('৳200')
  })
})

describe('describeBalance', () => {
  it('says baki, agrim or clear', () => {
    expect(describeBalance(300)).toBe('Baki ৳300')
    expect(describeBalance(-200)).toBe('Agrim ৳200')
    expect(describeBalance(0)).toBe('Hisab clear')
  })
})

describe('parseAmount', () => {
  it.each([
    ['500', 500],
    [' 1,500 ', 1500],
    ['৳250', 250],
    ['৬০০', 600],
  ])('reads %j as %d', (text, value) => {
    expect(parseAmount(text)).toBe(value)
  })

  it.each(['', '0', '12.5', 'abc', '-5', '10000001'])('rejects %j', (text) => {
    expect(parseAmount(text)).toBeNull()
  })
})

describe('formatWhen', () => {
  const now = new Date(2026, 9, 27, 18, 0)
  it('says today, yesterday or days ago', () => {
    expect(formatWhen(new Date(2026, 9, 27, 9, 5).toISOString(), now)).toMatch(/^Aj 9:05/i)
    expect(formatWhen(new Date(2026, 9, 26, 23, 0).toISOString(), now)).toBe('Gotokal')
    expect(formatWhen(new Date(2026, 9, 22, 12, 0).toISOString(), now)).toBe('5 din age')
  })
})

describe('dates for editing an entry', () => {
  const now = new Date(2026, 9, 28, 15, 0) // 28 Oct 2026, 3 PM on this phone

  it('writes a moment as a local date for the date box', () => {
    expect(toDateInput(new Date(2026, 9, 5, 23, 30))).toBe('2026-10-05')
  })

  it('moves an entry to another day, keeping its time of day', () => {
    const moved = moveToDate('2026-10-20', new Date(2026, 9, 25, 9, 15), now)
    expect(moved).toEqual(new Date(2026, 9, 20, 9, 15))
  })

  it('never goes past now, and refuses future or impossible days', () => {
    expect(moveToDate('2026-10-28', new Date(2026, 9, 1, 20, 0), now)).toEqual(now)
    expect(moveToDate('2026-10-29', new Date(2026, 9, 1, 9, 0), now)).toBeNull()
    expect(moveToDate('2026-02-30', new Date(2026, 9, 1, 9, 0), now)).toBeNull()
    expect(moveToDate('', new Date(2026, 9, 1, 9, 0), now)).toBeNull()
  })
})
