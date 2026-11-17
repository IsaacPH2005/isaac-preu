<script setup lang="ts">
const { filters, reset, activeCount } = useSearchFilters()
const { options } = useFilterOptions()
const { documents } = useDocuments()

const topicQuery = ref('')

const subjects = computed(() => options.value?.subjects ?? [])
const total = computed(() => options.value?.total ?? 0)

const topics = computed(() => {
  const all = options.value?.topics ?? {}
  let list: { topic: string; count: number; subject: string }[]
  if (filters.value.subject) {
    list = (all[filters.value.subject] ?? []).map((t) => ({ ...t, subject: filters.value.subject }))
  } else {
    // Sin materia elegida: fusiona temas de todas las materias
    list = Object.entries(all).flatMap(([subject, ts]) => ts.map((t) => ({ ...t, subject })))
    list.sort((a, b) => b.count - a.count || a.topic.localeCompare(b.topic))
  }
  const q = normalize(topicQuery.value)
  return q ? list.filter((t) => normalize(t.topic).includes(q)) : list
})

const TOPIC_LIMIT = 40
const showAllTopics = ref(false)
const visibleTopics = computed(() => (showAllTopics.value ? topics.value : topics.value.slice(0, TOPIC_LIMIT)))

function normalize(s: string) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

function selectSubject(subject: string) {
  filters.value.subject = filters.value.subject === subject ? '' : subject
  filters.value.topic = ''
  topicQuery.value = ''
  showAllTopics.value = false
}

function selectTopic(topic: string, subject: string) {
  if (filters.value.topic === topic && (filters.value.subject === subject || !filters.value.subject)) {
    filters.value.topic = ''
    return
  }
  if (!filters.value.subject) filters.value.subject = subject
  filters.value.topic = topic
}

// ─── Examen ─────────────────────────────────────────────────────────
const examQuery = ref('')
const showAllExams = ref(false)
const EXAM_LIMIT = 8
const examTypes = computed(() => options.value?.exam_types ?? [])
const exams = computed(() => {
  const q = normalize(examQuery.value)
  const list = options.value?.exams ?? []
  return q ? list.filter((e) => normalize(`${e.exam} ${e.exam_type} ${e.exam_year ?? ''}`).includes(q)) : list
})
const visibleExams = computed(() =>
  showAllExams.value || examQuery.value ? exams.value : exams.value.slice(0, EXAM_LIMIT),
)

function selectExamType(t: string) {
  filters.value.examType = filters.value.examType === t ? '' : t
  filters.value.exam = ''
}
function selectExam(e: string) {
  filters.value.exam = filters.value.exam === e ? '' : e
}

// ─── Página del libro: "120" o "100-120" ────────────────────────────
const pageInput = ref('')
watch(
  () => [filters.value.pageFrom, filters.value.pageTo] as const,
  ([a, b]) => {
    pageInput.value = !a && !b ? '' : a === b ? String(a) : `${a ?? ''}-${b ?? ''}`
  },
  { immediate: true },
)
function applyPages() {
  const raw = pageInput.value.replace(/\s+/g, '')
  const m = raw.match(/^(\d+)?(?:[-–](\d+)?)?$/)
  if (!raw || !m || (!m[1] && !m[2])) {
    filters.value.pageFrom = null
    filters.value.pageTo = null
    pageInput.value = ''
    return
  }
  const from = m[1] ? Number(m[1]) : null
  const to = /[-–]/.test(raw) ? (m[2] ? Number(m[2]) : null) : from
  const swap = from != null && to != null && from > to
  filters.value.pageFrom = swap ? to : from
  filters.value.pageTo = swap ? from : to
}
function stepPage(delta: number) {
  const cur = filters.value.pageFrom ?? (delta > 0 ? (options.value?.page_min ?? 1) - 1 : 2)
  const next = Math.max(1, cur + delta)
  filters.value.pageFrom = next
  filters.value.pageTo = next
}

// ─── Dificultad y respuestas ────────────────────────────────────────
const DIFFICULTY = [
  { value: 1, label: 'Fácil' },
  { value: 2, label: 'Medio' },
  { value: 3, label: 'Difícil' },
  { value: 4, label: 'Experto' },
]
const difficultyCounts = computed<Record<number, number>>(() =>
  Object.fromEntries((options.value?.difficulties ?? []).map((d) => [d.difficulty, d.count])),
)
function selectDifficulty(d: number) {
  filters.value.difficulty = filters.value.difficulty === d ? null : d
}
const { show: showAnswers, set: setShowAnswers } = useShowAnswers()
const showAnswersModel = computed({ get: () => showAnswers.value, set: setShowAnswers })

const documentModel = computed({
  get: () => (filters.value.documentId == null ? '' : String(filters.value.documentId)),
  set: (v: string) => {
    filters.value.documentId = v ? Number(v) : null
    filters.value.subject = ''
    filters.value.topic = ''
  },
})
</script>

<template>
  <div class="space-y-7">
    <div class="flex items-center justify-between">
      <span class="font-serif text-xl italic">Filtros</span>
      <button v-if="activeCount" class="text-xs font-medium text-accent-700 hover:underline" @click="reset">
        Limpiar todo
      </button>
    </div>

    <!-- Documento -->
    <section>
      <h3 class="panel-title">Documento</h3>
      <select v-model="documentModel" class="input cursor-pointer pr-8">
        <option value="">Todos los documentos</option>
        <option v-for="d in documents" :key="d.id" :value="String(d.id)">
          {{ d.filename }} ({{ d.question_count }})
        </option>
      </select>
    </section>

    <!-- Examen -->
    <section v-if="examTypes.length || exams.length">
      <h3 class="panel-title">Examen</h3>
      <div class="flex flex-wrap gap-1.5">
        <button
          class="pill px-3 py-1.5 text-[13px] transition"
          :class="!filters.examType ? 'bg-ink text-white' : 'bg-white text-ink-soft ring-1 ring-ink/10 hover:ring-ink/25'"
          @click="selectExamType('')"
        >
          Todos
        </button>
        <button
          v-for="t in examTypes"
          :key="t.exam_type"
          class="pill px-3 py-1.5 text-[13px] transition"
          :class="
            filters.examType === t.exam_type
              ? 'bg-accent-600 text-white'
              : 'bg-white text-ink-soft ring-1 ring-ink/10 hover:ring-ink/25'
          "
          @click="selectExamType(t.exam_type)"
        >
          {{ t.exam_type }}
          <span class="font-mono text-[11px] opacity-70">{{ t.count }}</span>
        </button>
      </div>

      <div v-if="exams.length > 4 || examQuery" class="relative mb-2 mt-3">
        <AppIcon name="search" :size="14" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input v-model="examQuery" type="search" placeholder="Buscar examen: 2012, parcial, modelo…" class="input py-1.5 pl-8 text-[13px]" />
      </div>
      <ul class="-mx-1 mt-2 max-h-[38vh] space-y-px overflow-y-auto pr-1 scrollbar-thin">
        <li v-for="e in visibleExams" :key="e.exam">
          <button
            class="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition"
            :class="filters.exam === e.exam ? 'bg-accent-600 text-white' : 'text-ink-soft hover:bg-ink/5 hover:text-ink'"
            :title="e.exam"
            @click="selectExam(e.exam)"
          >
            <span class="min-w-0 flex-1">
              <span class="block truncate">{{ e.exam }}</span>
              <span class="block text-[11px] opacity-70">
                {{ e.exam_type }} · pág. {{ e.first_page }}{{ e.last_page !== e.first_page ? `–${e.last_page}` : '' }}
              </span>
            </span>
            <span class="font-mono text-[11px] opacity-60">{{ e.count }}</span>
          </button>
        </li>
      </ul>
      <button
        v-if="!examQuery && exams.length > EXAM_LIMIT"
        class="mt-2 text-xs font-medium text-accent-700 hover:underline"
        @click="showAllExams = !showAllExams"
      >
        {{ showAllExams ? 'Mostrar menos' : `Ver los ${exams.length} exámenes` }}
      </button>
      <p v-if="examQuery && !exams.length" class="text-xs text-ink-muted">Ningún examen coincide.</p>
    </section>

    <!-- Página del libro -->
    <section>
      <h3 class="panel-title flex items-center justify-between">
        <span>Página del libro</span>
        <span v-if="options?.page_max" class="font-mono normal-case tracking-normal">
          {{ options.page_min }}–{{ options.page_max }}
        </span>
      </h3>
      <div class="flex items-center gap-1.5">
        <button class="btn-ghost px-2.5 py-1.5" aria-label="Página anterior" @click="stepPage(-1)">‹</button>
        <input
          v-model="pageInput"
          type="text"
          inputmode="numeric"
          placeholder="Ej. 120 o 100-120"
          class="input py-1.5 text-center text-[13px]"
          @keydown.enter="applyPages"
          @blur="applyPages"
        />
        <button class="btn-ghost px-2.5 py-1.5" aria-label="Página siguiente" @click="stepPage(1)">›</button>
      </div>
      <p class="mt-1.5 text-[11px] text-ink-muted">Número impreso en la hoja (el mismo de la clave de respuestas).</p>
    </section>

    <!-- Materia -->
    <section>
      <h3 class="panel-title">Materia</h3>
      <div class="flex flex-wrap gap-1.5">
        <button
          class="pill px-3 py-1.5 text-[13px] transition"
          :class="!filters.subject ? 'bg-ink text-white' : 'bg-white text-ink-soft ring-1 ring-ink/10 hover:ring-ink/25'"
          @click="selectSubject('')"
        >
          Todas
          <span class="font-mono text-[11px] opacity-70">{{ total }}</span>
        </button>
        <button
          v-for="s in subjects"
          :key="s.subject"
          class="pill px-3 py-1.5 text-[13px] transition"
          :class="
            filters.subject === s.subject
              ? subjectTone(s.subject).active
              : 'bg-white text-ink-soft ring-1 ring-ink/10 hover:ring-ink/25'
          "
          @click="selectSubject(s.subject)"
        >
          <span
            v-if="filters.subject !== s.subject"
            class="h-1.5 w-1.5 rounded-full"
            :class="subjectTone(s.subject).dot"
          />
          {{ subjectLabel(s.subject) }}
          <span class="font-mono text-[11px] opacity-70">{{ s.count }}</span>
        </button>
      </div>
      <p v-if="!subjects.length" class="text-xs text-ink-muted">Sin preguntas todavía.</p>
    </section>

    <!-- Tema -->
    <section>
      <h3 class="panel-title flex items-center justify-between">
        <span>Tema{{ filters.subject ? ` · ${subjectLabel(filters.subject)}` : '' }}</span>
        <span class="font-mono normal-case tracking-normal">{{ topics.length }}</span>
      </h3>
      <div v-if="(options?.topics && Object.keys(options.topics).length) || topicQuery" class="relative mb-2">
        <AppIcon name="search" :size="14" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input v-model="topicQuery" type="search" placeholder="Buscar tema…" class="input py-1.5 pl-8 text-[13px]" />
      </div>
      <ul class="-mx-1 max-h-[42vh] space-y-px overflow-y-auto pr-1 scrollbar-thin">
        <li v-for="t in visibleTopics" :key="t.subject + '|' + t.topic">
          <button
            class="group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition"
            :class="
              filters.topic === t.topic && (!filters.subject || filters.subject === t.subject)
                ? 'bg-accent-600 text-white'
                : 'text-ink-soft hover:bg-ink/5 hover:text-ink'
            "
            @click="selectTopic(t.topic, t.subject)"
          >
            <span v-if="!filters.subject" class="h-1.5 w-1.5 shrink-0 rounded-full" :class="subjectTone(t.subject).dot" />
            <span class="min-w-0 flex-1 truncate">{{ t.topic }}</span>
            <span class="font-mono text-[11px] opacity-60">{{ t.count }}</span>
          </button>
        </li>
      </ul>
      <button
        v-if="topics.length > TOPIC_LIMIT"
        class="mt-2 text-xs font-medium text-accent-700 hover:underline"
        @click="showAllTopics = !showAllTopics"
      >
        {{ showAllTopics ? 'Mostrar menos' : `Ver los ${topics.length} temas` }}
      </button>
      <p v-if="!topics.length" class="text-xs text-ink-muted">
        {{ topicQuery ? 'Ningún tema coincide.' : 'No hay temas para mostrar.' }}
      </p>
    </section>

    <!-- Dificultad -->
    <section v-if="options?.difficulties?.length">
      <h3 class="panel-title">Dificultad</h3>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="d in DIFFICULTY"
          :key="d.value"
          class="pill px-3 py-1.5 text-[13px] transition disabled:opacity-40"
          :class="
            filters.difficulty === d.value
              ? 'bg-accent-600 text-white'
              : 'bg-white text-ink-soft ring-1 ring-ink/10 hover:ring-ink/25'
          "
          :disabled="!difficultyCounts[d.value] && filters.difficulty !== d.value"
          @click="selectDifficulty(d.value)"
        >
          <span class="text-[11px] tracking-tighter">{{ '★'.repeat(d.value) }}</span>
          {{ d.label }}
          <span class="font-mono text-[11px] opacity-70">{{ difficultyCounts[d.value] ?? 0 }}</span>
        </button>
      </div>
    </section>

    <!-- Respuestas -->
    <section v-if="options?.answered_count" class="space-y-2">
      <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-ink/10 bg-white px-3 py-2.5">
        <span class="flex items-center gap-2 text-[13px] text-ink-soft">
          <AppIcon name="check" :size="16" />
          Solo con respuesta oficial
          <span class="font-mono text-[11px] text-ink-muted">{{ options.answered_count }}</span>
        </span>
        <span class="relative inline-flex">
          <input v-model="filters.hasAnswer" type="checkbox" class="peer sr-only" />
          <span class="h-5 w-9 rounded-full bg-ink/15 transition peer-checked:bg-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-500/40" />
          <span class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4" />
        </span>
      </label>
      <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-ink/10 bg-white px-3 py-2.5">
        <span class="flex items-center gap-2 text-[13px] text-ink-soft">
          <AppIcon name="book" :size="16" />
          Mostrar todas las respuestas
        </span>
        <span class="relative inline-flex">
          <input v-model="showAnswersModel" type="checkbox" class="peer sr-only" />
          <span class="h-5 w-9 rounded-full bg-ink/15 transition peer-checked:bg-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-500/40" />
          <span class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4" />
        </span>
      </label>
    </section>

    <!-- Diagramas -->
    <section>
      <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-ink/10 bg-white px-3 py-2.5">
        <span class="flex items-center gap-2 text-[13px] text-ink-soft">
          <AppIcon name="chart" :size="16" />
          Solo con gráficos/diagramas
          <span v-if="options" class="font-mono text-[11px] text-ink-muted">{{ options.diagram_count }}</span>
        </span>
        <span class="relative inline-flex">
          <input v-model="filters.hasDiagram" type="checkbox" class="peer sr-only" />
          <span class="h-5 w-9 rounded-full bg-ink/15 transition peer-checked:bg-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-500/40" />
          <span class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4" />
        </span>
      </label>
      <p v-if="filters.hasDiagram" class="mt-1.5 flex items-start gap-1.5 px-1 text-[11px] leading-snug text-amber-800">
        <AppIcon name="alert" :size="12" class="mt-0.5 shrink-0" />
        Las preguntas con gráficos son las que más errores de transcripción tienen: revísalas en la página original.
      </p>
    </section>
  </div>
</template>
