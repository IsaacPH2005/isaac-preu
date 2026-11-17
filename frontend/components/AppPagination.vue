<script setup lang="ts">
const props = defineProps<{ page: number; pages: number }>()
const emit = defineEmits<{ change: [page: number] }>()

// Ventana de páginas con elipsis: 1 … 4 5 [6] 7 8 … 20
const items = computed<(number | '…')[]>(() => {
  const { page, pages } = props
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1)
  const set = new Set([1, pages, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pages))
  const sorted = [...set].sort((a, b) => a - b)
  const out: (number | '…')[] = []
  sorted.forEach((p, i) => {
    if (i && p - sorted[i - 1] > 1) out.push('…')
    out.push(p)
  })
  return out
})
</script>

<template>
  <nav v-if="pages > 1" class="flex items-center justify-center gap-1" aria-label="Paginación">
    <button class="btn-ghost px-2" :disabled="page <= 1" aria-label="Anterior" @click="emit('change', page - 1)">
      <AppIcon name="chevronLeft" :size="16" />
    </button>
    <template v-for="(it, i) in items" :key="i">
      <span v-if="it === '…'" class="px-1 text-ink-muted">…</span>
      <button
        v-else
        class="h-9 min-w-9 rounded-lg px-2 font-mono text-sm transition"
        :class="it === page ? 'bg-ink text-white' : 'text-ink-soft hover:bg-ink/5'"
        @click="emit('change', it)"
      >
        {{ it }}
      </button>
    </template>
    <button class="btn-ghost px-2" :disabled="page >= pages" aria-label="Siguiente" @click="emit('change', page + 1)">
      <AppIcon name="chevronRight" :size="16" />
    </button>
  </nav>
</template>
