import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import * as aiStudioApi from "@/lib/api/ai-studio"
import type {
    AIStudioGenerateRequest,
    AIStudioSettingsUpdate,
} from "@/lib/api/ai-studio"

const aiStudioKeys = {
    all: ["ai-studio"] as const,
    settings: () => [...aiStudioKeys.all, "settings"] as const,
    drafts: () => [...aiStudioKeys.all, "drafts"] as const,
}

export function useAIStudioSettings() {
    return useQuery({
        queryKey: aiStudioKeys.settings(),
        queryFn: aiStudioApi.getAIStudioSettings,
        staleTime: 5 * 60 * 1000,
    })
}

export function useUpdateAIStudioSettings() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (update: AIStudioSettingsUpdate) =>
            aiStudioApi.updateAIStudioSettings(update),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: aiStudioKeys.settings() })
        },
    })
}

export function useGenerateAIStudioDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (request: AIStudioGenerateRequest) =>
            aiStudioApi.generateAIStudioDraft(request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: aiStudioKeys.drafts() })
        },
    })
}

export function useSaveAIStudioDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (draftId: string) => aiStudioApi.saveAIStudioDraft(draftId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: aiStudioKeys.drafts() })
        },
    })
}

export function useAIStudioDrafts() {
    return useQuery({
        queryKey: aiStudioKeys.drafts(),
        queryFn: aiStudioApi.listAIStudioDrafts,
        staleTime: 30 * 1000,
    })
}
