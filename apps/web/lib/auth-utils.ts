import { resolveApiBase } from '@/lib/api-base'

type LocationLike = {
  protocol: string
  hostname: string
}

export function resolveAuthApiBase(apiBase: string, location?: LocationLike): string {
  if (!location) return apiBase
  if (!apiBase.startsWith('/')) return resolveApiBase(apiBase, location)

  const { protocol, hostname } = location
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

export function getAuthApiBase(): string {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
  if (typeof window === 'undefined') return apiBase
  return resolveAuthApiBase(apiBase, window.location)
}
