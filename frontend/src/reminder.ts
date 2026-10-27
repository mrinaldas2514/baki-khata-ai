/** WhatsApp's click-to-chat link: opens the chat with the message typed in. It never sends by itself. */
export function whatsappLink(number: string, message: string): string {
  // A half-typed emoji (a lone surrogate) would make encodeURIComponent throw.
  const text = message.replace(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g, '\uFFFD')
  return `https://wa.me/${number.replace(/\D/g, '')}?text=${encodeURIComponent(text)}`
}

/** Copy text to the clipboard. Falls back to the old way on browsers without the Clipboard API. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Not allowed (e.g. not https): try the old way below.
  }
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.append(area)
  area.select()
  try {
    return document.execCommand?.('copy') ?? false
  } catch {
    return false
  } finally {
    area.remove()
  }
}
