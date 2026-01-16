const CSRF_COOKIE_NAME = 'crm_csrf'
const CSRF_HEADER = 'X-CSRF-Token'

export function getCsrfToken(): string | null {
    if (typeof document === 'undefined') return null
    const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`))
    return match ? decodeURIComponent(match[1]) : null
}

export function getCsrfHeaders(): Record<string, string> {
    const token = getCsrfToken()
    return token ? { [CSRF_HEADER]: token } : {}
}

export { CSRF_HEADER }
