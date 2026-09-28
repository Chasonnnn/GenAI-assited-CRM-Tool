// Same allowlist as the embed loader (app/embed/forms.v1.js/route.ts). The loader is a standalone
// script served to third-party pages, so it cannot import this list.
const ATTRIBUTION_QUERY_KEYS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ad_id",
    "adset_id",
    "campaign_id",
    "fbclid",
    "fbc",
    "fbp",
] as const

export type HostedIntakeAttribution = Record<string, string>

type StoredAttribution = {
    query: HostedIntakeAttribution
    attribution: HostedIntakeAttribution
}

function getStorageKey(slug: string): string {
    return `intake-attribution:${slug}`
}

function isStringRecord(value: unknown): value is HostedIntakeAttribution {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false
    return Object.values(value).every((item) => typeof item === "string")
}

function readStoredAttribution(slug: string): StoredAttribution | null {
    try {
        const raw = window.localStorage.getItem(getStorageKey(slug))
        if (!raw) return null
        const parsed: unknown = JSON.parse(raw)
        if (!parsed || typeof parsed !== "object") return null
        const { query, attribution } = parsed as Record<string, unknown>
        return isStringRecord(query) && isStringRecord(attribution) ? { query, attribution } : null
    } catch {
        return null
    }
}

function readQueryAttribution(): HostedIntakeAttribution {
    const params = new URLSearchParams(window.location.search)
    const query: HostedIntakeAttribution = {}
    for (const key of ATTRIBUTION_QUERY_KEYS) {
        const value = params.get(key)
        if (value) query[key] = value
    }
    return query
}

function readReferrer(): string | null {
    if (!document.referrer) return null
    try {
        const referrerUrl = new URL(document.referrer)
        return referrerUrl.origin + referrerUrl.pathname
    } catch {
        return null
    }
}

function isSameQuery(left: HostedIntakeAttribution, right: HostedIntakeAttribution): boolean {
    const leftKeys = Object.keys(left)
    return leftKeys.length === Object.keys(right).length && leftKeys.every((key) => left[key] === right[key])
}

/**
 * Returns the landing attribution for this hosted link and keeps it in local storage, so a draft
 * finished after a reload or a later visit still reports the original ad click. A visit that
 * brings new query values replaces the stored attribution.
 */
export function captureHostedIntakeAttribution(slug: string): HostedIntakeAttribution {
    if (typeof window === "undefined" || !slug) return {}
    const query = readQueryAttribution()
    const stored = readStoredAttribution(slug)
    if (stored && (Object.keys(query).length === 0 || isSameQuery(stored.query, query))) {
        return stored.attribution
    }

    const attribution: HostedIntakeAttribution = { ...query }
    // Meta's fbc format is fb.1.<creation time in milliseconds>.<fbclid>.
    if (attribution.fbclid && !attribution.fbc) {
        attribution.fbc = `fb.1.${Date.now()}.${attribution.fbclid}`
    }
    const referrer = readReferrer()
    if (referrer) attribution.referrer = referrer
    attribution.landing_url = window.location.href.split("#")[0] ?? window.location.href
    try {
        window.localStorage.setItem(getStorageKey(slug), JSON.stringify({ query, attribution }))
    } catch {
        // Without storage the attribution is read again from the page URL at submit.
    }
    return attribution
}

export function clearHostedIntakeAttribution(slug: string): void {
    try {
        window.localStorage.removeItem(getStorageKey(slug))
    } catch {
        // The server has already stored this attribution with the submission.
    }
}
