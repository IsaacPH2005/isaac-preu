<script setup lang="ts">
import type { Question } from '~/types'

const props = defineProps<{ question: Question }>()
const emit = defineEmits<{ viewPage: [q: Question]; filterTopic: [q: Question] }>()
const { push } = useToast()

const copied = ref(false)
const tone = computed(() => subjectTone(props.question.subject))

async function copy() {
  const ok = await copyToClipboard(questionToPlainText(props.question))
  if (ok) {
    copied.value = true
    setTimeout(() => (copied.value = false), 1600)
  } else {
    push('No se pudo copiar', 'error')
  }
}

// Separa "a) texto" en letra + contenido para alinear las alternativas.
const parsedOptions = computed(() =>
  props.question.options.map((opt) => {
    const m = opt.match(/^\s*\(?([A-Ea-e])[\).:]\s*(.*)$/s)
    return m ? { letter: m[1].toLowerCase(), text: m[2] } : { letter: '', text: opt }
  }),
)
</script>

<template>
  <article class="group rounded-xl border border-ink/[0.08] bg-white p-5 shadow-card transition hover:border-ink/15 sm:p-6">
    <!-- Badges -->
    <div class="flex flex-wrap items-center gap-1.5">
      <span class="pill" :class="tone.pill">{{ subjectLabel(question.subject) }}</span>
      <button
        class="pill max-w-full bg-paper text-ink-soft ring-1 ring-ink/10 transition hover:ring-ink/25"
        :title="`Filtrar por «${question.topic}»`"
        @click="emit('filterTopic', question)"
      >
        <span class="truncate">{{ question.topic }}</span>
      </button>
      <span v-if="question.has_diagram" class="pill bg-amber-50 text-amber-800 ring-1 ring-amber-200">
        <AppIcon name="chart" :size="12" /> Gráfico
      </span>
      <span class="ml-auto flex items-center gap-2 font-mono text-[11px] text-ink-muted">
        <span v-if="question.question_number">#{{ question.question_number }}</span>
        <span>Pág. {{ question.page_number }}</span>
      </span>
    </div>

    <!-- Enunciado -->
    <div class="mt-4 text-[15px] leading-relaxed text-ink">
      <span v-if="question.question_number" class="float-left mr-2 font-serif text-xl italic leading-6 text-accent-700">
        {{ question.question_number }}.
      </span>
      <MathText :content="question.statement" />
    </div>

    <!-- Aviso de figura -->
    <button
      v-if="question.has_diagram"
      class="mt-4 flex w-full items-center gap-3 rounded-lg border border-dashed border-amber-300 bg-amber-50/60 px-3 py-2.5 text-left text-xs text-amber-900 transition hover:bg-amber-50"
      @click="emit('viewPage', question)"
    >
      <AppIcon name="image" :size="18" />
      Esta pregunta incluye una figura. Ver la página original para el diagrama completo.
    </button>

    <!-- Alternativas -->
    <ol v-if="parsedOptions.length" class="mt-4 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
      <li v-for="(opt, i) in parsedOptions" :key="i" class="flex items-baseline gap-2 text-[14px] text-ink-soft">
        <span
          v-if="opt.letter"
          class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-paper font-mono text-[11px] font-medium text-ink-soft ring-1 ring-ink/10"
        >
          {{ opt.letter }}
        </span>
        <MathText :content="opt.text" tag="span" class="min-w-0" />
      </li>
    </ol>

    <!-- Acciones -->
    <div class="mt-5 flex flex-wrap items-center gap-2 border-t border-ink/[0.06] pt-4">
      <button class="btn-outline py-1.5 text-[13px]" @click="emit('viewPage', question)">
        <AppIcon name="image" :size="15" /> Ver página original
      </button>
      <button class="btn-ghost py-1.5 text-[13px]" @click="copy">
        <AppIcon :name="copied ? 'check' : 'copy'" :size="15" :class="copied ? 'text-accent-600' : ''" />
        {{ copied ? 'Copiado' : 'Copiar pregunta' }}
      </button>
      <span class="ml-auto hidden max-w-[40%] truncate text-[11px] text-ink-muted sm:inline" :title="question.document_filename">
        {{ question.document_filename }}
      </span>
    </div>
  </article>
</template>
