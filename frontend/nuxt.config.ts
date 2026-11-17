// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: false },
  // App de estudio 100% interactiva: render en cliente (KaTeX, clipboard, drag & drop).
  ssr: false,

  modules: ['@nuxtjs/tailwindcss'],
  css: ['katex/dist/katex.min.css', '~/assets/css/main.css'],

  runtimeConfig: {
    // URL interna del backend FastAPI. Sobrescribible con NUXT_BACKEND_URL.
    backendUrl: 'http://localhost:8000',
  },

  app: {
    head: {
      title: 'BancoPreu — Banco de preguntas',
      htmlAttrs: { lang: 'es' },
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'Extrae, clasifica y busca preguntas de bancos preuniversitarios en PDF.' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap',
        },
      ],
    },
  },

  tailwindcss: {
    cssPath: false,
  },

  typescript: {
    strict: true,
  },
})
