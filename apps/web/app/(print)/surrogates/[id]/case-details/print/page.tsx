import type { Metadata } from "next"
import { headers } from "next/headers"

import { CaseDetailsPrintView } from "@/components/surrogates/detail/print/CaseDetailsPrintView"
import type { SurrogateCaseDetailsExportView } from "@/lib/api/surrogates"
import { buildServerApiHeaders } from "@/lib/server-api-headers"

export const dynamic = "force-dynamic"
export const revalidate = 0
export const metadata: Metadata = {
    title: "Case Details Print",
    description: "Printable surrogate case details.",
    robots: {
        index: false,
        follow: false,
    },
}

interface PageProps {
    params: Promise<{ id?: string | string[] }>
    searchParams: Promise<{ export_token?: string | string[] }>
}

async function fetchCaseDetailsForExport(
    surrogateId: string,
    exportToken: string,
): Promise<SurrogateCaseDetailsExportView | null> {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const url = `${apiBase}/surrogates/${surrogateId}/export-view?export_token=${encodeURIComponent(exportToken)}`
    const requestHeaders = await headers()

    const response = await fetch(url, {
        cache: "no-store",
        headers: buildServerApiHeaders(requestHeaders),
    })
    if (!response.ok) {
        return null
    }
    return response.json()
}

export default async function CaseDetailsPrintPage({ params, searchParams }: PageProps) {
    const resolvedParams = await params
    const resolvedSearchParams = await searchParams

    const rawId = resolvedParams.id
    const surrogateId = Array.isArray(rawId) ? rawId[0] : rawId

    const rawToken = resolvedSearchParams.export_token
    const exportToken = Array.isArray(rawToken) ? rawToken[0] : rawToken

    if (!surrogateId) {
        return <div className="p-6 text-sm text-muted-foreground">Missing surrogate id.</div>
    }
    if (!exportToken) {
        return <div className="p-6 text-sm text-muted-foreground">Missing export token.</div>
    }

    const data = await fetchCaseDetailsForExport(surrogateId, exportToken)
    if (!data) {
        return (
            <div className="p-6 text-sm text-muted-foreground">
                Unable to load case details export.
            </div>
        )
    }

    return <CaseDetailsPrintView data={data} />
}
