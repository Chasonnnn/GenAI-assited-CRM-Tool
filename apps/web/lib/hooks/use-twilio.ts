/** React Query hooks for organization-scoped Twilio configuration. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import * as twilioApi from "@/lib/api/twilio"
import type {
    TwilioCredentialTestRequest,
    TwilioReadiness,
    TwilioSettingsUpdate,
} from "@/lib/api/twilio"

export const twilioKeys = {
    all: ["twilio"] as const,
    settings: () => [...twilioKeys.all, "settings"] as const,
    readiness: () => [...twilioKeys.all, "readiness"] as const,
}

export const READINESS_POLL_INTERVAL_MS = 3 * 1000
/** A queued check that has not reported back by now is treated as lost; the next click requeues it. */
export const READINESS_POLL_TIMEOUT_MS = 2 * 60 * 1000

/**
 * Poll cadence while a queued provider check is outstanding.
 * Polling stops once evidence checked after `awaitingCheckSince` arrives, or after the timeout.
 */
export function readinessPollInterval(
    data: TwilioReadiness | undefined,
    awaitingCheckSince: string | null,
    now: number = Date.now(),
): number | false {
    if (!awaitingCheckSince) return false
    const queuedAt = Date.parse(awaitingCheckSince)
    if (Number.isNaN(queuedAt) || now - queuedAt > READINESS_POLL_TIMEOUT_MS) return false
    const checkedAt = data?.provider.checked_at ? Date.parse(data.provider.checked_at) : Number.NaN
    if (!Number.isNaN(checkedAt) && checkedAt >= queuedAt) return false
    return READINESS_POLL_INTERVAL_MS
}

export function useTwilioSettings(enabled = true) {
    return useQuery({
        queryKey: twilioKeys.settings(),
        queryFn: twilioApi.getTwilioSettings,
        enabled,
        staleTime: 5 * 60 * 1000,
    })
}

export function useTwilioReadiness(enabled = true, awaitingCheckSince: string | null = null) {
    return useQuery({
        queryKey: twilioKeys.readiness(),
        queryFn: twilioApi.getTwilioReadiness,
        enabled,
        staleTime: 30 * 1000,
        refetchInterval: (query) => readinessPollInterval(query.state.data, awaitingCheckSince),
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

export function useQueueTwilioReadinessCheck() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => twilioApi.queueTwilioReadinessCheck(),
        onSuccess: (response) => {
            queryClient.setQueryData(twilioKeys.readiness(), response.readiness)
        },
    })
}
