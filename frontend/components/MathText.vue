<script setup lang="ts">
/**
 * Renderiza texto con fórmulas mezcladas: $...$ (en línea), $$...$$ (bloque),
 * \(...\) y \[...\]. Los delimitadores sin cerrar se muestran como texto.
 */
const props = withDefaults(defineProps<{ content: string; tag?: string }>(), { tag: 'div' })
const html = computed(() => renderMathHtml(props.content ?? ''))
</script>

<template>
  <component :is="tag" class="math-text" v-html="html" />
</template>
