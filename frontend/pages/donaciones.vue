<script setup lang="ts">
const { push } = useToast()

// ─── Datos de la donación ──────────────────────────────────────────
const WA_NUMBER = '59168597440'
const ACCOUNT = '40022425120'
const HOLDER = 'ISAAC PARISACA HUALLPA'
const BANK = 'BancoFie'
const QR_IMAGE = '/qr/bancofie-qr.png'
const QR_RECEIPT = '/qr/bancofie-comprobante.jpeg'
const MEME_IMAGE = '/memes/meme-gracias.jpg'
// El comprobante de BancoFie indica «válido hasta 18/11/2026».
const QR_VALID_UNTIL = new Date('2026-11-18T23:59:59-04:00')
const QR_VALID_LABEL = '18/11/2026'
const qrExpired = ref(false)

const waLink = (message: string) => `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(message)}`
const waMeme = waLink('Hola Isaac 👋 Te mando un meme para el Fondo Oficial de Memes de BancoPreu:')
const waHelp = waLink('Hola Isaac 👋 No pude pagar con el QR de donaciones de BancoPreu, ¿me ayudas?')

// ─── Menú ──────────────────────────────────────────────────────────
interface Item {
  amount: number
  icon: string
  name: string
  note: string
}

const menu: Item[] = [
  { amount: 10, icon: '☕', name: 'Api con té', note: 'Una hora más de código' },
  { amount: 25, icon: '🍗', name: 'Medio pollo', note: 'La unidad oficial de motivación' },
  { amount: 50, icon: '🍟', name: 'Pollo con papas', note: 'Combustible para una semana de bugs' },
  { amount: 100, icon: '😂', name: 'Pollo + meme', note: 'Incluye un meme dedicado' },
]

const selected = ref<Item | null>(menu[1])
const custom = ref('')

const customAmount = computed(() => {
  const n = Number(custom.value.replace(',', '.'))
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : null
})
const amount = computed(() => customAmount.value ?? selected.value?.amount ?? null)
const lineName = computed(() => (customAmount.value ? 'Aporte libre' : selected.value?.name ?? 'Aporte libre'))
const lineIcon = computed(() => (customAmount.value ? '💛' : selected.value?.icon ?? '💛'))

function choose(item: Item) {
  selected.value = item
  custom.value = ''
}

function onCustomInput() {
  if (custom.value) selected.value = null
}

const fmt = (n: number) => `Bs. ${Number.isInteger(n) ? n : n.toFixed(2)}`

const waPaid = computed(() =>
  waLink(
    amount.value
      ? `Hola Isaac 👋 Te acabo de invitar ${lineName.value.toLowerCase()} (${fmt(amount.value)}) desde BancoPreu. Te mando el comprobante:`
      : 'Hola Isaac 👋 Te acabo de hacer una donación desde BancoPreu. Te mando el comprobante:',
  ),
)

// ─── Acciones del ticket ───────────────────────────────────────────
const copied = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | null = null

async function copyField(value: string, key: string, label: string) {
  const ok = await copyToClipboard(value)
  if (!ok) {
    push('No se pudo copiar. Selecciónalo y cópialo a mano.', 'error')
    return
  }
  copied.value = key
  push(`${label} copiado`, 'success')
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => (copied.value = ''), 1800)
}

// En el celular no se puede escanear la propia pantalla: lo útil es guardar el QR
// y abrirlo desde la app del banco («Pagar con QR» → «Subir imagen»).
const isTouch = ref(false)

async function saveQr() {
  try {
    const blob = await (await fetch(QR_IMAGE)).blob()
    const file = new File([blob], 'qr-donacion-bancopreu.png', { type: blob.type || 'image/png' })
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: 'QR de donación BancoPreu' })
      return
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
    push('QR guardado. Ábrelo desde la app de tu banco.', 'success')
  } catch (e: any) {
    if (e?.name !== 'AbortError') push('No se pudo guardar. Mantén presionado el QR para guardarlo.', 'error')
  }
}

// Barra de pago fija en móvil: visible mientras el ticket no está en pantalla.
const ticketVisible = ref(true)
let observer: IntersectionObserver | null = null

function goToTicket() {
  document.getElementById('ticket')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  qrExpired.value = Date.now() > QR_VALID_UNTIL.getTime()
  isTouch.value = window.matchMedia('(pointer: coarse)').matches
  const ticket = document.getElementById('ticket')
  if (ticket && 'IntersectionObserver' in window) {
    // Oculta la barra si el ticket está en pantalla o ya quedó arriba (no tapar el footer).
    observer = new IntersectionObserver(([entry]) => {
      ticketVisible.value = entry.isIntersecting || entry.boundingClientRect.top < 0
    }, {
      rootMargin: '0px 0px -30% 0px',
    })
    observer.observe(ticket)
  }
})
onBeforeUnmount(() => {
  if (copiedTimer) clearTimeout(copiedTimer)
  observer?.disconnect()
})

useHead({
  title: 'Invítame un pollo — BancoPreu',
  meta: [
    {
      name: 'description',
      content: 'BancoPreu es gratis y sin anuncios. Si te sirvió, invítale un pollo al dev con QR de BancoFie.',
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
  <div class="min-h-screen">
    <header class="sticky top-0 z-30 border-b border-ink/[0.07] bg-paper/85 backdrop-blur">
      <div class="mx-auto flex h-16 max-w-[1120px] items-center gap-3 px-4 sm:px-6">
        <NuxtLink to="/" class="flex items-baseline gap-2">
          <span class="font-serif text-[28px] italic leading-none tracking-tight text-ink">BancoPreu</span>
          <span class="hidden text-xs text-ink-muted sm:inline">banco de preguntas</span>
        </NuxtLink>
        <NuxtLink to="/" class="btn-ghost ml-auto px-2.5">
          <AppIcon name="chevronLeft" :size="15" />
          <span class="hidden sm:inline">Volver a las preguntas</span>
          <span class="sm:hidden">Volver</span>
        </NuxtLink>
      </div>
    </header>

    <main class="mx-auto max-w-[1120px] px-4 pb-6 pt-10 sm:px-6 sm:pt-14">
      <div class="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-16">
        <!-- ─── Izquierda: presentación + menú ─────────────────────── -->
        <div>
          <h1 class="font-serif text-[clamp(3rem,8vw,5.25rem)] italic leading-[0.92] tracking-tight text-ink">
            Invítame<br />un pollo.
          </h1>
          <p class="mt-6 max-w-[34rem] text-[16px] leading-relaxed text-ink-soft">
            BancoPreu es gratis, sin anuncios y sin cuentas. Si te ayudó a estudiar, puedes devolver el favor con
            lo que quieras: el aporte paga el servidor, las APIs que leen los PDF y, claro, el pollo.
          </p>

          <!-- Paso 1: menú -->
          <section class="mt-12" aria-labelledby="menu-title">
            <h2 id="menu-title" class="flex items-baseline gap-3">
              <span class="step-num">1</span>
              <span class="font-serif text-[28px] italic leading-none">Elige del menú</span>
            </h2>

            <div class="mt-5 rounded-2xl border border-ink/10 bg-white/70 p-2 sm:p-3" role="radiogroup" aria-labelledby="menu-title">
              <button
                v-for="item in menu"
                :key="item.amount"
                type="button"
                role="radio"
                :aria-checked="selected?.amount === item.amount && !customAmount"
                class="menu-row group"
                :class="selected?.amount === item.amount && !customAmount ? 'is-active' : ''"
                @click="choose(item)"
              >
                <span class="text-2xl leading-none" aria-hidden="true">{{ item.icon }}</span>
                <span class="min-w-0">
                  <span class="block text-[15px] font-semibold text-ink">{{ item.name }}</span>
                  <span class="block text-[13px] text-ink-muted">{{ item.note }}</span>
                </span>
                <span class="menu-leader" aria-hidden="true" />
                <span class="font-serif text-2xl italic leading-none text-ink">Bs.&nbsp;{{ item.amount }}</span>
              </button>

              <label
                class="menu-row cursor-text"
                :class="customAmount ? 'is-active' : ''"
              >
                <span class="text-2xl leading-none" aria-hidden="true">💛</span>
                <span class="min-w-0">
                  <span class="block text-[15px] font-semibold text-ink">Otro monto</span>
                  <span class="block text-[13px] text-ink-muted">Hasta Bs. 1 se agradece</span>
                </span>
                <span class="menu-leader" aria-hidden="true" />
                <span class="flex items-baseline gap-1 font-serif text-2xl italic leading-none text-ink">
                  Bs.
                  <input
                    v-model="custom"
                    inputmode="decimal"
                    placeholder="—"
                    aria-label="Otro monto en bolivianos"
                    class="w-16 border-b border-dashed border-ink/30 bg-transparent text-right font-serif text-2xl italic text-ink placeholder:text-ink-muted focus:border-accent-600 focus:outline-none"
                    @input="onCustomInput"
                  />
                </span>
              </label>
            </div>
          </section>

          <!-- En qué se va -->
          <p class="mt-6 max-w-[36rem] text-[14px] leading-relaxed text-ink-muted">
            <strong class="font-semibold text-ink-soft">¿En qué se va?</strong>
            Hosting y base de datos, las APIs de IA que extraen las preguntas, subir bancos nuevos y mantener todo
            gratis. Lo que sobre, en pollo y memes.
          </p>
        </div>

        <!-- ─── Derecha: ticket ──────────────────────────────────── -->
        <aside id="ticket" class="scroll-mt-24 lg:sticky lg:top-24" aria-label="Tu pedido">
          <div class="ticket">
            <div class="ticket-edge" aria-hidden="true" />
            <div class="ticket-body">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="font-serif text-[26px] italic leading-none text-ink">Pollería BancoPreu</p>
                  <p class="mt-1.5 font-mono text-[11px] text-ink-muted">Pedido para Isaac, el dev</p>
                </div>
                <span class="stamp" aria-hidden="true">Gracias</span>
              </div>

              <div class="ticket-rule" />

              <div class="flex items-baseline justify-between gap-3 font-mono text-[13px] text-ink">
                <span>1 × {{ lineIcon }} {{ lineName }}</span>
                <span>{{ amount ? fmt(amount) : 'a elegir' }}</span>
              </div>
              <div class="mt-2 flex items-baseline justify-between gap-3">
                <span class="font-mono text-[13px] font-semibold text-ink">Total</span>
                <span class="font-serif text-[34px] italic leading-none text-ink" aria-live="polite">
                  {{ amount ? fmt(amount) : 'Bs. —' }}
                </span>
              </div>

              <div class="ticket-rule" />

              <!-- Paso 2: pagar -->
              <h2 class="flex items-baseline gap-3">
                <span class="step-num">2</span>
                <span class="text-[15px] font-semibold text-ink">
                  {{ isTouch ? 'Guarda el QR y págalo desde tu banco' : 'Escanea con la app de tu banco' }}
                </span>
              </h2>
              <p class="mt-1.5 pl-9 text-[13px] leading-relaxed text-ink-muted">
                El QR tiene monto libre: escribe
                <strong class="font-semibold text-ink-soft">{{ amount ? fmt(amount) : 'tu aporte' }}</strong>
                al pagar.
                <template v-if="isTouch">En tu app: «Pagar con QR» → «Subir imagen».</template>
              </p>

              <div class="relative mx-auto mt-4 w-full max-w-[248px]">
                <img
                  :src="QR_IMAGE"
                  :alt="`Código QR de ${BANK} para donar a ${HOLDER}`"
                  class="w-full rounded-md bg-white p-2 ring-1 ring-ink/10"
                  :class="qrExpired ? 'opacity-20 blur-[2px]' : ''"
                  width="578"
                  height="578"
                  decoding="async"
                />
                <div
                  v-if="qrExpired"
                  class="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center"
                >
                  <p class="text-[14px] font-semibold text-ink">Este QR venció el {{ QR_VALID_LABEL }}</p>
                  <p class="text-[12px] leading-snug text-ink-soft">Transfiere al número de cuenta o pídeme uno nuevo.</p>
                  <a :href="waHelp" target="_blank" rel="noopener" class="btn-primary mt-1 py-1.5 text-[13px]">
                    <AppIcon name="message" :size="14" />
                    Pedir QR nuevo
                  </a>
                </div>
              </div>

              <div class="mt-4 grid gap-2">
                <button v-if="!qrExpired" type="button" :class="isTouch ? 'btn-primary' : 'btn-outline'" @click="saveQr">
                  <AppIcon name="download" :size="15" />
                  {{ isTouch ? 'Guardar QR en el celular' : 'Descargar QR' }}
                </button>
              </div>

              <dl class="mt-4 space-y-1 font-mono text-[12.5px]">
                <div class="ticket-field">
                  <dt class="text-ink-muted">Banco</dt>
                  <dd class="text-ink">{{ BANK }}</dd>
                </div>
                <div class="ticket-field">
                  <dt class="text-ink-muted">Titular</dt>
                  <dd class="flex items-center gap-1 text-right text-ink">
                    <span class="truncate">{{ HOLDER }}</span>
                    <button
                      type="button"
                      class="copy-btn"
                      :aria-label="copied === 'holder' ? 'Titular copiado' : 'Copiar titular'"
                      @click="copyField(HOLDER, 'holder', 'Titular')"
                    >
                      <AppIcon :name="copied === 'holder' ? 'check' : 'copy'" :size="14" />
                    </button>
                  </dd>
                </div>
                <div class="ticket-field">
                  <dt class="text-ink-muted">Cuenta</dt>
                  <dd class="flex items-center gap-1 text-ink">
                    <span class="font-semibold tracking-wide">{{ ACCOUNT }}</span>
                    <button
                      type="button"
                      class="copy-btn"
                      :aria-label="copied === 'account' ? 'Cuenta copiada' : 'Copiar número de cuenta'"
                      @click="copyField(ACCOUNT, 'account', 'Número de cuenta')"
                    >
                      <AppIcon :name="copied === 'account' ? 'check' : 'copy'" :size="14" />
                    </button>
                  </dd>
                </div>
              </dl>

              <div class="ticket-rule" />

              <!-- Paso 3: avisar -->
              <h2 class="flex items-baseline gap-3">
                <span class="step-num">3</span>
                <span class="text-[15px] font-semibold text-ink">¿Ya pagaste? Avísame</span>
              </h2>
              <a :href="waPaid" target="_blank" rel="noopener" class="btn-primary mt-3 w-full">
                <AppIcon name="message" :size="16" />
                Enviar comprobante por WhatsApp
              </a>

              <p v-if="!qrExpired" class="mt-4 text-center font-mono text-[11px] text-ink-muted">
                QR válido hasta el {{ QR_VALID_LABEL }}
              </p>
              <p class="mt-1.5 flex flex-wrap justify-center gap-x-4 gap-y-1 text-[12px]">
                <a :href="waHelp" target="_blank" rel="noopener" class="font-medium text-accent-700 hover:underline">
                  ¿Problemas para pagar?
                </a>
                <a :href="QR_RECEIPT" target="_blank" rel="noopener" class="font-medium text-ink-soft hover:underline">
                  Ver QR original del banco
                </a>
              </p>
            </div>
            <div class="ticket-edge ticket-edge--bottom" aria-hidden="true" />
          </div>
        </aside>
      </div>

      <!-- ─── Fondo de memes ─────────────────────────────────────── -->
      <section class="mt-20 grid items-center gap-10 border-t border-ink/10 pt-14 md:grid-cols-[280px_minmax(0,1fr)] md:gap-14">
        <figure class="mx-auto w-full max-w-[280px] -rotate-2 rounded-lg bg-white p-2.5 pb-3 shadow-lift ring-1 ring-ink/10">
          <img
            :src="MEME_IMAGE"
            alt="Meme de un perrito con traje: «Muchas gracias por su atención, aplaudan y no hagan preguntas»"
            class="w-full rounded"
            width="736"
            height="736"
            loading="lazy"
            decoding="async"
          />
          <figcaption class="pt-2.5 text-center font-serif text-[15px] italic text-ink-soft">Meme oficial del fondo</figcaption>
        </figure>

        <div>
          <h2 class="font-serif text-[clamp(2rem,4vw,2.75rem)] italic leading-tight">El Fondo Oficial de Memes</h2>
          <p class="mt-3 max-w-[34rem] text-[15px] leading-relaxed text-ink-soft">
            Estudiar Física a las 2 a.&nbsp;m. duele menos con memes. Si tienes uno bueno sobre la preu, el examen de
            admisión o el profe que no explica, mándamelo: los mejores aparecen por aquí.
          </p>
          <a :href="waMeme" target="_blank" rel="noopener" class="btn-outline mt-5">
            <AppIcon name="message" :size="16" />
            Mandar un meme
          </a>
        </div>
      </section>
    </main>

    <AppFooter narrow />
    <ToastHost />

    <!-- Móvil: barra de pago fija hasta llegar al ticket -->
    <Transition
      enter-from-class="translate-y-full"
      leave-to-class="translate-y-full"
      enter-active-class="transition-transform duration-200 motion-reduce:transition-none"
      leave-active-class="transition-transform duration-200 motion-reduce:transition-none"
    >
      <div
        v-if="!ticketVisible"
        class="fixed inset-x-0 bottom-0 z-40 border-t border-ink/10 bg-receipt/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur lg:hidden"
      >
        <div class="mx-auto flex max-w-md items-center gap-3">
          <div class="min-w-0 flex-1">
            <p class="truncate text-[12px] text-ink-muted">{{ lineIcon }} {{ lineName }}</p>
            <p class="font-serif text-[24px] italic leading-none text-ink">{{ amount ? fmt(amount) : 'Bs. —' }}</p>
          </div>
          <button type="button" class="btn-primary" @click="goToTicket">
            <AppIcon name="heart" :size="15" />
            Pagar con QR
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.step-num {
  @apply inline-flex h-6 w-6 shrink-0 translate-y-[-2px] items-center justify-center rounded-full bg-ink font-mono text-[12px] font-medium text-white;
}

/* Menú tipo pizarra de pollería */
.menu-row {
  @apply grid w-full grid-cols-[2rem_auto_minmax(1rem,1fr)_auto] items-center gap-3 rounded-xl px-3 py-3.5 text-left transition-colors
    focus-within:outline-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500;
}
.menu-row:hover {
  @apply bg-mustard-50/70;
}
.menu-row.is-active {
  @apply bg-mustard-100/80 ring-1 ring-mustard-300;
}
.menu-leader {
  @apply h-0 self-end border-b-2 border-dotted border-ink/20;
  margin-bottom: 0.45rem;
}
@media (max-width: 420px) {
  .menu-row {
    grid-template-columns: 1.75rem minmax(0, 1fr) auto;
  }
  .menu-leader {
    display: none;
  }
}

/* Ticket de pedido */
.ticket {
  filter: drop-shadow(0 1px 0 rgba(28, 27, 25, 0.06)) drop-shadow(0 12px 28px rgba(28, 27, 25, 0.14));
}
.ticket-body {
  @apply bg-receipt px-5 pb-5 pt-4 sm:px-6;
}
.ticket-edge {
  height: 10px;
  background: radial-gradient(circle at 7px 0, transparent 6px, #fffdf7 6.5px) repeat-x;
  background-size: 14px 10px;
  transform: scaleY(-1);
}
.ticket-edge--bottom {
  transform: none;
}
.ticket-rule {
  @apply my-4 border-t-2 border-dashed border-ink/15;
}
.ticket-field {
  @apply flex items-center justify-between gap-3 py-0.5;
}
.copy-btn {
  @apply inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-ink-muted transition hover:bg-ink/5 hover:text-ink
    focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-500;
}
.stamp {
  @apply shrink-0 rotate-[-8deg] rounded border-2 border-mustard-500 px-2 py-0.5 font-serif text-[17px] italic leading-none text-mustard-700;
}

@media (prefers-reduced-motion: reduce) {
  .menu-row {
    transition: none;
  }
}
</style>
