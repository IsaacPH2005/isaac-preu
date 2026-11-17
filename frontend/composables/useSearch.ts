import type { FiltersResponse, QuestionPage, SearchFilters } from '~/types'

const DEFAULT_FILTERS: SearchFilters = {
  q: '',
  subject: '',
  topic: '',
  documentId: null,
  hasDiagram: false,
  page: 1,
  limit: 20,
}

export function useSearchFilters() {
  const filters = useState<SearchFilters>('search-filters', () => ({ ...DEFAULT_FILTERS }))

  function reset() {
    filters.value = { ...DEFAULT_FILTERS, limit: filters.value.limit }
  }

  const activeCount = computed(
    () =>
      [filters.value.subject, filters.value.topic, filters.value.documentId, filters.value.hasDiagram, filters.value.q].filter(
        Boolean,
      ).length,
  )

  return { filters, reset, activeCount }
}

function cleanQuery(obj: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== '' && v !== null && v !== undefined && v !== false),
  )
}

/** Resultados de /api/questions; ignora respuestas obsoletas si llegan desordenadas. */
export function useQuestionResults() {
  const { filters } = useSearchFilters()
  const result = useState<QuestionPage | null>('question-results', () => null)
  const loading = useState('question-loading', () => false)
  const error = useState<string | null>('question-error', () => null)
  let seq = 0

  async function fetchQuestions() {
    const id = ++seq
    loading.value = true
    try {
      const f = filters.value
      const data = await $fetch<QuestionPage>('/api/questions', {
        query: cleanQuery({
          q: f.q.trim(),
          subject: f.subject,
          topic: f.topic,
          document_id: f.documentId,
          has_diagram: f.hasDiagram || undefined,
          page: f.page,
          limit: f.limit,
        }),
      })
      if (id !== seq) return
      result.value = data
      error.value = null
    } catch (e: any) {
      if (id !== seq) return
      error.value = e?.data?.detail || e?.message || 'Error al buscar preguntas'
    } finally {
      if (id === seq) loading.value = false
    }
  }

  return { result, loading, error, fetchQuestions }
}

export function useFilterOptions() {
  const { filters } = useSearchFilters()
  const options = useState<FiltersResponse | null>('filter-options', () => null)

  async function fetchFilters() {
    try {
      options.value = await $fetch<FiltersResponse>('/api/filters', {
        query: cleanQuery({
          document_id: filters.value.documentId,
          has_diagram: filters.value.hasDiagram || undefined,
        }),
      })
    } catch {
      /* el panel mantiene el último estado conocido */
    }
  }

  return { options, fetchFilters }
}
