export interface Toast {
  id: number
  message: string
  tone: 'success' | 'error' | 'info'
}

let nextId = 1

export function useToast() {
  const toasts = useState<Toast[]>('toasts', () => [])

  function push(message: string, tone: Toast['tone'] = 'info', ms = 2600) {
    const id = nextId++
    toasts.value = [...toasts.value, { id, message, tone }]
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, ms)
  }

  return { toasts, push }
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* recurre al método alternativo */
  }
  // Alternativa para contextos no seguros (p. ej. acceso por IP de la red local)
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(ta)
  return ok
}
