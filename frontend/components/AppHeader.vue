<script setup lang="ts">
const emit = defineEmits<{ upload: []; toggleFilters: [] }>()
const { active, documents } = useDocuments()
const { activeCount } = useSearchFilters()
const { allowUploads } = useServerInfo()

const primary = computed(() => active.value.find((d) => d.status === 'processing') ?? active.value[0])
const pct = computed(() => Math.round((primary.value?.progress ?? 0) * 100))
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-ink/[0.07] bg-paper/85 backdrop-blur">
    <div class="mx-auto flex h-16 max-w-[1440px] items-center gap-3 px-4 sm:px-6">
      <button class="btn-ghost -ml-2 px-2 lg:hidden" aria-label="Filtros" @click="emit('toggleFilters')">
        <AppIcon name="filter" />
        <span v-if="activeCount" class="pill bg-accent-600 px-1.5 text-white">{{ activeCount }}</span>
      </button>

      <a href="/" class="flex items-baseline gap-2">
        <span class="font-serif text-[28px] italic leading-none tracking-tight text-ink">BancoPreu</span>
        <span class="hidden text-xs text-ink-muted sm:inline">banco de preguntas</span>
      </a>

      <div class="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
        <NuxtLink
          to="/donaciones"
          class="btn-ghost shrink-0 gap-1.5 px-2.5"
          title="Invítame un pollo: donaciones"
          aria-label="Donaciones"
        >
          <AppIcon name="heart" :size="16" class="text-rose-500" />
          <span class="hidden sm:inline">Donar</span>
        </NuxtLink>

        <!-- Progreso en vivo -->
        <button
          v-if="primary && allowUploads"
          class="group hidden min-w-0 items-center gap-3 rounded-lg border border-ink/10 bg-white px-3 py-1.5 text-left md:flex"
          @click="emit('upload')"
        >
          <span class="relative flex h-2 w-2 shrink-0">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-500 opacity-60" />
            <span class="relative inline-flex h-2 w-2 rounded-full bg-accent-500" />
          </span>
          <span class="min-w-0">
            <span class="block truncate text-xs font-medium text-ink">
              <template v-if="primary.status === 'pending'">En cola: {{ primary.filename }}</template>
              <template v-else>
                Procesando página {{ primary.processed_pages }} de {{ primary.total_pages }}…
              </template>
            </span>
            <span class="mt-1 block h-1 w-52 overflow-hidden rounded-full bg-ink/10">
              <span class="block h-full rounded-full bg-accent-500 transition-all duration-700" :style="{ width: pct + '%' }" />
            </span>
          </span>
          <span v-if="active.length > 1" class="pill bg-ink/5 text-ink-soft">+{{ active.length - 1 }}</span>
        </button>

        <span v-else-if="documents.length" class="hidden text-xs text-ink-muted md:inline">
          {{ documents.length }} documento{{ documents.length === 1 ? '' : 's' }}
        </span>

        <button v-if="allowUploads" class="btn-primary" @click="emit('upload')">
          <AppIcon name="upload" :size="16" />
          <span class="hidden sm:inline">Subir PDF</span>
        </button>
      </div>
    </div>
  </header>
</template>
