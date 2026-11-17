<script setup lang="ts">
const { push } = useToast()

// ─── Datos de la donación ──────────────────────────────────────────
const WA_NUMBER = '59168597440'
const WA_DISPLAY = '+591 685 97440'
const ACCOUNT = '40022425120'
const HOLDER = 'ISAAC PARISACA HUALLPA'
const BANK = 'BancoFie'
const QR_IMAGE = '/qr/bancofie-qr.png'
const QR_RECEIPT = '/qr/bancofie-comprobante.jpeg'
const MEME_IMAGE = '/memes/meme-gracias.jpg'
// El comprobante de BancoFie indica «válido hasta 18/11/2026».
const QR_VALID_UNTIL = new Date('2026-11-18T23:59:59-04:00')
const qrExpired = computed(() => Date.now() > QR_VALID_UNTIL.getTime())

const waLink = (message: string) => `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(message)}`
const waGeneral = waLink('Hola Isaac 👋 Vi la página de donaciones de BancoPreu y tengo una duda.')
const waWork = waLink(
  'Hola Isaac 👋 Vi BancoPreu y quiero hablar contigo por una recomendación / para trabajar juntos.',
)
const waMeme = waLink('Hola Isaac 👋 Te mando un meme para el Fondo Oficial de Memes de BancoPreu:')
const waHelp = waLink('Hola Isaac 👋 No pude escanear el QR de donaciones de BancoPreu, ¿me ayudas?')

const copied = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | null = null

onBeforeUnmount(() => {
  if (copiedTimer) clearTimeout(copiedTimer)
})

async function copyField(value: string, key: string, label: string) {
  const ok = await copyToClipboard(value)
  if (!ok) {
    push('No se pudo copiar. Intenta seleccionarlo a mano.', 'error')
    return
  }
  copied.value = key
  push(`${label} copiado ✨`, 'success')
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => (copied.value = ''), 1800)
}

// ─── Niveles de hambre ─────────────────────────────────────────────
interface Tier {
  amount: number
  icon: string
  title: string
  blurb: string
}

const tiers: Tier[] = [
  { amount: 10, icon: '☕', title: 'Un api con té', blurb: 'Una hora de concentración. O de mirar la pantalla, según el día.' },
  { amount: 25, icon: '🍗', title: 'Medio pollo', blurb: 'La unidad oficial de motivación de este proyecto.' },
  { amount: 50, icon: '🍟', title: 'Pollo + papas', blurb: 'Modo dios del desarrollador: activado.' },
  { amount: 100, icon: '😂', title: 'Pollo + meme', blurb: 'Financias el próximo meme de calidad dudosa.' },
]

const selectedAmount = ref<number | null>(null)

async function pickAmount(tier: Tier) {
  selectedAmount.value = tier.amount
  const ok = await copyToClipboard(String(tier.amount))
  if (ok) push(`Bs. ${tier.amount} copiado. Pégalo en tu app del banco.`, 'success')
  else push(`Escribe Bs. ${tier.amount} en tu app del banco.`, 'info')

  if (window.innerWidth < 1024) {
    document.getElementById('qr-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

useHead({
  title: 'Donaciones — BancoPreu',
  meta: [
    {
      name: 'description',
      content:
        'Invítame un pollo y financia el Fondo Oficial de Memes de BancoPreu. Donaciones por QR de BancoFie.',
    },
    { property: 'og:title', content: 'Invítame un pollo — BancoPreu' },
    {
      property: 'og:description',
      content: 'BancoPreu es gratis y sin anuncios. Si te sirvió, invítame un pollo (o financia un meme).',
    },
  ],
})
</script>

<template>
  <div class="relative min-h-screen overflow-hidden">
    <!-- Fondos decorativos -->
    <div
      class="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[540px] bg-[radial-gradient(50rem_30rem_at_78%_-8%,rgba(47,138,111,0.14),transparent),radial-gradient(38rem_26rem_at_8%_6%,rgba(232,176,75,0.16),transparent)]"
    />

    <header class="sticky top-0 z-30 border-b border-ink/[0.07] bg-paper/85 backdrop-blur">
      <div class="mx-auto flex h-16 max-w-[1180px] items-center gap-3 px-4 sm:px-6">
        <NuxtLink to="/" class="flex items-baseline gap-2">
          <span class="font-serif text-[28px] italic leading-none tracking-tight text-ink">BancoPreu</span>
          <span class="hidden text-xs text-ink-muted sm:inline">banco de preguntas</span>
        </NuxtLink>

        <nav class="ml-auto flex items-center gap-1.5">
          <NuxtLink to="/" class="btn-ghost px-2 sm:hidden" aria-label="Volver al banco de preguntas">
            <AppIcon name="chevronLeft" :size="17" />
          </NuxtLink>
          <NuxtLink to="/" class="btn-ghost hidden px-2.5 sm:inline-flex">
            <AppIcon name="chevronLeft" :size="15" />
            Volver al banco
          </NuxtLink>
          <a :href="waGeneral" target="_blank" rel="noopener" class="btn-primary py-1.5 text-[13px]">
            <AppIcon name="message" :size="15" />
            WhatsApp
          </a>
        </nav>
      </div>
    </header>

    <main class="mx-auto max-w-[1180px] px-4 pb-4 pt-10 sm:px-6 sm:pt-14">
      <!-- ─── Héroe + QR ─────────────────────────────────────────── -->
      <section class="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-12">
        <div>
          <span class="pill bg-white text-ink-soft ring-1 ring-ink/10">
            <AppIcon name="heart" :size="12" class="text-rose-500" />
            Donaciones · sin culpa
          </span>

          <h1 class="mt-4 font-serif text-[clamp(2.9rem,7vw,4.6rem)] italic leading-[0.95] tracking-tight text-ink">
            Invítame
            <span class="relative inline-block">
              un pollo
              <svg
                class="absolute -bottom-1 left-0 h-3 w-full text-amber-400"
                viewBox="0 0 200 12"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path d="M2 8C40 3 150 2 198 7" stroke="currentColor" stroke-width="5" stroke-linecap="round" fill="none" />
              </svg>
            </span>
            .
          </h1>

          <p class="mt-5 max-w-xl text-[15px] leading-relaxed text-ink-soft sm:text-base">
            BancoPreu es gratis, sin anuncios y sin plan premium. Si te ayudó a estudiar (o a aprobar),
            esta es tu oportunidad de devolver el favor: <strong class="font-semibold text-ink">un pollo para el dev</strong>
            y un meme para la comunidad.
          </p>

          <div class="mt-5 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
            <span class="pill bg-white ring-1 ring-ink/10">Sin suscripciones</span>
            <span class="pill bg-white ring-1 ring-ink/10">Sin anuncios</span>
            <span class="pill bg-white ring-1 ring-ink/10">Sin letra chica</span>
          </div>

          <div class="mt-7 flex flex-wrap gap-2">
            <a href="#qr-panel" class="btn-primary">
              <AppIcon name="heart" :size="16" />
              Donar con QR
            </a>
            <a :href="waGeneral" target="_blank" rel="noopener" class="btn-outline">
              <AppIcon name="message" :size="16" />
              Hablar con Isaac
            </a>
          </div>

          <!-- Causas -->
          <div class="mt-9 grid gap-3 sm:grid-cols-2">
            <article
              class="rounded-2xl border border-ink/[0.08] bg-white p-4 shadow-card transition hover:-translate-y-0.5 hover:shadow-lift"
            >
              <div class="flex items-center gap-3">
                <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-xl ring-1 ring-amber-200/70">
                  🍗
                </span>
                <div>
                  <p class="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">Causa oficial #1</p>
                  <h2 class="font-serif text-xl italic leading-tight">El fondo del pollo</h2>
                </div>
              </div>
              <p class="mt-3 text-[13px] leading-relaxed text-ink-soft">
                El pollo no es un lujo: es el combustible oficial del proyecto. Café, horas de código y una que
                otra crisis existencial resuelta.
              </p>
            </article>

            <article
              class="rounded-2xl border border-ink/[0.08] bg-white p-4 shadow-card transition hover:-translate-y-0.5 hover:shadow-lift"
            >
              <div class="flex items-center gap-3">
                <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-xl ring-1 ring-accent-200/70">
                  😂
                </span>
                <div>
                  <p class="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">Causa oficial #2</p>
                  <h2 class="font-serif text-xl italic leading-tight">El fondo de memes</h2>
                </div>
              </div>
              <p class="mt-3 text-[13px] leading-relaxed text-ink-soft">
                Una causa seria: cada aporte financia memes de calidad dudosa y mantiene el humor en producción.
              </p>
              <a
                :href="waMeme"
                target="_blank"
                rel="noopener"
                class="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-accent-700 hover:text-accent-600"
              >
                Mandar mi meme
                <AppIcon name="external" :size="12" />
              </a>
            </article>
          </div>

          <dl class="mt-8 grid grid-cols-3 gap-4 border-t border-ink/10 pt-5">
            <div>
              <dt class="text-[11px] uppercase tracking-wider text-ink-muted">Anuncios</dt>
              <dd class="mt-1 font-serif text-2xl italic leading-none">Cero</dd>
            </div>
            <div>
              <dt class="text-[11px] uppercase tracking-wider text-ink-muted">Precio</dt>
              <dd class="mt-1 font-serif text-2xl italic leading-none">Bs. 0</dd>
            </div>
            <div>
              <dt class="text-[11px] uppercase tracking-wider text-ink-muted">Meta actual</dt>
              <dd class="mt-1 font-serif text-2xl italic leading-none">1 pollo</dd>
            </div>
          </dl>
        </div>

        <!-- Panel QR -->
        <div id="qr-panel" class="scroll-mt-24 lg:sticky lg:top-24">
          <div class="relative overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-lift">
            <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-accent-50/70 via-white to-white" />

            <div class="relative p-5 sm:p-6">
              <div class="flex items-center justify-between gap-3">
                <span class="pill bg-accent-600 text-white">
                  <AppIcon name="bank" :size="13" />
                  Donación por QR
                </span>
                <span class="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">{{ BANK }}</span>
              </div>

              <div class="mx-auto mt-5 w-full max-w-[300px] rounded-2xl bg-white p-3 shadow-card ring-1 ring-ink/10">
                <img
                  :src="QR_IMAGE"
                  alt="Código QR de BancoFie para donar a Isaac Parisaca Huallpa"
                  class="w-full rounded-lg"
                  width="578"
                  height="578"
                  decoding="async"
                />
              </div>

              <p class="mt-4 text-center text-sm text-ink-soft">
                Escanea desde la app de tu banco y escribe el monto que nazca.
              </p>

              <div class="mt-4 divide-y divide-ink/[0.06] overflow-hidden rounded-xl bg-paper/80 ring-1 ring-ink/[0.06]">
                <button
                  class="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition hover:bg-white"
                  @click="copyField(HOLDER, 'holder', 'Titular')"
                >
                  <span class="min-w-0">
                    <span class="block text-[10px] uppercase tracking-wider text-ink-muted">Titular</span>
                    <span class="block truncate text-[12px] font-medium text-ink">{{ HOLDER }}</span>
                  </span>
                  <AppIcon
                    :name="copied === 'holder' ? 'check' : 'copy'"
                    :size="15"
                    class="shrink-0"
                    :class="copied === 'holder' ? 'text-accent-600' : 'text-ink-muted'"
                  />
                </button>

                <button
                  class="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition hover:bg-white"
                  @click="copyField(ACCOUNT, 'account', 'Número de cuenta')"
                >
                  <span class="min-w-0">
                    <span class="block text-[10px] uppercase tracking-wider text-ink-muted">Cuenta destino</span>
                    <span class="block font-mono text-[13px] font-medium tracking-wide text-ink">{{ ACCOUNT }}</span>
                  </span>
                  <AppIcon
                    :name="copied === 'account' ? 'check' : 'copy'"
                    :size="15"
                    class="shrink-0"
                    :class="copied === 'account' ? 'text-accent-600' : 'text-ink-muted'"
                  />
                </button>

                <div class="flex items-center justify-between gap-3 px-3 py-2.5">
                  <span>
                    <span class="block text-[10px] uppercase tracking-wider text-ink-muted">Monto</span>
                    <span class="block text-[12px] font-medium text-ink">Tú eliges 🍗</span>
                  </span>
                  <AppIcon name="sparkles" :size="15" class="shrink-0 text-ink-muted" />
                </div>
              </div>

              <button class="btn-primary mt-3 w-full" @click="copyField(ACCOUNT, 'account', 'Número de cuenta')">
                <AppIcon :name="copied === 'account' ? 'check' : 'copy'" :size="15" />
                {{ copied === 'account' ? 'Cuenta copiada' : 'Copiar número de cuenta' }}
              </button>

              <a :href="QR_IMAGE" download="qr-donacion-bancofie-isaac.png" class="btn-ghost mt-1.5 w-full py-1.5 text-xs">
                <AppIcon name="download" :size="14" />
                Descargar el QR
              </a>

              <p class="mt-3 text-center text-[11px] leading-relaxed text-ink-muted">
                El QR no muerde. Hasta Bs. 1 cuenta (y se agradece con un meme).
              </p>
              <p class="mt-1 text-center text-[10px] text-ink-muted">
                <template v-if="qrExpired">
                  ⚠️ Este QR ya venció.
                  <a :href="waHelp" target="_blank" rel="noopener" class="font-medium text-accent-700 underline-offset-2 hover:underline">
                    Pídeme uno nuevo
                  </a>
                </template>
                <template v-else>
                  QR vigente hasta el 18/11/2026 ·
                  <a :href="waHelp" target="_blank" rel="noopener" class="font-medium text-accent-700 underline-offset-2 hover:underline">
                    ¿Venció? Pídeme otro
                  </a>
                </template>
              </p>
              <div class="mt-1.5 flex flex-wrap items-center justify-center gap-x-2.5 gap-y-1 text-[11px]">
                <a
                  :href="QR_RECEIPT"
                  target="_blank"
                  rel="noopener"
                  class="inline-flex items-center gap-1 font-medium text-ink-soft underline-offset-2 hover:text-ink hover:underline"
                >
                  <AppIcon name="external" :size="11" />
                  Ver comprobante del banco
                </a>
                <span class="text-ink/20" aria-hidden="true">·</span>
                <a
                  :href="waHelp"
                  target="_blank"
                  rel="noopener"
                  class="font-medium text-accent-700 underline-offset-2 hover:underline"
                >
                  ¿No funciona el QR?
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ─── Niveles de hambre ───────────────────────────────────── -->
      <section class="mt-16 sm:mt-20">
        <div class="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p class="panel-title">Elige tu nivel de hambre</p>
            <h2 class="font-serif text-3xl italic leading-tight sm:text-4xl">¿Qué tan agradecido estás?</h2>
          </div>
          <p class="max-w-sm text-sm leading-relaxed text-ink-soft">
            Toca una tarjeta y te copio el monto. Luego lo pegas en tu app del banco y listo.
          </p>
        </div>

        <div class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <button
            v-for="tier in tiers"
            :key="tier.amount"
            type="button"
            class="group rounded-2xl border bg-white p-5 text-left shadow-card transition hover:-translate-y-0.5 hover:shadow-lift"
            :class="
              selectedAmount === tier.amount
                ? 'border-accent-500 ring-2 ring-accent-500/20'
                : 'border-ink/[0.08] hover:border-ink/15'
            "
            @click="pickAmount(tier)"
          >
            <span class="flex h-10 w-10 items-center justify-center rounded-full bg-paper text-xl ring-1 ring-ink/10">
              {{ tier.icon }}
            </span>
            <span class="mt-3 block font-serif text-2xl italic leading-none">Bs. {{ tier.amount }}</span>
            <span class="mt-1.5 block text-sm font-medium text-ink">{{ tier.title }}</span>
            <span class="mt-1 block min-h-[32px] text-xs leading-relaxed text-ink-muted">{{ tier.blurb }}</span>
            <span
              class="mt-4 inline-flex items-center gap-1 text-[11px] font-medium"
              :class="selectedAmount === tier.amount ? 'text-accent-700' : 'text-ink-muted group-hover:text-ink-soft'"
            >
              <AppIcon :name="selectedAmount === tier.amount ? 'check' : 'copy'" :size="12" />
              {{ selectedAmount === tier.amount ? 'Monto copiado' : 'Copiar monto' }}
            </span>
          </button>
        </div>

        <p class="mt-3 text-xs text-ink-muted">¿Otro monto? También sirve. El QR no juzga.</p>
      </section>

      <!-- ─── Meme oficial ────────────────────────────────────────── -->
      <section class="mt-16 grid items-center gap-8 sm:mt-20 lg:grid-cols-2 lg:gap-14">
        <div class="relative mx-auto w-full max-w-md">
          <div class="absolute -inset-3 -rotate-2 rounded-3xl bg-amber-200/45" aria-hidden="true" />
          <figure
            class="relative -rotate-1 rounded-2xl border border-ink/10 bg-white p-3 shadow-lift transition duration-300 hover:rotate-0"
          >
            <img
              :src="MEME_IMAGE"
              alt="Meme de un perrito con traje que dice: muchas gracias por su atención, aplaudan y no hagan preguntas"
              class="w-full rounded-xl"
              width="736"
              height="736"
              loading="lazy"
              decoding="async"
            />
            <figcaption class="px-2 pb-1 pt-3 text-center text-[11px] text-ink-muted">
              El meme oficial del fondo. Calidad cuestionable, intención noble.
            </figcaption>
          </figure>
          <span
            class="absolute -right-2 -top-3 rotate-6 rounded-full bg-ink px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-white shadow-lift"
          >
            Meme certificado
          </span>
        </div>

        <div>
          <p class="panel-title">Causa #2, pero con más estilo</p>
          <h2 class="font-serif text-3xl italic leading-tight sm:text-4xl">El Fondo Oficial de Memes</h2>
          <p class="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-soft">
            Los memes son parte del servicio: hacen que estudiar Física a las 2 a.m. duela un poquito menos.
            Tu donación también financia esta área tan seria del proyecto.
          </p>

          <ul class="mt-5 space-y-2.5 text-sm text-ink-soft">
            <li class="flex items-start gap-2.5">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-50 text-accent-700">
                <AppIcon name="check" :size="12" />
              </span>
              <span><strong class="font-medium text-ink">Bs. 10:</strong> un meme reciclado, pero con cariño.</span>
            </li>
            <li class="flex items-start gap-2.5">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-50 text-accent-700">
                <AppIcon name="check" :size="12" />
              </span>
              <span><strong class="font-medium text-ink">Bs. 50:</strong> un meme nuevo, editado sin dormir.</span>
            </li>
            <li class="flex items-start gap-2.5">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-50 text-accent-700">
                <AppIcon name="check" :size="12" />
              </span>
              <span><strong class="font-medium text-ink">Bs. 100:</strong> un meme que sí da risa (sin garantía).</span>
            </li>
          </ul>

          <div class="mt-6 flex flex-wrap gap-2">
            <a :href="waMeme" target="_blank" rel="noopener" class="btn-primary">
              <AppIcon name="message" :size="16" />
              Mandar mi meme
            </a>
            <a href="#qr-panel" class="btn-outline">
              <AppIcon name="heart" :size="16" />
              Financiar el fondo
            </a>
          </div>
          <p class="mt-3 text-xs text-ink-muted">Aceptamos memes propios, robados con permiso y de dudosa procedencia.</p>
        </div>
      </section>

      <!-- ─── Transparencia ───────────────────────────────────────── -->
      <section class="mt-16 rounded-2xl border border-ink/[0.08] bg-white p-6 shadow-card sm:mt-20 sm:p-8">
        <div class="max-w-2xl">
          <p class="panel-title">Transparencia (más o menos)</p>
          <h2 class="font-serif text-3xl italic leading-tight sm:text-4xl">¿En qué se va tu aporte?</h2>
        </div>

        <div class="mt-7 grid gap-6 sm:grid-cols-3">
          <div>
            <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-50 text-accent-700">
              <AppIcon name="bank" :size="19" />
            </span>
            <h3 class="mt-3 text-sm font-semibold text-ink">Servidores y APIs</h3>
            <p class="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
              Hosting, base de datos y las APIs de IA que extraen y ordenan las preguntas.
            </p>
          </div>
          <div>
            <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
              <AppIcon name="book" :size="19" />
            </span>
            <h3 class="mt-3 text-sm font-semibold text-ink">Más preguntas</h3>
            <p class="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
              Subir nuevos bancos y mantener el buscador rápido, gratis y sin anuncios.
            </p>
          </div>
          <div>
            <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
              <AppIcon name="heart" :size="19" />
            </span>
            <h3 class="mt-3 text-sm font-semibold text-ink">Pollo y memes</h3>
            <p class="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
              La parte no negociable: alimentar al dev y mantener el humor en producción.
            </p>
          </div>
        </div>
      </section>

      <!-- ─── Contacto / trabajar conmigo ─────────────────────────── -->
      <section class="relative mt-16 overflow-hidden rounded-3xl bg-ink text-white shadow-lift sm:mt-20">
        <div class="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full bg-accent-500/25 blur-3xl" />
        <div class="pointer-events-none absolute -bottom-24 left-1/3 h-64 w-64 rounded-full bg-amber-400/15 blur-3xl" />

        <div class="relative p-6 sm:p-10">
          <span class="pill bg-white/10 text-white/80 ring-1 ring-white/15">
            <AppIcon name="sparkles" :size="12" />
            Hablemos
          </span>

          <h2 class="mt-4 max-w-2xl font-serif text-3xl italic leading-tight sm:text-4xl">
            ¿Más recomendaciones o quieres trabajar conmigo?
          </h2>
          <p class="mt-3 max-w-xl text-sm leading-relaxed text-white/70">
            Escríbeme directo. Hago páginas web, apps, automatizaciones y cosas raras con IA. También acepto
            recomendaciones de pollo y memes.
          </p>

          <div class="mt-6 flex flex-wrap items-center gap-2.5">
            <a
              :href="waWork"
              target="_blank"
              rel="noopener"
              class="btn bg-white text-ink hover:bg-paper"
            >
              <AppIcon name="message" :size="16" />
              WhatsApp: {{ WA_DISPLAY }}
            </a>
            <a href="tel:+59168597440" class="btn border border-white/20 text-white hover:bg-white/10">
              Llamar
            </a>
          </div>

          <div class="mt-8 flex items-center gap-3 border-t border-white/10 pt-5">
            <span class="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 font-serif text-lg italic">
              IC
            </span>
            <div>
              <p class="text-sm font-medium">Isaac Creativo Dev</p>
              <p class="text-xs text-white/50">Web · IA · memes · soluciones a medida</p>
            </div>
            <span class="ml-auto hidden font-mono text-[11px] text-white/40 sm:inline">{{ WA_DISPLAY }}</span>
          </div>
        </div>
      </section>
    </main>

    <AppFooter />
    <ToastHost />
  </div>
</template>
