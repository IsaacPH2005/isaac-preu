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
    </section>
  </div>
</template>
