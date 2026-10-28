import { describe, expect, it } from 'vitest'
import { ApiError } from './api/client'
import { authErrorMessage, parseErrorMessage, saveErrorMessage, voiceErrorMessage } from './errors'
import { strings } from './strings'
import { serverErrorCode } from './voice/engines'

const tooMany = new ApiError('http', 429, 'Onek bar chesta hoyeche.', [], 42)

describe('too many tries (429)', () => {
  it('says how long to wait, in Banglish, wherever it happens', () => {
    expect(strings.errors.rateLimited(42)).toBe('Onek bar chesta hoyeche. 42 second por abar chesta korun.')
    expect(strings.errors.rateLimited(3600)).toBe('Onek bar chesta hoyeche. 60 minute por abar chesta korun.')
    expect(parseErrorMessage(tooMany)).toBe(strings.errors.rateLimited(42))
    expect(saveErrorMessage(tooMany)).toBe(strings.errors.rateLimited(42))
    expect(authErrorMessage(tooMany)).toBe(strings.errors.rateLimited(42))
    expect(voiceErrorMessage(serverErrorCode(tooMany))).toBe(strings.errors.micTooMany)
  })

  it('assumes a minute when the server did not say', () => {
    expect(parseErrorMessage(new ApiError('http', 429, 'x'))).toBe(strings.errors.rateLimited(60))
  })
})

describe('voice when AI is off', () => {
  it('a 403 from the server means server voice is off: the browser is used instead', () => {
    expect(serverErrorCode(new ApiError('http', 403, 'AI is turned off'))).toBe('server-off')
  })
})
