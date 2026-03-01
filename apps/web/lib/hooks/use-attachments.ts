/**
 * React Query hooks for surrogate attachments
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { attachmentsApi } from "../api/attachments"
import { toast } from "sonner"
import { surrogateKeys } from "./use-surrogates"
import { openDownloadUrlWithSpreadsheetWarning } from "@/lib/utils/csv-download-warning"

export function useAttachments(surrogateId: string | null) {
    return useQuery({
        queryKey: ["attachments", surrogateId],
        queryFn: () => attachmentsApi.list(surrogateId!),
        enabled: !!surrogateId,
    })
}

/**
 * Fetch only image attachments for a surrogate (for journey featured image selection)
 */
export function useImageAttachments(surrogateId: string | null) {
    return useQuery({
        queryKey: ["attachments", surrogateId, "images"],
        queryFn: () => attachmentsApi.list(surrogateId!, "image"),
        enabled: !!surrogateId,
    })
}

export function useUploadAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ surrogateId, file }: { surrogateId: string; file: File }) =>
            attachmentsApi.upload(surrogateId, file),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId] })
            queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId, "images"] })
            // Invalidate history/activity cache to show attachment_added immediately
            queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(variables.surrogateId), 'activity'],
                exact: false,
            })
        },
    })
}

export function useDownloadAttachment() {
    return useMutation({
        mutationFn: (attachmentId: string) =>
            attachmentsApi.getDownloadUrl(attachmentId),
        onSuccess: (data) => {
            const opened = openDownloadUrlWithSpreadsheetWarning(
                data.download_url,
                data.filename,
            )
            if (!opened) {
                toast.info(`Download cancelled for ${data.filename}`)
            }
        },
        onError: (error: Error) => {
            toast.error("Download failed", {
                description: error.message || "Unable to download file. Please try again.",
            })
        },
    })
}

/**
 * Fetch signed download URL without opening a new tab.
 * Useful for image previews.
 */
export function useAttachmentDownloadUrl() {
    return useMutation({
        mutationFn: (attachmentId: string) =>
            attachmentsApi.getDownloadUrl(attachmentId),
    })
}

export function useDeleteAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ attachmentId, surrogateId: _surrogateId }: { attachmentId: string; surrogateId: string }) =>
            attachmentsApi.delete(attachmentId),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId] })
            queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId, "images"] })
            // Invalidate history/activity cache to show attachment_deleted immediately
            queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(variables.surrogateId), 'activity'],
                exact: false,
            })
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
