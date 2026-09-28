import { Suspense } from "react"

import UnassignedSurrogatesPageClient from "./page.client"

type SearchParamValue = string | string[] | undefined

function getFirstSearchParam(value: SearchParamValue): string | null {
    if (Array.isArray(value)) return value[0] ?? null
    return value ?? null
}

function serializeSearchParams(searchParams: Record<string, SearchParamValue>): string {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(searchParams)) {
        if (Array.isArray(value)) {
            for (const entry of value) {
                if (entry !== undefined) params.append(key, entry)
            }
        } else if (value !== undefined) {
            params.set(key, value)
        }
    }
    return params.toString()
}

function UnassignedSurrogatesPageSkeleton() {
    return (
        <div className="flex h-full flex-col" aria-busy="true">
            <div className="flex min-h-16 items-center border-b border-border px-6">
                <div className="h-7 w-56 rounded-md bg-muted" />
            </div>
            <div className="p-6">
            <div className="rounded-lg border bg-card p-4">
                <div className="space-y-3">
                    <div className="h-12 w-full rounded-md bg-muted/70" />
                    <div className="h-12 w-full rounded-md bg-muted/60" />
                    <div className="h-12 w-full rounded-md bg-muted/50" />
                </div>
            </div>
            </div>
        </div>
    )
}

export default async function UnassignedSurrogatesPage({
    searchParams,
}: {
    searchParams: Promise<Record<string, SearchParamValue>>
}) {
    const resolvedSearchParams = await searchParams

    return (
        <Suspense fallback={<UnassignedSurrogatesPageSkeleton />}>
            <UnassignedSurrogatesPageClient
                initialPageParam={getFirstSearchParam(resolvedSearchParams.page)}
                initialSearchParams={serializeSearchParams(resolvedSearchParams)}
            />
        </Suspense>
    )
}
