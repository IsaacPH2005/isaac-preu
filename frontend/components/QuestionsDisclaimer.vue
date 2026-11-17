<script setup lang="ts">
// Aviso global: las preguntas se extraen de los PDF con IA y pueden tener errores.
// Se puede cerrar y no vuelve a aparecer en este navegador.
const STORAGE_KEY = 'bancopreu:disclaimer-hidden'
const hidden = useState('disclaimer-hidden', () => false)
const ready = ref(false)

onMounted(() => {
  try {
    hidden.value = localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    /* almacenamiento bloqueado */
  }
  ready.value = true
})

function dismiss() {
  hidden.value = true
  try {
    localStorage.setItem(STORAGE_KEY, '1')
  } catch {
    /* almacenamiento bloqueado */
  }
}
</script>

<template>
  <div
    v-if="ready && !hidden"
    class="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900"
    role="note"
  >
    <AppIcon name="alert" :size="18" class="mt-0.5 shrink-0 text-amber-700" />
    <div class="min-w-0 flex-1 text-[13px] leading-relaxed">
      <p class="font-medium">Aviso: algunas preguntas pueden estar mal.</p>
      <p class="mt-0.5">
        El banco se extrae de los PDF con IA y puede contener errores en el enunciado, los datos, las alternativas o la
        respuesta. <strong class="font-semibold">Las preguntas con gráficos son las que más fallan</strong>: en la
        práctica, prácticamente todas (≈100 %) pueden estar mal transcritas. Revisa siempre la página original antes de
        dar una por buena.
      </p>
    </div>
    <button
      class="shrink-0 rounded-md px-2 py-1 text-[12px] font-medium text-amber-900/70 transition hover:bg-amber-100 hover:text-amber-900"
      aria-label="Ocultar aviso"
      @click="dismiss"
    >
      Entendido
    </button>
  </div>
</template>
