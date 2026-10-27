import { describe, expect, it } from 'vitest'
import { whatsappLink } from './reminder'

describe('whatsappLink', () => {
  it('prefills the message for the number, digits only', () => {
    expect(whatsappLink('880 1711-000001', 'Priyo Rahim,\n৳500 baki & dhonnobad')).toBe(
      'https://wa.me/8801711000001?text=Priyo%20Rahim%2C%0A%E0%A7%B3500%20baki%20%26%20dhonnobad',
    )
  })

  it('survives a half-typed emoji', () => {
    expect(whatsappLink('8801711000001', 'ok \ud83d')).toBe('https://wa.me/8801711000001?text=ok%20%EF%BF%BD')
  })
})
