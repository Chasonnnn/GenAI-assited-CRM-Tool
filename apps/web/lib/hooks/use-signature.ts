/**
 * React Query hooks for email signature (enhanced)
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    getUserSignature,
    updateUserSignature,
    getSignaturePreview,
    uploadSignaturePhoto,
    deleteSignaturePhoto,
    getOrgSignature,
    updateOrgSignature,
    uploadOrgLogo,
    deleteOrgLogo,
    getOrgSignaturePreview,
    UserSignatureUpdate,
    OrgSignatureUpdate,
} from '@/lib/api/signature'

// =============================================================================
// Query Keys
// =============================================================================

export const signatureKeys = {
    all: ['signature'] as const,
    user: () => [...signatureKeys.all, 'user'] as const,
    preview: () => [...signatureKeys.all, 'preview'] as const,
    org: () => [...signatureKeys.all, 'org'] as const,
    orgPreview: () => [...signatureKeys.all, 'org-preview'] as const,
}

// =============================================================================
// User Hooks
// =============================================================================

export function useUserSignature() {
    return useQuery({
        queryKey: signatureKeys.user(),
        queryFn: getUserSignature,
    })
}

export function useUpdateUserSignature() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: UserSignatureUpdate) => updateUserSignature(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.user() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.preview() })
        },
    })
}

export function useSignaturePreview() {
    return useQuery({
        queryKey: signatureKeys.preview(),
        queryFn: getSignaturePreview,
    })
}

export function useUploadSignaturePhoto() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (file: File) => uploadSignaturePhoto(file),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.user() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.preview() })
        },
    })
}

export function useDeleteSignaturePhoto() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: () => deleteSignaturePhoto(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.user() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.preview() })
        },
    })
}

// =============================================================================
// Admin Hooks (org signature settings)
// =============================================================================

export function useOrgSignature() {
    return useQuery({
        queryKey: signatureKeys.org(),
        queryFn: getOrgSignature,
    })
}

export function useUpdateOrgSignature() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: OrgSignatureUpdate) => updateOrgSignature(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.org() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.preview() })
        },
    })
}

export function useUploadOrgLogo() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (file: File) => uploadOrgLogo(file),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.org() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.preview() })
        },
    })
}

export function useDeleteOrgLogo() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: () => deleteOrgLogo(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.org() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.preview() })
            queryClient.invalidateQueries({ queryKey: signatureKeys.orgPreview() })
        },
    })
}

export function useOrgSignaturePreview(options: { enabled?: boolean; mode?: "org_only"; template?: string } = {}) {
    const { enabled = false, mode, template } = options
    return useQuery({
        queryKey: [...signatureKeys.orgPreview(), mode ?? "default", template ?? "default"],
        queryFn: () => getOrgSignaturePreview(template, mode),
        enabled,
    })
}
