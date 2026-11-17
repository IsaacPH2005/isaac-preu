<script setup lang="ts">
import type { Question } from '~/types'

const props = defineProps<{ question: Question }>()
const emit = defineEmits<{ viewPage: [q: Question]; filterTopic: [q: Question]; filterExam: [q: Question] }>()
const { push } = useToast()
const { show: showAnswersToggle } = useShowAnswers()
const { filters } = useSearchFilters()
const { solutionsEnabled } = useServerInfo()
// "Solo con respuesta oficial" también deja las respuestas a la vista
const showAllAnswers = computed(() => showAnswersToggle.value || filters.value.hasAnswer)

// Respuesta oficial: visible con el interruptor global o con "Ver respuesta" en esta tarjeta
const revealed = ref(false)
const hasAnswer = computed(() => !!props.question.answer)
const answerShown = computed(() => hasAnswer.value && (showAllAnswers.value || revealed.value))
const solutionOpen = ref(false)
const pagePreview = ref(false)
// El botón «Cómo resolverlo» está oculto por ahora: vuelve a `true` para mostrarlo de nuevo.
const SHOW_SOLUTIONS = false
const canShowSolution = computed(() => SHOW_SOLUTIONS && (props.question.has_solution || solutionsEnabled.value))
const answerLetters = computed(() => props.question.answer.toLowerCase().split('/').filter(Boolean))
const answerOptionText = computed(() => {
  if (answerLetters.value.length !== 1) return ''
  return parsedOptions.value.find((o) => o.letter === answerLetters.value[0])?.text ?? ''
})
const label = computed(() => props.question.question_label || (props.question.question_number ? String(props.question.question_number) : ''))
const DIFF_LABEL = ['', 'Fácil', 'Medio', 'Difícil', 'Experto']

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
      <span
        v-if="question.difficulty"
        class="pill bg-paper text-ink-soft ring-1 ring-ink/10"
        :title="`Dificultad sugerida: ${DIFF_LABEL[question.difficulty]}`"
      >
        <span class="text-[10px] tracking-tighter text-amber-600">{{ '★'.repeat(question.difficulty) }}</span>
        {{ DIFF_LABEL[question.difficulty] }}
      </span>
      <span class="ml-auto flex items-center gap-2 font-mono text-[11px] text-ink-muted">
        <span v-if="label">{{ label }}</span>
        <span>Pág. {{ question.page_number }}</span>
      </span>
    </div>
    <button
      v-if="question.exam"
      class="mt-2 block max-w-full truncate text-left text-[12px] text-ink-muted transition hover:text-accent-700 hover:underline"
      :title="`Ver solo «${question.exam}»`"
      @click="emit('filterExam', question)"
    >
      {{ question.exam }}<template v-if="question.exam_type"> · {{ question.exam_type }}</template>
    </button>

    <!-- Aviso: las preguntas con figura son las que más fallan al extraerse -->
    <p
      v-if="question.has_diagram"
      class="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] leading-snug text-amber-900"
    >
      <AppIcon name="alert" :size="14" class="mt-0.5 shrink-0" />
      <span>
        <strong class="font-semibold">Pregunta con figura:</strong> el enunciado, los datos del gráfico y las
        alternativas pueden estar mal transcritos. Compárala con la página original antes de usarla.
      </span>
    </p>

    <!-- Enunciado -->
    <div class="mt-4 text-[15px] leading-relaxed text-ink">
      <span v-if="label" class="float-left mr-2 font-serif text-xl italic leading-6 text-accent-700">
        {{ label }}.
      </span>
      <MathText :content="question.statement" />
    </div>

    <!-- Figuras recortadas del libro -->
    <div v-if="question.figure_urls?.length" class="mt-4 flex flex-wrap gap-3">
      <button
        v-for="(url, i) in question.figure_urls"
        :key="url"
        class="group/fig relative overflow-hidden rounded-lg border border-ink/10 bg-white p-1.5 transition hover:border-accent-500"
        :title="'Ampliar en la página original'"
        @click="emit('viewPage', question)"
      >
        <img
          :src="url"
          :alt="`Figura ${i + 1} de la pregunta ${label}`"
          loading="lazy"
          class="max-h-72 w-auto max-w-full object-contain"
        />
      </button>
    </div>

    <!-- Sin recorte (página escaneada): vista de la página dentro de la tarjeta -->
    <template v-else-if="question.has_diagram">
      <button
        class="mt-4 flex w-full items-center gap-3 rounded-lg border border-dashed border-amber-300 bg-amber-50/60 px-3 py-2.5 text-left text-xs text-amber-900 transition hover:bg-amber-50"
        :aria-expanded="pagePreview"
        @click="pagePreview = !pagePreview"
      >
        <AppIcon name="image" :size="18" />
        {{ pagePreview ? 'Ocultar la página' : 'Esta pregunta tiene una figura: ver la página aquí' }}
      </button>
      <button
        v-if="pagePreview"
        class="mt-2 block w-full overflow-hidden rounded-lg border border-ink/10 bg-white"
        title="Abrir en grande"
        @click="emit('viewPage', question)"
      >
        <img :src="question.page_image_url" :alt="`Página ${question.page_number}`" loading="lazy" class="w-full" />
      </button>
    </template>

    <!-- Alternativas -->
    <ol v-if="parsedOptions.length" class="mt-4 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
      <li
        v-for="(opt, i) in parsedOptions"
        :key="i"
        class="flex items-baseline gap-2 rounded-md text-[14px] transition"
        :class="answerShown && answerLetters.includes(opt.letter) ? '-mx-1.5 bg-accent-50 px-1.5 font-medium text-ink' : 'text-ink-soft'"
      >
        <span
          v-if="opt.letter"
          class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-medium ring-1"
          :class="
            answerShown && answerLetters.includes(opt.letter)
              ? 'bg-accent-600 text-white ring-accent-600'
              : 'bg-paper text-ink-soft ring-ink/10'
          "
        >
          {{ opt.letter }}
        </span>
        <MathText :content="opt.text" tag="span" class="min-w-0" />
      </li>
    </ol>

    <!-- Respuesta oficial -->
    <div
      v-if="answerShown"
      class="mt-4 rounded-lg border border-accent-200 bg-accent-50/60 px-3 py-2.5 text-[13px] text-ink"
    >
      <p class="flex flex-wrap items-baseline gap-x-1.5">
        <span class="font-medium text-accent-700">Respuesta oficial:</span>
        <span class="font-mono font-semibold">{{ question.answer.split('/').join(' o ') }})</span>
        <MathText v-if="question.answer_detail" :content="question.answer_detail" tag="span" />
        <MathText v-else-if="answerOptionText" :content="answerOptionText" tag="span" class="text-ink-soft" />
      </p>
      <p v-if="question.key_note" class="mt-1 text-[12px] text-amber-800">{{ question.key_note }}</p>
    </div>

    <!-- Solución y estrategia (IA) -->
    <SolutionPanel v-if="SHOW_SOLUTIONS && solutionOpen" :question-id="question.id" :official-answer="question.answer" />

    <!-- Acciones -->
    <div class="mt-5 flex flex-wrap items-center gap-2 border-t border-ink/[0.06] pt-4">
      <button
        v-if="hasAnswer && !showAllAnswers"
        class="btn-outline py-1.5 text-[13px]"
        :aria-expanded="revealed"
        @click="revealed = !revealed"
      >
        <AppIcon name="check" :size="15" /> {{ revealed ? 'Ocultar respuesta' : 'Ver respuesta' }}
      </button>
      <button
        v-if="canShowSolution"
        class="btn-outline py-1.5 text-[13px]"
        :class="solutionOpen ? 'bg-accent-50 ring-accent-200' : ''"
        :aria-expanded="solutionOpen"
        @click="solutionOpen = !solutionOpen"
      >
        <AppIcon name="book" :size="15" /> {{ solutionOpen ? 'Ocultar solución' : 'Cómo resolverlo' }}
      </button>
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
