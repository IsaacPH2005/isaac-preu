<script setup lang="ts">
import type { Solution } from '~/types'

const props = defineProps<{ questionId: number; officialAnswer: string }>()

const solution = ref<Solution | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let timer: ReturnType<typeof setTimeout> | null = null
let polls = 0
const MAX_POLLS = 120 // ~6 minutos

async function load() {
  try {
    solution.value = await $fetch<Solution>(`/api/questions/${props.questionId}/solution`)
    if (solution.value.status === 'none' && solution.value.can_generate) await generate()
    else schedule()
  } catch (e: any) {
    error.value = e?.data?.detail || 'No se pudo cargar la solución'
  } finally {
    loading.value = false
  }
}

async function generate(regenerate = false) {
  error.value = null
  polls = 0
  try {
    solution.value = await $fetch<Solution>(`/api/questions/${props.questionId}/solution`, {
      method: 'POST',
      query: regenerate ? { regenerate: true } : {},
    })
    schedule()
  } catch (e: any) {
    error.value = e?.data?.detail || 'No se pudo generar la solución'
  }
}

function schedule() {
  if (timer) clearTimeout(timer)
  if (solution.value?.status !== 'pending') return
  if (++polls > MAX_POLLS) {
    error.value = 'La IA está tardando demasiado. Inténtalo de nuevo más tarde.'
    return
  }
  timer = setTimeout(async () => {
    try {
      solution.value = await $fetch<Solution>(`/api/questions/${props.questionId}/solution`)
    } catch {
      /* reintenta en el siguiente ciclo */
    }
    schedule()
  }, 3000)
}

onMounted(load)
onBeforeUnmount(() => timer && clearTimeout(timer))

const s = computed(() => solution.value)
const disagrees = computed(
  () => s.value?.status === 'done' && !!props.officialAnswer && s.value.reaches_key === false,
)
</script>

<template>
  <div class="mt-4 rounded-lg border border-ink/10 bg-paper/60 px-4 py-3 text-[14px] text-ink">
    <div class="mb-2 flex items-center gap-2">
      <AppIcon name="book" :size="16" class="text-accent-600" />
      <span class="font-medium">Cómo resolverlo</span>
      <span v-if="s?.status === 'done' && s.confidence" class="pill bg-white text-[11px] text-ink-muted ring-1 ring-ink/10">
        confianza {{ s.confidence }}
      </span>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-[13px] text-ink-muted">
      <AppIcon name="loader" :size="14" class="animate-spin" /> Cargando…
    </div>

    <div v-else-if="error" class="text-[13px]">
      <p class="text-red-700">{{ error }}</p>
      <button v-if="solution?.can_generate" class="btn-outline mt-2 py-1 text-xs" @click="generate(true)">Reintentar</button>
    </div>

    <div v-else-if="s?.status === 'pending'" class="flex items-center gap-2 text-[13px] text-ink-soft">
      <AppIcon name="loader" :size="14" class="animate-spin text-accent-600" />
      La IA está resolviendo la pregunta… suele tardar menos de un minuto.
    </div>

    <div v-else-if="s?.status === 'failed'" class="text-[13px]">
      <p class="text-red-700">No se pudo generar la solución: {{ s.error }}</p>
      <button v-if="s.can_generate" class="btn-outline mt-2 py-1 text-xs" @click="generate(true)">Reintentar</button>
    </div>

    <p v-else-if="s?.status === 'none'" class="text-[13px] text-ink-muted">
      Todavía no hay una solución para esta pregunta.
    </p>

    <template v-else-if="s?.status === 'done'">
      <!-- Datos leídos de la figura -->
      <div v-if="s.figure_data?.length" class="mb-3 rounded-md bg-white px-3 py-2 ring-1 ring-ink/10">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Datos leídos de la figura</p>
        <ul class="mt-1 flex flex-wrap gap-1.5">
          <li v-for="(d, i) in s.figure_data" :key="i" class="rounded bg-paper px-1.5 py-0.5 text-[13px]">
            <MathText :content="d" tag="span" />
          </li>
        </ul>
        <p class="mt-1 text-[11px] text-ink-muted">Compáralos con la figura: si alguno está mal, la solución también.</p>
      </div>

      <!-- Estrategia -->
      <div class="rounded-md bg-accent-50 px-3 py-2">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-accent-700">Estrategia</p>
        <MathText :content="s.strategy" class="mt-0.5" />
      </div>

      <!-- Pasos -->
      <ol class="mt-3 space-y-2">
        <li v-for="(step, i) in s.steps" :key="i" class="flex gap-2.5">
          <span
            class="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white font-mono text-[11px] text-ink-soft ring-1 ring-ink/10"
          >
            {{ i + 1 }}
          </span>
          <MathText :content="step" class="min-w-0 flex-1" />
        </li>
      </ol>

      <!-- Tips -->
      <div v-if="s.shortcut || s.common_mistake" class="mt-3 grid gap-2 sm:grid-cols-2">
        <div v-if="s.shortcut" class="rounded-md bg-white px-3 py-2 ring-1 ring-ink/10">
          <p class="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Tip para el examen</p>
          <MathText :content="s.shortcut" class="mt-0.5 text-[13px]" />
        </div>
        <div v-if="s.common_mistake" class="rounded-md bg-white px-3 py-2 ring-1 ring-ink/10">
          <p class="text-[11px] font-semibold uppercase tracking-wide text-red-700">Error común</p>
          <MathText :content="s.common_mistake" class="mt-0.5 text-[13px]" />
        </div>
      </div>

      <p v-if="disagrees" class="mt-3 rounded-md bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
        Atención: el desarrollo de la IA no llega a la respuesta oficial ({{ officialAnswer }}).
        <template v-if="s.note">{{ s.note }}</template>
      </p>
      <p v-else-if="s.note" class="mt-3 text-[12px] text-amber-800">{{ s.note }}</p>

      <div class="mt-3 flex items-center justify-between gap-2 text-[11px] text-ink-muted">
        <span>Explicación generada por IA: revísala con criterio.</span>
        <button v-if="s.can_generate" class="hover:text-accent-700 hover:underline" @click="generate(true)">
          Generar de nuevo
        </button>
      </div>
    </template>
  </div>
</template>
