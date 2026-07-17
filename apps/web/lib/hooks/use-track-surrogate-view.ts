"use client"

import { useEffect } from "react"

import { trackSurrogateViewed } from "@/lib/workflow-metrics"

export function useTrackSurrogateView(surrogateId: string | null | undefined) {
    useEffect(() => {
        if (!surrogateId) return
        trackSurrogateViewed(surrogateId)
    }, [surrogateId])
}
