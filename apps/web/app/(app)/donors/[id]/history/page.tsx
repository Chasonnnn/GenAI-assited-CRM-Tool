"use client"

import { useParams, useSearchParams } from "next/navigation"

import { EntityActivityHistory } from "@/components/activity/EntityActivityHistory"

const DEFAULT_DONORS_LIST_PATH = "/donors"

function sanitizeReturnTo(value: string | null): string {
    if (!value || value.startsWith("//")) return DEFAULT_DONORS_LIST_PATH
    if (value === DEFAULT_DONORS_LIST_PATH || value.startsWith(`${DEFAULT_DONORS_LIST_PATH}?`)) {
        return value
    }
    return DEFAULT_DONORS_LIST_PATH
}

export default function DonorActivityHistoryPage() {
    const { id } = useParams<{ id: string }>()
    const searchParams = useSearchParams()
    const returnTo = sanitizeReturnTo(searchParams.get("return_to"))
    return (
        <EntityActivityHistory
            entityType="donor"
            entityId={id}
            backHref={`/donors/${id}?return_to=${encodeURIComponent(returnTo)}`}
        />
    )
}
