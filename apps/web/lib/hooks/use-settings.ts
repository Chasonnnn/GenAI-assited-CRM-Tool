import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getOrgSettings, updateOrgSettings } from '@/lib/api/settings'
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
