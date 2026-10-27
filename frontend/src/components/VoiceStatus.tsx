import { voiceErrorMessage } from '../errors'
import { strings } from '../strings'
import type { VoiceErrorCode } from '../voice/engines'
import type { VoiceState } from '../voice/useVoiceInput'
import { Alert } from './ui'

interface Props {
  state: VoiceState
  error: VoiceErrorCode | null
  /** The box holds a transcript the shopkeeper hasn't changed yet. */
  showCheckHint: boolean
  /** The box is empty, so explain how the mic works. */
  showHoldHint: boolean
}

/** One line under the entry box saying what the mic is doing, or what went wrong. */
export function VoiceStatus({ state, error, showCheckHint, showHoldHint }: Props) {
  if (state === 'error' && error) return <Alert tone="warning">{voiceErrorMessage(error)}</Alert>

  let message: string | null = null
  if (state === 'listening') message = strings.voice.listeningHint
  else if (state === 'processing') message = strings.voice.processingHint
  else if (showCheckHint) message = strings.voice.checkTranscript
  else if (showHoldHint) message = strings.voice.holdHint
  if (!message) return null

  return (
    <p role="status" className={`text-lg ${state === 'listening' ? 'font-semibold text-red-700' : 'text-stone-600'}`}>
      {message}
    </p>
  )
}
