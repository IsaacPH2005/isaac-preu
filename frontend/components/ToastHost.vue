<script setup lang="ts">
const { toasts } = useToast()
const toneClass = {
  success: 'bg-ink text-white',
  error: 'bg-red-600 text-white',
  info: 'bg-white text-ink ring-1 ring-ink/10',
}
</script>

<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex -translate-x-1/2 flex-col items-center gap-2">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="animate-fade-in rounded-lg px-4 py-2.5 text-sm shadow-lift"
        :class="toneClass[t.tone]"
        role="status"
      >
        {{ t.message }}
      </div>
    </div>
  </Teleport>
</template>
