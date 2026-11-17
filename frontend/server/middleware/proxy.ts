/**
 * Reenvía /api/** y /storage/** al backend FastAPI. Así el navegador habla con un
 * único origen (sin CORS) y la URL del backend se configura en tiempo de ejecución
 * con NUXT_BACKEND_URL.
 */
export default defineEventHandler((event) => {
  const path = event.path || '/'
  if (!path.startsWith('/api/') && path !== '/api' && !path.startsWith('/storage/')) return

  const { backendUrl } = useRuntimeConfig(event)
  return proxyRequest(event, `${String(backendUrl).replace(/\/$/, '')}${path}`)
})
