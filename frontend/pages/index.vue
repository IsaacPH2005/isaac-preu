<script setup lang="ts">
import type { Question } from '~/types'

const { filters } = useSearchFilters()
const { result, loading, error, fetchQuestions } = useQuestionResults()
const { options, fetchFilters } = useFilterOptions()
const { documents, loaded: docsLoaded, active, finishedTick, progressTick } = useDocuments()
const { kick } = useDocumentsPolling()
const { allowUploads, load: loadServerInfo } = useServerInfo()

const uploadOpen = ref(false)
const filtersOpen = ref(false)
const viewing = ref<Question | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const resultsTop = ref<HTMLElement | null>(null)

// ─── Búsqueda con debounce de 300 ms ────────────────────────────────
const qInput = ref(filters.value.q)
let debounce: ReturnType<typeof setTimeout> | null = null
watch(qInput, (v) => {
  if (debounce) clearTimeout(debounce)
  debounce = setTimeout(() => (filters.value.q = v), 300)
})
watch(
  () => filters.value.q,
  (v) => {
    if (v !== qInput.value) qInput.value = v
  },
)
function clearSearch() {
  qInput.value = ''
  filters.value.q = ''
  searchInput.value?.focus()
}

// ─── Disparadores de carga ──────────────────────────────────────────
const filterKey = computed(() => {
  const f = filters.value
  return JSON.stringify([f.q.trim(), f.subject, f.topic, f.documentId, f.hasDiagram])
})
watch(filterKey, () => {
  if (filters.value.page !== 1) filters.value.page = 1 // el watcher de página recarga
  else fetchQuestions()
})
watch(
  () => filters.value.page,
  () => {
    fetchQuestions()
    resultsTop.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  },
)
watch(
  () => [filters.value.documentId, filters.value.hasDiagram],
  () => fetchFilters(),
)
// Un documento terminó (o se eliminó): refresca todo.
watch(finishedTick, () => {
  fetchFilters()
  fetchQuestions()
})
// Mientras se procesa, los contadores crecen en vivo; los resultados se cargan si aún no había.
watch(progressTick, () => {
  fetchFilters()
  if (!result.value?.total) fetchQuestions()
})

onMounted(() => {
  loadServerInfo()
  fetchFilters()
  fetchQuestions()
  window.addEventListener('keydown', onGlobalKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKey))

function onGlobalKey(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName)
  if (e.key === '/' && !typing && !uploadOpen.value && !viewing.value) {
    e.preventDefault()
    searchInput.value?.focus()
  }
}

function onDocsChanged() {
  kick()
  fetchFilters()
  fetchQuestions()
}

function filterByTopic(q: Question) {
  filters.value.subject = q.subject
  filters.value.topic = q.topic
}

const total = computed(() => result.value?.total ?? 0)
const items = computed(() => result.value?.items ?? [])
const hasAnyQuestion = computed(() => (options.value?.total ?? 0) > 0 || total.value > 0)
const showEmptyLibrary = computed(() => docsLoaded.value && !documents.value.length)

const chips = computed(() => {
  const f = filters.value
  const out: { label: string; clear: () => void }[] = []
  if (f.documentId) {
    const d = documents.value.find((x) => x.id === f.documentId)
    out.push({ label: d?.filename ?? `Documento ${f.documentId}`, clear: () => (f.documentId = null) })
  }
  if (f.subject) out.push({ label: subjectLabel(f.subject), clear: () => ((f.subject = ''), (f.topic = '')) })
  if (f.topic) out.push({ label: f.topic, clear: () => (f.topic = '') })
  if (f.hasDiagram) out.push({ label: 'Con gráficos', clear: () => (f.hasDiagram = false) })
  return out
})

const suggestions = ['plano inclinado', 'Ruffini', 'moles', 'MRUV', 'ecuación cuadrática', 'mitosis']
</script>

<template>
  <div class="min-h-screen">
    <AppHeader @upload="uploadOpen = true" @toggle-filters="filtersOpen = !filtersOpen" />

    <div class="mx-auto grid max-w-[1440px] gap-8 px-4 py-6 sm:px-6 lg:grid-cols-[280px_minmax(0,1fr)] lg:py-8">
      <!-- Sidebar de filtros (escritorio) -->
      <aside class="hidden lg:block">
        <div class="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pb-8 pr-2 scrollbar-thin">
          <FilterSidebar />
        </div>
      </aside>

      <!-- Drawer de filtros (móvil) -->
      <Teleport to="body">
        <div v-if="filtersOpen" class="fixed inset-0 z-40 lg:hidden">
          <div class="absolute inset-0 animate-fade-in bg-ink/40" @click="filtersOpen = false" />
          <div class="absolute inset-y-0 left-0 w-[86%] max-w-sm overflow-y-auto bg-paper p-5 shadow-lift">
            <button class="btn-ghost absolute right-3 top-3 px-2" aria-label="Cerrar" @click="filtersOpen = false">
              <AppIcon name="x" />
            </button>
            <FilterSidebar />
          </div>
        </div>
      </Teleport>

      <main class="min-w-0">
        <!-- Barra de búsqueda -->
        <div ref="resultsTop" class="scroll-mt-24">
          <div class="relative">
            <AppIcon name="search" :size="20" class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              ref="searchInput"
              v-model="qInput"
              type="search"
              autocomplete="off"
              spellcheck="false"
              placeholder="Busca por palabras clave: plano inclinado, Ruffini, moles…"
              class="h-14 w-full rounded-xl border border-ink/10 bg-white pl-12 pr-24 text-base text-ink shadow-card placeholder:text-ink-muted focus:border-accent-500 focus:outline-none focus:ring-4 focus:ring-accent-500/15"
            />
            <div class="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
              <AppIcon v-if="loading" name="loader" :size="16" class="animate-spin text-ink-muted" />
              <button v-if="qInput" class="btn-ghost px-1.5 py-1" aria-label="Limpiar búsqueda" @click="clearSearch">
                <AppIcon name="x" :size="16" />
              </button>
              <kbd v-else class="hidden rounded border border-ink/15 px-1.5 font-mono text-[11px] text-ink-muted sm:inline">/</kbd>
            </div>
          </div>

          <div v-if="!qInput && hasAnyQuestion" class="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
            <span>Prueba:</span>
            <button
              v-for="s in suggestions"
              :key="s"
              class="rounded-full px-2 py-0.5 text-ink-soft ring-1 ring-ink/10 transition hover:bg-white hover:ring-ink/20"
              @click="qInput = s"
            >
              {{ s }}
            </button>
          </div>
        </div>

        <!-- Cabecera de resultados -->
        <div class="mt-6 flex flex-wrap items-center gap-2">
          <h1 class="mr-2 font-serif text-[26px] italic leading-none">
            <template v-if="result">{{ total.toLocaleString('es') }} pregunta{{ total === 1 ? '' : 's' }}</template>
            <template v-else>Preguntas</template>
          </h1>
          <span v-if="filters.q.trim()" class="text-xs text-ink-muted">ordenadas por relevancia</span>
          <button
            v-for="c in chips"
            :key="c.label"
            class="pill bg-white py-1 text-ink-soft ring-1 ring-ink/10 hover:ring-ink/25"
            @click="c.clear()"
          >
            {{ c.label }} <AppIcon name="x" :size="12" />
          </button>
        </div>

        <p v-if="error" class="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{{ error }}</p>

        <!-- Biblioteca vacía -->
        <div
          v-if="showEmptyLibrary"
          class="mt-6 flex flex-col items-center rounded-2xl border border-dashed border-ink/15 bg-white/60 px-6 py-16 text-center"
        >
          <span class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent-50 text-accent-600">
            <AppIcon name="book" :size="26" />
          </span>
          <h2 class="font-serif text-3xl italic">{{ allowUploads ? 'Tu banco está vacío' : 'Aún no hay preguntas' }}</h2>
          <p v-if="allowUploads" class="mt-2 max-w-md text-sm text-ink-soft">
            Sube un PDF con preguntas (Física, Química, Álgebra…). La IA extraerá cada pregunta con sus fórmulas,
            la clasificará por materia y tema, y podrás buscarlas al instante.
          </p>
          <p v-else class="mt-2 max-w-md text-sm text-ink-soft">El banco de preguntas se publicará pronto.</p>
          <button v-if="allowUploads" class="btn-primary mt-6" @click="uploadOpen = true">
            <AppIcon name="upload" :size="16" /> Subir mi primer PDF
          </button>
        </div>

        <!-- Esqueleto de carga -->
        <div v-else-if="loading && !result" class="mt-6 space-y-4">
          <div v-for="i in 3" :key="i" class="animate-pulse rounded-xl border border-ink/[0.06] bg-white p-6">
            <div class="flex gap-2">
              <div class="h-5 w-16 rounded-full bg-ink/10" />
              <div class="h-5 w-32 rounded-full bg-ink/5" />
            </div>
            <div class="mt-5 h-3 w-full rounded bg-ink/5" />
            <div class="mt-2 h-3 w-4/5 rounded bg-ink/5" />
            <div class="mt-5 grid grid-cols-2 gap-2">
              <div v-for="j in 4" :key="j" class="h-3 rounded bg-ink/5" />
            </div>
          </div>
        </div>

        <!-- Sin resultados -->
        <div v-else-if="result && !items.length" class="mt-6 rounded-2xl border border-ink/10 bg-white px-6 py-14 text-center">
          <template v-if="active.length && !hasAnyQuestion">
            <AppIcon name="loader" :size="26" class="mx-auto animate-spin text-accent-600" />
            <p class="mt-3 text-sm text-ink-soft">Extrayendo preguntas… aparecerán aquí en unos momentos.</p>
          </template>
          <template v-else>
            <p class="font-serif text-2xl italic">Sin coincidencias</p>
            <p class="mt-2 text-sm text-ink-muted">Prueba con otras palabras o quita algún filtro.</p>
          </template>
        </div>

        <!-- Resultados -->
        <div v-else class="mt-6 space-y-4 transition-opacity" :class="loading ? 'opacity-60' : ''">
          <QuestionCard
            v-for="q in items"
            :key="q.id"
            :question="q"
            @view-page="viewing = $event"
            @filter-topic="filterByTopic"
          />
        </div>

        <div v-if="result && result.pages > 1" class="mt-8">
          <AppPagination :page="filters.page" :pages="result.pages" @change="filters.page = $event" />
        </div>
      </main>
    </div>

    <AppFooter />

    <UploadModal v-if="allowUploads" :open="uploadOpen" @close="uploadOpen = false" @changed="onDocsChanged" />
    <PageViewer :question="viewing" @close="viewing = null" />
    <ToastHost />
  </div>
</template>
