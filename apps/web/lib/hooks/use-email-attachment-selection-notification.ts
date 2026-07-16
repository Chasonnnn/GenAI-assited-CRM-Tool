"use client"

import { useEffect, useEffectEvent } from "react"

export interface EmailAttachmentSelectionState {
    selectedAttachmentIds: string[]
    hasBlockingAttachments: boolean
    totalBytes: number
    errorMessage: string | null
}

type EmailAttachmentSelectionNotificationOptions = EmailAttachmentSelectionState & {
    onSelectionChange: (state: EmailAttachmentSelectionState) => void
}

export function useEmailAttachmentSelectionNotification({
    selectedAttachmentIds,
    hasBlockingAttachments,
    totalBytes,
    errorMessage,
    onSelectionChange,
}: EmailAttachmentSelectionNotificationOptions) {
    const notifySelectionChange = useEffectEvent(onSelectionChange)

    useEffect(() => {
        notifySelectionChange({
            selectedAttachmentIds,
            hasBlockingAttachments,
            totalBytes,
            errorMessage,
        })
    }, [errorMessage, hasBlockingAttachments, selectedAttachmentIds, totalBytes])
}
