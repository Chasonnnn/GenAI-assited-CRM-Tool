import { JourneyPrintView } from "@/components/surrogates/journey/JourneyPrintView"
import type { JourneyResponse } from "@/lib/api/journey"

export const dynamic = "force-dynamic"
export const revalidate = 0

interface PageProps {
    params: Promise<{ id?: string | string[] }>
    searchParams: Promise<{ export_token?: string | string[] }>
}

async function fetchJourneyForExport(
    surrogateId: string,
    exportToken: string,
): Promise<JourneyResponse | null> {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const url = `${apiBase}/journey/surrogates/${surrogateId}/export-view?export_token=${encodeURIComponent(exportToken)}`

    const response = await fetch(url, { cache: "no-store" })
    if (!response.ok) {
        return null
    }

    return response.json()
}

export default async function JourneyPrintPage({ params, searchParams }: PageProps) {
    const resolvedParams = await params
    const resolvedSearchParams = await searchParams

    const rawId = resolvedParams.id
    const surrogateId = Array.isArray(rawId) ? rawId[0] : rawId

    const rawToken = resolvedSearchParams.export_token
    const exportToken = Array.isArray(rawToken) ? rawToken[0] : rawToken

    if (!surrogateId) {
        return (
            <div className="p-6 text-sm text-muted-foreground">
                Missing surrogate id.
            </div>
        )
    }

    if (!exportToken) {
        return (
            <div className="p-6 text-sm text-muted-foreground">
                Missing export token.
            </div>
        )
    }

    const journey = await fetchJourneyForExport(surrogateId, exportToken)
    if (!journey) {
        return (
            <div className="p-6 text-sm text-muted-foreground">
                Unable to load journey export.
            </div>
        )
    }

    return <JourneyPrintView journey={journey} />
}
