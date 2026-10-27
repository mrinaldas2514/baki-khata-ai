import { ApiError } from './api/client'
import { strings } from './strings'
import type { VoiceErrorCode } from './voice/engines'

/** A friendly message for a failed POST /parse. Every one of these opens the manual form. */
export function parseErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError) || error.kind === 'network') return strings.errors.network
  switch (error.status) {
    case 404:
      return strings.errors.shopNotFound
    case 422:
      return strings.errors.notTransaction
    case 502:
      return strings.errors.aiFailed
    case 503:
      return strings.errors.aiUnavailable
    default:
      return strings.errors.aiFailed
  }
}

/** A friendly message for a failed save. */
export function saveErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError) || error.kind === 'network') return strings.errors.network
  switch (error.status) {
    case 404:
      return strings.errors.shopNotFound
    case 409:
      return strings.errors.duplicateCustomer
    case 422:
      return strings.errors.invalidData
    default:
      return strings.errors.saveFailed
  }
}

const VOICE_ERRORS: Record<VoiceErrorCode, string> = {
  permission: strings.errors.micPermission,
  insecure: strings.errors.micInsecure,
  'no-speech': strings.errors.micNoSpeech,
  'no-mic': strings.errors.micNotFound,
  network: strings.errors.micNetwork,
  language: strings.errors.micLanguage,
  'server-off': strings.errors.micServerOff,
  'too-long': strings.errors.micTooLong,
  failed: strings.errors.micFailed,
}

/** A friendly message for failed voice input. Typing always still works. */
export function voiceErrorMessage(code: VoiceErrorCode): string {
  return VOICE_ERRORS[code]
}
