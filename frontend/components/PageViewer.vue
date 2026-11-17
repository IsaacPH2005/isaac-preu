<script setup lang="ts">
import type { Question } from '~/types'

const props = defineProps<{ question: Question | null }>()
const emit = defineEmits<{ close: [] }>()

const zoom = ref(1) // 1 = ajustar al ancho
const loading = ref(true)
const failed = ref(false)

watch(
  () => props.question?.id,
  () => {
    zoom.value = 1
    loading.value = true
    failed.value = false
  },
)

function setZoom(delta: number) {
  zoom.value = Math.min(3, Math.max(0.5, +(zoom.value + delta).toFixed(2)))
}

function onKey(e: KeyboardEvent) {
  if (!props.question) return
  if (e.key === 'Escape') emit('close')
  if (e.key === '+' || e.key === '=') setZoom(0.25)
  if (e.key === '-') setZoom(-0.25)
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="question" class="fixed inset-0 z-50">
      <div class="absolute inset-0 animate-fade-in bg-ink/40 backdrop-blur-[2px]" @click="emit('close')" />

      <aside
        class="absolute inset-y-0 right-0 flex w-full max-w-3xl animate-slide-in flex-col bg-paper shadow-lift"
        role="dialog"
        aria-modal="true"
        aria-label="Página original"
      >
        <header class="flex items-center gap-3 border-b border-ink/[0.07] px-4 py-3">
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium">{{ question.document_filename }}</p>
            <p class="text-xs text-ink-muted">
              Página {{ question.page_number }}
              <template v-if="question.question_number"> · Pregunta #{{ question.question_number }}</template>
              · {{ subjectLabel(question.subject) }}
            </p>
          </div>
          <div class="flex items-center rounded-lg border border-ink/10 bg-white">
            <button class="btn-ghost rounded-r-none px-2 py-1.5" aria-label="Alejar" @click="setZoom(-0.25)">
              <AppIcon name="zoomOut" :size="16" />
            </button>
            <button class="min-w-[3.25rem] px-1 font-mono text-xs text-ink-soft" title="Ajustar al ancho" @click="zoom = 1">
              {{ Math.round(zoom * 100) }}%
            </button>
            <button class="btn-ghost rounded-l-none px-2 py-1.5" aria-label="Acercar" @click="setZoom(0.25)">
              <AppIcon name="zoomIn" :size="16" />
            </button>
          </div>
          <a v-if="question.pdf_url" :href="question.pdf_url" target="_blank" class="btn-ghost hidden px-2 sm:inline-flex" title="Abrir el PDF en esta página">
            <AppIcon name="external" :size="16" />
          </a>
          <button class="btn-ghost px-2" aria-label="Cerrar" @click="emit('close')"><AppIcon name="x" /></button>
        </header>

        <div class="relative flex-1 overflow-auto bg-paper-dark/60 p-4 scrollbar-thin">
          <div v-if="loading && !failed" class="absolute inset-0 flex items-center justify-center text-ink-muted">
            <AppIcon name="loader" :size="28" class="animate-spin" />
          </div>
          <div v-if="failed" class="flex h-full flex-col items-center justify-center gap-2 text-sm text-ink-muted">
            <AppIcon name="alert" :size="24" />
            No se pudo cargar la imagen de la página.
          </div>
          <img
            v-show="!failed"
            :key="question.page_image_url"
            :src="question.page_image_url"
            :alt="`Página ${question.page_number}`"
            class="mx-auto block max-w-none rounded bg-white shadow-card transition-[width] duration-150"
            :style="{ width: zoom * 100 + '%' }"
            @load="loading = false"
            @error="failed = true"
          />
        </div>
      </aside>
    </div>
  </Teleport>
</template>
