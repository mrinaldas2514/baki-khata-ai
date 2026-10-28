/** The browser's rule-based parser gives exactly the Python parser's answers (rulesParity.json). */
import { describe, expect, it } from 'vitest'
import parity from './rulesParity.json'
import { cleanName, nameWords, normalizeNumbers, parseText } from './rules'

describe('same answers as the backend rules', () => {
  it.each(parity.cases.map((c) => [c.text, c] as const))('%s', (_text, c) => {
    expect(normalizeNumbers(c.text)).toBe(c.normalized)
    expect(parseText(c.text)).toEqual(c.parsed)
  })

  it('covers the whole evaluation set and more', () => {
    expect(parity.cases.length).toBeGreaterThan(200)
  })
})

describe('names', () => {
  it('drops honorifics, also joined ones', () => {
    expect(nameWords('Rahim bhai')).toEqual(['rahim'])
    expect(nameWords('rahimbhai')).toEqual(['rahim'])
    expect(nameWords('আয়েশা আপা')).toEqual(['আয়েশা'])
    expect(nameWords('Mama')).toEqual(['mama']) // a customer really called "Mama"
  })

  it('cleans a new customer name like the backend', () => {
    expect(cleanName('salma apa')).toBe('Salma')
    expect(cleanName('রহিম ভাই')).toBe('রহিম')
  })
})
