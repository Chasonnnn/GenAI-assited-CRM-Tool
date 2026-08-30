/**
 * React Query hooks for surrogate attachments
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { attachmentsApi } from "../api/attachments"
import { toast } from "@/components/ui/toast"
import { surrogateKeys } from "./use-surrogates"
import { donorKeys } from "./use-donors"
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
            void queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId] })
            void queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId, "images"] })
            // Invalidate history/activity cache to show attachment_added immediately
            void queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(variables.surrogateId), 'activity'],
                exact: false,
            })
        },
    })
}

export function useDownloadAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (attachmentId: string) =>
            attachmentsApi.getDownloadUrl(attachmentId),
        onSuccess: (data) => {
            void queryClient.invalidateQueries({ queryKey: ["audit", "list"] })
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
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (attachmentId: string) =>
            attachmentsApi.getDownloadUrl(attachmentId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["audit", "list"] })
        },
    })
}

export function useDeleteAttachment() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ attachmentId, surrogateId: _surrogateId }: { attachmentId: string; surrogateId: string }) =>
            attachmentsApi.delete(attachmentId),
        onSuccess: (_, variables) => {
            void queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId] })
            void queryClient.invalidateQueries({ queryKey: ["attachments", variables.surrogateId, "images"] })
            // Invalidate history/activity cache to show attachment_deleted immediately
            void queryClient.invalidateQueries({
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
            void queryClient.invalidateQueries({ queryKey: ["ip-attachments", variables.ipId] })
        },
    })
}

export const donorAttachmentKeys = {
    all: ["donor-attachments"] as const,
    list: (donorId: string) => [...donorAttachmentKeys.all, donorId] as const,
}

export function useDonorAttachments(donorId: string | null) {
    return useQuery({
        queryKey: donorAttachmentKeys.list(donorId ?? ""),
        queryFn: () => attachmentsApi.listForDonor(donorId!),
        enabled: Boolean(donorId),
    })
}

export function useAttachmentPreviewUrl(attachmentId: string | null) {
    return useQuery({
        queryKey: ["attachments", "download-url", attachmentId ?? ""],
        queryFn: () => attachmentsApi.getDownloadUrl(attachmentId!),
        enabled: Boolean(attachmentId),
    })
}

function invalidateDonorAttachmentSurfaces(
    queryClient: ReturnType<typeof useQueryClient>,
    donorId: string,
) {
    void queryClient.invalidateQueries({ queryKey: donorAttachmentKeys.list(donorId) })
    void queryClient.invalidateQueries({ queryKey: donorKeys.detail(donorId) })
}

export function useUploadDonorAttachment() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ donorId, file }: { donorId: string; file: File }) =>
            attachmentsApi.uploadForDonor(donorId, file),
        onSuccess: (_, variables) => {
            invalidateDonorAttachmentSurfaces(queryClient, variables.donorId)
        },
    })
}

export function useUploadDonorProfilePhoto() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ donorId, file }: { donorId: string; file: File }) =>
            attachmentsApi.uploadDonorProfilePhoto(donorId, file),
        onSuccess: (_, variables) => {
            invalidateDonorAttachmentSurfaces(queryClient, variables.donorId)
        },
    })
}

export function useDeleteDonorAttachment() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ attachmentId }: { attachmentId: string; donorId: string }) =>
            attachmentsApi.delete(attachmentId),
        onSuccess: (_, variables) => {
            invalidateDonorAttachmentSurfaces(queryClient, variables.donorId)
        },
    })
}
