interface PreviewRoute {
  name?: string | symbol | null
  query: Record<string, unknown>
}

const LOCAL_PREVIEW_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]'])

export function isLocalPipSettingsPreview(route: PreviewRoute): boolean {
  if (!import.meta.env.DEV || route.name !== 'PipSettingsReview' || route.query.preview !== '1') {
    return false
  }
  return typeof window !== 'undefined' && LOCAL_PREVIEW_HOSTS.has(window.location.hostname)
}
