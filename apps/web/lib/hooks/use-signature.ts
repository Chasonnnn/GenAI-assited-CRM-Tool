/**
 * React Query hooks for email signature
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getSignature, updateSignature, SignatureUpdate } from '@/lib/api/signature'

// Query keys
export const signatureKeys = {
    all: ['signature'] as const,
    current: () => [...signatureKeys.all, 'current'] as const,
}

// Hooks
export function useSignature() {
    return useQuery({
        queryKey: signatureKeys.current(),
        queryFn: getSignature,
    })
}

export function useUpdateSignature() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: SignatureUpdate) => updateSignature(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: signatureKeys.current() })
        },
    })
}
