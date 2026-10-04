import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth-context'
import {
    deleteOrganizationLogo,
    getOrgSettings,
    updateOrgSettings,
    uploadOrganizationLogo,
} from '@/lib/api/settings'
import type { UpdateOrgRequest } from '@/lib/api/settings'

const settingsKeys = {
    all: ['settings'] as const,
    organization: () => [...settingsKeys.all, 'organization'] as const,
}

export function useOrgSettings(options: { enabled?: boolean } = {}) {
    return useQuery({
        queryKey: settingsKeys.organization(),
        queryFn: getOrgSettings,
        enabled: options.enabled ?? true,
    })
}

export function useUpdateOrgSettings() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: UpdateOrgRequest) => updateOrgSettings(data),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: settingsKeys.organization() })
        },
    })
}

/** The sidebar reads the logo from /auth/me, so both logo mutations refresh it with the org settings. */
function useOrganizationLogoMutation<TVariables, TData>(mutationFn: (variables: TVariables) => Promise<TData>) {
    const queryClient = useQueryClient()
    const { refetch } = useAuth()

    return useMutation({
        mutationFn,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: settingsKeys.organization() })
            refetch()
        },
    })
}

export function useUploadOrganizationLogo() {
    return useOrganizationLogoMutation((file: File) => uploadOrganizationLogo(file))
}

export function useDeleteOrganizationLogo() {
    return useOrganizationLogoMutation<void, void>(() => deleteOrganizationLogo())
}
