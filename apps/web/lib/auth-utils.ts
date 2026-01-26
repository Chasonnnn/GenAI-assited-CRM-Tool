export function getAuthApiBase(): string {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
  if (typeof window === 'undefined') return apiBase
  if (!apiBase.startsWith('/')) return apiBase

  const { protocol, hostname } = window.location
  if (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.endsWith('.localhost') ||
    hostname.endsWith('.test')
  ) {
    return apiBase
  }

  const parts = hostname.split('.')
  if (parts.length < 2) return apiBase
  const baseDomain = parts.slice(1).join('.')
  return `${protocol}//api.${baseDomain}`
}
