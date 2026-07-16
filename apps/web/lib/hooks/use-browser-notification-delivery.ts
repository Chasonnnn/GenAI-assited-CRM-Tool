"use client"

import { useEffect, useRef } from "react"

import type { NotificationPermission } from "@/lib/hooks/use-browser-notifications"

type BrowserNotificationSource = {
    id?: string | null
    title?: string | null
    body?: string | null
    entity_type?: string | null
    entity_id?: string | null
    type?: string | null
}

type ShowBrowserNotification = (
    title: string,
    options?: {
        body?: string
        icon?: string
        tag?: string
        entityType?: string
        entityId?: string
        notificationType?: string
    },
) => unknown

export function useBrowserNotificationDelivery({
    latest,
    permission,
    showNotification,
}: {
    latest: BrowserNotificationSource | null
    permission: NotificationPermission
    showNotification: ShowBrowserNotification
}) {
    const lastDeliveredIdRef = useRef<string | null>(null)

    useEffect(() => {
        if (!latest?.id) return
        if (latest.id === lastDeliveredIdRef.current) return
        if (permission !== "granted") return
        if (typeof document === "undefined" || !document.hidden) return

        lastDeliveredIdRef.current = latest.id
        showNotification(latest.title || "New notification", {
            tag: latest.id,
            ...(latest.body ? { body: latest.body } : {}),
            ...(latest.entity_type ? { entityType: latest.entity_type } : {}),
            ...(latest.entity_id ? { entityId: latest.entity_id } : {}),
            ...(latest.type ? { notificationType: latest.type } : {}),
        })
    }, [latest, permission, showNotification])
}
