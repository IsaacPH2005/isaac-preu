import type { DocumentItem } from '~/types'

const POLL_MS = 3000

/**
 * Estado global de documentos con polling cada 3 s mientras haya alguno
 * pendiente o en proceso. Emite `onDocumentFinished` cuando uno termina.
 */
export function useDocuments() {
  const documents = useState<DocumentItem[]>('documents', () => [])
  const loaded = useState('documents-loaded', () => false)
  const error = useState<string | null>('documents-error', () => null)
  const finishedTick = useState('documents-finished-tick', () => 0)
  const progressTick = useState('documents-progress-tick', () => 0)

  const active = computed(() =>
    documents.value.filter((d) => d.status === 'pending' || d.status === 'processing'),
  )

  async function refresh() {
    try {
      const prev = new Map(documents.value.map((d) => [d.id, d]))
      const next = await $fetch<DocumentItem[]>('/api/documents')
      let finished = false
      let progressed = false
      for (const d of next) {
        const before = prev.get(d.id)
        const wasActive = before && (before.status === 'pending' || before.status === 'processing')
        if (wasActive && (d.status === 'completed' || d.status === 'failed')) finished = true
        if (before && before.question_count !== d.question_count) progressed = true
      }
      if (prev.size && next.length !== prev.size) finished = true
      documents.value = next
      error.value = null
      if (finished) finishedTick.value++
      if (progressed) progressTick.value++
    } catch (e: any) {
      error.value = e?.data?.detail || e?.message || 'No se pudo conectar con el servidor'
    } finally {
      loaded.value = true
    }
  }

  return { documents, active, loaded, error, finishedTick, progressTick, refresh }
}

/** Inicia el polling (llamar una sola vez, desde la página principal). */
export function useDocumentsPolling() {
  const { refresh, active } = useDocuments()
  let timer: ReturnType<typeof setTimeout> | null = null
  let stopped = false

  async function loop() {
    await refresh()
    if (stopped) return
    // Si no hay documentos activos, sondea mucho más lento (por si se suben desde otra pestaña).
    timer = setTimeout(loop, active.value.length ? POLL_MS : POLL_MS * 10)
  }

  function kick() {
    if (timer) clearTimeout(timer)
    loop()
  }

  onMounted(loop)
  onBeforeUnmount(() => {
    stopped = true
    if (timer) clearTimeout(timer)
  })

  return { kick }
}
