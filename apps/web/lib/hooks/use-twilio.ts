/** React Query hooks for organization-scoped Twilio configuration. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import * as twilioApi from "@/lib/api/twilio"
import type {
    TwilioCredentialTestRequest,
    TwilioSettingsUpdate,
} from "@/lib/api/twilio"

export const twilioKeys = {
    all: ["twilio"] as const,
    settings: () => [...twilioKeys.all, "settings"] as const,
    readiness: () => [...twilioKeys.all, "readiness"] as const,
}

export function useTwilioSettings(enabled = true) {
    return useQuery({
        queryKey: twilioKeys.settings(),
        queryFn: twilioApi.getTwilioSettings,
        enabled,
        staleTime: 5 * 60 * 1000,
    })
}

export function useTwilioReadiness(enabled = true) {
    return useQuery({
        queryKey: twilioKeys.readiness(),
        queryFn: twilioApi.getTwilioReadiness,
        enabled,
        staleTime: 30 * 1000,
    })
}

export function useUpdateTwilioSettings() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (update: TwilioSettingsUpdate) =>
            twilioApi.updateTwilioSettings(update),
        onSuccess: (savedSettings) => {
            queryClient.setQueryData(twilioKeys.settings(), savedSettings)
            void queryClient.invalidateQueries({ queryKey: twilioKeys.settings() })
            void queryClient.invalidateQueries({ queryKey: twilioKeys.readiness() })
        },
    })
}

export function useTestTwilioCredentials() {
    return useMutation({
        mutationFn: (request: TwilioCredentialTestRequest) =>
            twilioApi.testTwilioCredentials(request),
    })
}
