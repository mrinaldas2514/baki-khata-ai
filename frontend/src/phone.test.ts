import { describe, expect, it } from 'vitest'
import { formatPhone, normalizeMobile } from './phone'

describe('normalizeMobile', () => {
  it.each([
    ['01711000001', '+8801711000001'],
    ['01711-000001', '+8801711000001'],
    ['+880 1711-000001', '+8801711000001'],
    ['8801711000001', '+8801711000001'],
    ['008801711000001', '+8801711000001'],
    ['+91 98765 43210', '+919876543210'],
    ['919876543210', '+919876543210'],
    ['09876543210', '+919876543210'],
    ['98765 43210', '+919876543210'],
  ])('%s -> %s', (text, normalized) => {
    expect(normalizeMobile(text)).toBe(normalized)
  })

  it.each(['', '12345', '01211000001', '0171100000', '+915123456789', '+44 7700 900123', 'call me'])(
    'rejects %j',
    (text) => {
      expect(normalizeMobile(text)).toBeNull()
    },
  )
})

describe('formatPhone', () => {
  it('writes numbers the way people read them', () => {
    expect(formatPhone('+8801711000001')).toBe('01711-000001')
    expect(formatPhone('+919876543210')).toBe('+91 98765 43210')
    expect(formatPhone('01711-000001')).toBe('01711-000001') // saved before normalizing
  })
})
