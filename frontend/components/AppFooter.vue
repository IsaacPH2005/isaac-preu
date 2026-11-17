<script setup lang="ts">
const WA_LINK =
  'https://wa.me/59168597440?text=' +
  encodeURIComponent('Hola Isaac 👋 Vi BancoPreu y quiero hablar contigo.')
const year = new Date().getFullYear()
</script>

<template>
  <footer class="mt-16 border-t border-ink/[0.07] bg-paper-dark/40">
    <div
      class="mx-auto flex max-w-[1440px] flex-col gap-4 px-4 py-7 sm:px-6 md:flex-row md:items-center md:justify-between"
    >
      <div>
        <p class="font-serif text-lg italic leading-none">BancoPreu</p>
        <p class="mt-1.5 text-xs text-ink-muted">
          Hecho con café, memes y demasiado cariño por
          <span class="font-medium text-ink-soft">Isaac Creativo Dev</span>.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <NuxtLink to="/donaciones" class="btn-outline py-1.5 text-[13px]">
          <AppIcon name="heart" :size="14" class="text-rose-500" />
          Invítame un pollo
        </NuxtLink>
        <a :href="WA_LINK" target="_blank" rel="noopener" class="btn-ghost py-1.5 text-[13px]">
          <AppIcon name="message" :size="14" />
          +591 685 97440
        </a>
      </div>
    </div>

    <div class="border-t border-ink/[0.06]">
      <div
        class="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2 px-4 py-3 text-[11px] text-ink-muted sm:px-6"
      >
        <span>© {{ year }} BancoPreu. Sin anuncios, sin suscripciones, sin letra chica.</span>
        <span class="hidden sm:inline">Hecho en Bolivia 🇧🇴</span>
      </div>
    </div>
  </footer>
</template>
