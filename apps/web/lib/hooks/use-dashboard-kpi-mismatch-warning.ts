"use client"

import { useEffect, useRef } from "react"

type DashboardKpiMismatchWarningOptions = {
    dateParams: unknown
    distributionTotal: number
    enabled: boolean
    filters: unknown
    kpiTotal: number
}

export function useDashboardKpiMismatchWarning({
    dateParams,
    distributionTotal,
    enabled,
    filters,
    kpiTotal,
}: DashboardKpiMismatchWarningOptions) {
    const lastWarningKeyRef = useRef<string | null>(null)
    const warningKey = JSON.stringify({
        dateParams,
        distributionTotal,
        filters,
        kpiTotal,
    })

    useEffect(() => {
        const delta = Math.abs(kpiTotal - distributionTotal)
        const ratio = delta / Math.max(kpiTotal || 1, 1)
        if (!enabled || delta < 5 || ratio < 0.2) {
            lastWarningKeyRef.current = null
            return
        }
        if (lastWarningKeyRef.current === warningKey) return

        lastWarningKeyRef.current = warningKey
        console.warn("[dashboard] KPI vs distribution mismatch", {
            kpiTotal,
            distributionTotal,
            filters,
            dateParams,
        })
    }, [
        dateParams,
        distributionTotal,
        enabled,
        filters,
        kpiTotal,
        warningKey,
    ])
}
