import type { FiltersResponse, QuestionPage, SearchFilters } from '~/types'

const DEFAULT_FILTERS: SearchFilters = {
  q: '',
  subject: '',
  topic: '',
  documentId: null,
  hasDiagram: false,
  examType: '',
  exam: '',
  pageFrom: null,
  pageTo: null,
  difficulty: null,
  hasAnswer: false,
  page: 1,
  limit: 20,
}

export function useSearchFilters() {
  const filters = useState<SearchFilters>('search-filters', () => ({ ...DEFAULT_FILTERS }))

  function reset() {
    filters.value = { ...DEFAULT_FILTERS, limit: filters.value.limit }
  }

  const activeCount = computed(() => {
    const f = filters.value
    return [
      f.subject,
      f.topic,
      f.documentId,
      f.hasDiagram,
      f.q,
      f.examType,
      f.exam,
      f.pageFrom || f.pageTo,
      f.difficulty,
      f.hasAnswer,
    ].filter(Boolean).length
  })

  return { filters, reset, activeCount }
}

/** Parámetros compartidos por /api/questions y /api/filters. */
export function filterParams(f: SearchFilters) {
  return {
    subject: f.subject,
    topic: f.topic,
    document_id: f.documentId,
    has_diagram: f.hasDiagram || undefined,
    exam_type: f.examType,
    exam: f.exam,
    page_from: f.pageFrom,
    page_to: f.pageTo,
    difficulty: f.difficulty,
    has_answer: f.hasAnswer || undefined,
  }
}

/** Mostrar u ocultar las respuestas oficiales (se recuerda en este navegador). */
export function useShowAnswers() {
  const show = useState('show-answers', () => false)
  onMounted(() => {
    try {
      show.value = localStorage.getItem('bancopreu:show-answers') === '1'
    } catch {
      /* almacenamiento bloqueado */
    }
  })
  function set(v: boolean) {
    show.value = v
    try {
      localStorage.setItem('bancopreu:show-answers', v ? '1' : '0')
    } catch {
      /* almacenamiento bloqueado */
    }
  }
  return { show, set }
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
          ...filterParams(f),
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
        query: cleanQuery(filterParams(filters.value)),
      })
    } catch {
      /* el panel mantiene el último estado conocido */
    }
  }

  return { options, fetchFilters }
}
