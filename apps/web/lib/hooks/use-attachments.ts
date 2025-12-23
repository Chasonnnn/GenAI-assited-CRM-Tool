/**
 * React Query hooks for case attachments
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { attachmentsApi } from "../api/attachments"

export function useAttachments(caseId: string | null) {
    return useQuery({
        queryKey: ["attachments", caseId],
        queryFn: () => attachmentsApi.list(caseId!),
        enabled: !!caseId,
    })
}

export function useUploadAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ caseId, file }: { caseId: string; file: File }) =>
            attachmentsApi.upload(caseId, file),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["attachments", variables.caseId] })
        },
    })
}

export function useDownloadAttachment() {
    return useMutation({
        mutationFn: (attachmentId: string) =>
            attachmentsApi.getDownloadUrl(attachmentId),
        onSuccess: (data) => {
            // Open download URL in new tab
            window.open(data.download_url, "_blank")
        },
    })
}

export function useDeleteAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ attachmentId, caseId }: { attachmentId: string; caseId: string }) =>
            attachmentsApi.delete(attachmentId),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["attachments", variables.caseId] })
        },
    })
}

// IP Attachment hooks
export function useIPAttachments(ipId: string | null) {
    return useQuery({
        queryKey: ["ip-attachments", ipId],
        queryFn: () => attachmentsApi.listForIP(ipId!),
        enabled: !!ipId,
    })
}

export function useUploadIPAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ ipId, file }: { ipId: string; file: File }) =>
            attachmentsApi.uploadForIP(ipId, file),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["ip-attachments", variables.ipId] })
        },
    })
}
