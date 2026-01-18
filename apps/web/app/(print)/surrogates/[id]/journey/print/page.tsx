import { JourneyPrintView } from "@/components/surrogates/journey/JourneyPrintView"
import type { JourneyResponse } from "@/lib/api/journey"

export const dynamic = "force-dynamic"
export const revalidate = 0

interface PageProps {
    params: { id: string }
    searchParams: { export_token?: string }
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
    const exportToken = searchParams.export_token
    if (!exportToken) {
        return (
            <div className="p-6 text-sm text-muted-foreground">
                Missing export token.
            </div>
        )
    }

    const journey = await fetchJourneyForExport(params.id, exportToken)
    if (!journey) {
        return (
            <div className="p-6 text-sm text-muted-foreground">
                Unable to load journey export.
            </div>
        )
    }

    return <JourneyPrintView journey={journey} />
}
