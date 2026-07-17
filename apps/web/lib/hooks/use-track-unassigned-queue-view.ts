import { useEffect } from "react"

import { trackUnassignedQueueViewed } from "@/lib/workflow-metrics"

export function useTrackUnassignedQueueView(enabled: boolean) {
    useEffect(() => {
        if (!enabled) return
        trackUnassignedQueueViewed()
    }, [enabled])
}
