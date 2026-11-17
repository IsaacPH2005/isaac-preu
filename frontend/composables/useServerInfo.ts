interface HealthResponse {
  status: string
  gemini_configured: boolean
  gemini_keys: number
  allow_uploads: boolean
  solutions_enabled?: boolean
}

/** Configuración del backend (p. ej. modo solo lectura en producción). */
export function useServerInfo() {
  const info = useState<HealthResponse | null>('server-info', () => null)
  // Mientras no se sepa, se asume solo lectura para no mostrar botones que luego desaparecen.
  const allowUploads = computed(() => info.value?.allow_uploads ?? false)

  async function load() {
    try {
      info.value = await $fetch<HealthResponse>('/api/health')
    } catch {
      /* se reintenta en el próximo montaje */
    }
  }

  const solutionsEnabled = computed(() => info.value?.solutions_enabled ?? false)

  return { info, allowUploads, solutionsEnabled, load }
}
