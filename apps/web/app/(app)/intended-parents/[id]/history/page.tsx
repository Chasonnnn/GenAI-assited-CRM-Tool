"use client"

import { useParams } from "next/navigation"

import { EntityActivityHistory } from "@/components/activity/EntityActivityHistory"

export default function IntendedParentActivityHistoryPage() {
    const { id } = useParams<{ id: string }>()
    return (
        <EntityActivityHistory
            entityType="intended_parent"
            entityId={id}
            backHref={`/intended-parents/${id}`}
        />
    )
}
