<script setup lang="ts">
// narrow: alinea el pie con páginas de ancho 1120px (donaciones); por defecto 1440px.
const props = defineProps<{ narrow?: boolean }>()
const maxW = computed(() => (props.narrow ? 'max-w-[1120px]' : 'max-w-[1440px]'))

const WA_NUMBER = '59168597440'
const WA_DISPLAY = '+591 685 97440'
const wa = (msg: string) => `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(msg)}`
const WA_WORK = wa('Hola Isaac 👋 Vi BancoPreu y quiero cotizar un proyecto contigo.')
const WA_REPORT = wa('Hola Isaac 👋 Encontré una pregunta con un error en BancoPreu:')
const year = new Date().getFullYear()

const route = useRoute()
const onDonations = computed(() => route.path.startsWith('/donaciones'))
</script>

<template>
  <footer class="mt-20 border-t border-ink/10 bg-paper-dark/50">
    <div :class="maxW" class="mx-auto grid gap-10 px-4 py-12 sm:px-6 md:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] md:gap-16">
      <!-- Sobre BancoPreu -->
      <div class="max-w-[30rem]">
        <p class="font-serif text-[26px] italic leading-none text-ink">BancoPreu</p>
        <p class="mt-3 text-[14px] leading-relaxed text-ink-soft">
          Un buscador gratuito de preguntas preuniversitarias: Física, Química, Biología y Matemáticas, con fórmulas
          y la página original de cada pregunta.
        </p>
        <p class="mt-3 text-[13px] leading-relaxed text-ink-muted">
          Las preguntas se extraen de los PDF con IA y pueden tener errores. Ante la duda, revisa la página
          original.
          <a :href="WA_REPORT" target="_blank" rel="noopener" class="font-medium text-accent-700 hover:underline">
            Reportar un error
          </a>
        </p>

        <nav class="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[14px]" aria-label="Pie de página">
          <NuxtLink to="/" class="font-medium text-ink-soft hover:text-ink">Buscar preguntas</NuxtLink>
          <NuxtLink v-if="!onDonations" to="/donaciones" class="inline-flex items-center gap-1.5 font-medium text-ink-soft hover:text-ink">
            <AppIcon name="heart" :size="14" class="text-rose-500" />
            Invítame un pollo
          </NuxtLink>
        </nav>
      </div>

      <!-- Autor -->
      <section aria-labelledby="footer-author" class="md:border-l md:border-ink/10 md:pl-10">
        <div class="flex items-center gap-4">
          <span
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-ink font-serif text-[24px] italic text-paper"
            aria-hidden="true"
          >
            Ic
          </span>
          <div>
            <p class="text-[13px] text-ink-muted">Hecho por</p>
            <p id="footer-author" class="font-serif text-[24px] italic leading-tight text-ink">Isaac Creativo Dev</p>
          </div>
        </div>

        <p class="mt-4 text-[14px] leading-relaxed text-ink-soft">
          Desarrollo páginas web, apps y automatizaciones con IA para negocios, institutos y emprendedores en
          Bolivia. ¿Tienes una idea? Hablemos.
        </p>

        <div class="mt-5 flex flex-wrap items-center gap-2">
          <a :href="WA_WORK" target="_blank" rel="noopener" class="btn-primary">
            <AppIcon name="message" :size="16" />
            Cotizar un proyecto
          </a>
          <a :href="`tel:+${WA_NUMBER}`" class="btn-ghost font-mono text-[13px]">{{ WA_DISPLAY }}</a>
        </div>
      </section>
    </div>

    <div class="border-t border-ink/[0.07]">
      <div
        :class="maxW"
        class="mx-auto flex flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-4 text-[12px] text-ink-muted sm:px-6"
      >
        <span>© {{ year }} BancoPreu. Gratis y sin anuncios.</span>
        <span>Hecho en Bolivia 🇧🇴</span>
      </div>
    </div>
  </footer>
</template>
