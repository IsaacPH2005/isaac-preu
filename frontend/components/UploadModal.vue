<script setup lang="ts">
import type { DocumentItem } from '~/types'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; changed: [] }>()

const { documents, error: docsError } = useDocuments()
const { push } = useToast()

interface UploadJob {
  key: string
  name: string
  size: number
  progress: number
  state: 'uploading' | 'done' | 'error'
  error?: string
}

const jobs = ref<UploadJob[]>([])
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
let dragDepth = 0

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function uploadFile(file: File) {
  const job: UploadJob = reactive({
    key: `${file.name}-${file.size}-${Date.now()}`,
    name: file.name,
    size: file.size,
    progress: 0,
    state: 'uploading',
  })
  jobs.value.unshift(job)

  const form = new FormData()
  form.append('file', file)
  const xhr = new XMLHttpRequest()
  xhr.open('POST', '/api/documents/upload')
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) job.progress = e.loaded / e.total
  }
  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      job.state = 'done'
      job.progress = 1
      push(`«${file.name}» subido. Extrayendo preguntas…`, 'success')
      emit('changed')
      setTimeout(() => (jobs.value = jobs.value.filter((j) => j.key !== job.key)), 2500)
    } else {
      job.state = 'error'
      try {
        job.error = JSON.parse(xhr.responseText).detail
      } catch {
        job.error = `Error ${xhr.status}`
      }
    }
  }
  xhr.onerror = () => {
    job.state = 'error'
    job.error = 'Error de red'
  }
  xhr.send(form)
}

// ─── Clave de respuestas (JSON/CSV) ─────────────────────────────────
const keyBusy = ref(false)
const keyResult = ref<{ key_rows: number; matched_questions: number; unmatched_key_rows: number; unmatched: string[] } | null>(null)
const keyRows = ref<number | null>(null)

async function loadKeySummary() {
  try {
    keyRows.value = (await $fetch<{ rows: number }>('/api/answer-key')).rows
  } catch {
    keyRows.value = null
  }
}
watch(
  () => props.open,
  (o) => {
    if (o) loadKeySummary()
  },
  { immediate: true },
)

async function onPickKey(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  keyBusy.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    keyResult.value = await $fetch('/api/answer-key', { method: 'POST', body: form })
    keyRows.value = keyResult.value?.key_rows ?? null
    push(`Clave aplicada: ${keyResult.value?.matched_questions} preguntas con respuesta`, 'success')
    emit('changed')
  } catch (err: any) {
    push(err?.data?.detail || 'No se pudo cargar la clave', 'error')
  } finally {
    keyBusy.value = false
  }
}

function handleFiles(list: FileList | null | undefined) {
  if (!list) return
  const files = Array.from(list)
  const pdfs = files.filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))
  if (pdfs.length < files.length) push('Solo se aceptan archivos PDF', 'error')
  pdfs.forEach(uploadFile)
}

function onDrop(e: DragEvent) {
  dragDepth = 0
  dragging.value = false
  handleFiles(e.dataTransfer?.files)
}
function onDragEnter() {
  dragDepth++
  dragging.value = true
}
function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1)
  if (!dragDepth) dragging.value = false
}
function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  handleFiles(input.files)
  input.value = ''
}

async function removeDoc(doc: DocumentItem) {
  if (!confirm(`¿Eliminar «${doc.filename}» y sus ${doc.question_count} preguntas?`)) return
  try {
    await $fetch(`/api/documents/${doc.id}`, { method: 'DELETE' })
    push('Documento eliminado', 'info')
    emit('changed')
  } catch (e: any) {
    push(e?.data?.detail || 'No se pudo eliminar', 'error')
  }
}

function canResume(doc: DocumentItem) {
  return doc.status === 'failed' && doc.processed_pages > 0 && doc.processed_pages < doc.total_pages
}

async function reprocess(doc: DocumentItem, resume = false) {
  if (!resume && doc.question_count && !confirm(`Se volverán a extraer las ${doc.total_pages} páginas de «${doc.filename}». ¿Continuar?`)) return
  try {
    await $fetch(`/api/documents/${doc.id}/reprocess`, { method: 'POST', query: resume ? { resume: true } : {} })
    push(resume ? `Reanudando desde la página ${doc.processed_pages + 1}…` : 'Reprocesando documento…', 'info')
    emit('changed')
  } catch (e: any) {
    push(e?.data?.detail || 'No se pudo reprocesar', 'error')
  }
}

const statusLabel: Record<string, string> = {
  pending: 'En cola',
  processing: 'Procesando',
  completed: 'Completado',
  failed: 'Error',
}
const statusClass: Record<string, string> = {
  pending: 'bg-stone-100 text-stone-700',
  processing: 'bg-accent-50 text-accent-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.open) emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8">
      <div class="fixed inset-0 animate-fade-in bg-ink/40 backdrop-blur-[2px]" @click="emit('close')" />

      <div
        class="relative w-full max-w-2xl animate-fade-in rounded-2xl bg-paper shadow-lift ring-1 ring-ink/10"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
      >
        <div class="flex items-center justify-between border-b border-ink/[0.07] px-5 py-4">
          <div>
            <h2 id="upload-title" class="font-serif text-2xl italic leading-none">Documentos</h2>
            <p class="mt-1 text-xs text-ink-muted">Sube bancos de preguntas en PDF; la IA extrae y clasifica cada pregunta.</p>
          </div>
          <button class="btn-ghost px-2" aria-label="Cerrar" @click="emit('close')"><AppIcon name="x" /></button>
        </div>

        <div class="space-y-5 p-5">
          <!-- Zona de arrastre -->
          <label
            class="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition"
            :class="dragging ? 'border-accent-500 bg-accent-50' : 'border-ink/15 bg-white hover:border-accent-500/60'"
            @dragenter.prevent="onDragEnter"
            @dragover.prevent
            @dragleave.prevent="onDragLeave"
            @drop.prevent="onDrop"
          >
            <span
              class="mb-3 flex h-12 w-12 items-center justify-center rounded-full transition"
              :class="dragging ? 'bg-accent-600 text-white' : 'bg-accent-50 text-accent-600'"
            >
              <AppIcon name="upload" :size="22" />
            </span>
            <span class="text-sm font-medium text-ink">Arrastra tus PDF aquí</span>
            <span class="mt-1 text-xs text-ink-muted">o haz clic para elegir · archivos de cientos de páginas son bienvenidos</span>
            <input ref="fileInput" type="file" accept="application/pdf,.pdf" multiple class="sr-only" @change="onPick" />
          </label>

          <!-- Subidas en curso -->
          <ul v-if="jobs.length" class="space-y-2">
            <li v-for="job in jobs" :key="job.key" class="rounded-lg border border-ink/10 bg-white px-3 py-2.5">
              <div class="flex items-center justify-between gap-3 text-sm">
                <span class="truncate font-medium">{{ job.name }}</span>
                <span class="shrink-0 text-xs text-ink-muted">
                  <template v-if="job.state === 'uploading'">Subiendo {{ Math.round(job.progress * 100) }}%</template>
                  <template v-else-if="job.state === 'done'">Subido ✓</template>
                  <span v-else class="text-red-600">{{ job.error }}</span>
                </span>
              </div>
              <div class="mt-2 h-1 overflow-hidden rounded-full bg-ink/10">
                <div
                  class="h-full rounded-full transition-all"
                  :class="job.state === 'error' ? 'bg-red-500' : 'bg-accent-500'"
                  :style="{ width: Math.max(4, job.progress * 100) + '%' }"
                />
              </div>
              <p class="mt-1 text-[11px] text-ink-muted">{{ formatSize(job.size) }}</p>
            </li>
          </ul>

          <!-- Lista de documentos -->
          <div>
            <h3 class="panel-title">Biblioteca</h3>
            <p v-if="docsError" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ docsError }}</p>
            <p v-else-if="!documents.length" class="rounded-lg border border-ink/10 bg-white px-3 py-6 text-center text-sm text-ink-muted">
              Aún no has subido documentos.
            </p>
            <ul v-else class="max-h-[46vh] space-y-2 overflow-y-auto pr-1 scrollbar-thin">
              <li v-for="doc in documents" :key="doc.id" class="rounded-lg border border-ink/10 bg-white px-3 py-3">
                <div class="flex items-start gap-3">
                  <span class="mt-0.5 text-ink-muted"><AppIcon name="file" /></span>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <a v-if="doc.pdf_url" :href="doc.pdf_url" target="_blank" class="truncate text-sm font-medium hover:underline">{{ doc.filename }}</a>
                      <span v-else class="truncate text-sm font-medium">{{ doc.filename }}</span>
                      <span class="pill shrink-0" :class="statusClass[doc.status]">{{ statusLabel[doc.status] }}</span>
                    </div>
                    <p class="mt-0.5 text-xs text-ink-muted">
                      {{ doc.total_pages }} páginas · {{ doc.question_count }} preguntas
                    </p>

                    <div v-if="doc.status === 'processing' || doc.status === 'pending'" class="mt-2">
                      <div class="flex justify-between text-[11px] text-ink-soft">
                        <span v-if="doc.status === 'processing'">Procesando página {{ doc.processed_pages }} de {{ doc.total_pages }}…</span>
                        <span v-else>Esperando al worker…</span>
                        <span class="font-mono">{{ Math.round(doc.progress * 100) }}%</span>
                      </div>
                      <div class="relative mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
                        <div class="h-full rounded-full bg-accent-500 transition-all duration-700" :style="{ width: doc.progress * 100 + '%' }" />
                        <div class="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/50 to-transparent" />
                      </div>
                    </div>

                    <p v-if="doc.error_message" class="mt-2 flex gap-1.5 text-xs" :class="doc.status === 'failed' ? 'text-red-700' : 'text-amber-700'">
                      <AppIcon name="alert" :size="14" class="mt-px shrink-0" />
                      <span>{{ doc.error_message }}</span>
                    </p>
                  </div>
                  <div class="flex shrink-0 gap-1">
                    <button
                      v-if="canResume(doc)"
                      class="btn-outline px-2.5 py-1 text-xs"
                      :title="`Continuar desde la página ${doc.processed_pages + 1}`"
                      @click="reprocess(doc, true)"
                    >
                      Reanudar
                    </button>
                    <button
                      v-if="doc.status === 'completed' || doc.status === 'failed'"
                      class="btn-ghost px-2 py-1.5"
                      title="Reprocesar"
                      @click="reprocess(doc)"
                    >
                      <AppIcon name="refresh" :size="16" />
                    </button>
                    <button class="btn-ghost px-2 py-1.5 hover:text-red-600" title="Eliminar" @click="removeDoc(doc)">
                      <AppIcon name="trash" :size="16" />
                    </button>
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <!-- Clave de respuestas -->
          <div>
            <h3 class="panel-title">Clave de respuestas</h3>
            <div class="rounded-lg border border-ink/10 bg-white px-3 py-3">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <p class="text-xs text-ink-soft">
                  <template v-if="keyRows">{{ keyRows }} respuestas cargadas.</template>
                  <template v-else>Sin clave cargada.</template>
                  Se aplica por página y número de pregunta, también después de reprocesar.
                </p>
                <label class="btn-outline cursor-pointer px-2.5 py-1 text-xs" :class="keyBusy ? 'pointer-events-none opacity-60' : ''">
                  <AppIcon :name="keyBusy ? 'loader' : 'upload'" :size="14" :class="keyBusy ? 'animate-spin' : ''" />
                  {{ keyRows ? 'Reemplazar clave' : 'Subir clave' }} (JSON/CSV)
                  <input type="file" accept=".json,.csv,application/json,text/csv" class="sr-only" @change="onPickKey" />
                </label>
              </div>
              <div v-if="keyResult" class="mt-2 text-xs text-ink-muted">
                {{ keyResult.matched_questions }} preguntas recibieron respuesta;
                {{ keyResult.unmatched_key_rows }} filas de la clave no encontraron su pregunta<span v-if="keyResult.unmatched.length">:
                  <span class="font-mono">{{ keyResult.unmatched.slice(0, 12).join(', ') }}{{ keyResult.unmatched.length > 12 ? '…' : '' }}</span></span>.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
