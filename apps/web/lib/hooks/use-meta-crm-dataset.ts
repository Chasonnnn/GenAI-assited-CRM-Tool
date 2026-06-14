import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as metaCrmDatasetApi from '../api/meta-crm-dataset'

const metaCrmDatasetKeys = {
    all: ['meta-crm-dataset'] as const,
    settings: () => [...metaCrmDatasetKeys.all, 'settings'] as const,
    eventsSummary: (windowHours: number) =>
        [...metaCrmDatasetKeys.all, 'events-summary', windowHours] as const,
    events: (params: metaCrmDatasetApi.MetaCrmDatasetEventsRequest) =>
        [...metaCrmDatasetKeys.all, 'events', params] as const,
}

export function useMetaCrmDatasetSettings(enabled = true) {
    return useQuery({
        queryKey: metaCrmDatasetKeys.settings(),
        queryFn: metaCrmDatasetApi.getMetaCrmDatasetSettings,
        enabled,
    })
}

export function useUpdateMetaCrmDatasetSettings() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: metaCrmDatasetApi.updateMetaCrmDatasetSettings,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaCrmDatasetKeys.settings() })
        },
    })
}

export function useMetaCrmDatasetOutboundTest() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: metaCrmDatasetApi.sendMetaCrmDatasetOutboundTest,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaCrmDatasetKeys.eventsSummary(24) })
            void queryClient.invalidateQueries({ queryKey: metaCrmDatasetKeys.all })
        },
    })
}

export function useMetaCrmDatasetEventsSummary(windowHours = 24) {
    return useQuery({
        queryKey: metaCrmDatasetKeys.eventsSummary(windowHours),
        queryFn: () => metaCrmDatasetApi.getMetaCrmDatasetEventsSummary(windowHours),
    })
}

export function useMetaCrmDatasetEvents(
    params: metaCrmDatasetApi.MetaCrmDatasetEventsRequest = {},
) {
    return useQuery({
        queryKey: metaCrmDatasetKeys.events(params),
        queryFn: () => metaCrmDatasetApi.getMetaCrmDatasetEvents(params),
    })
}

export function useRetryMetaCrmDatasetEvent() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({
            eventId,
            payload,
        }: {
            eventId: string
            payload?: metaCrmDatasetApi.RetryMetaCrmDatasetEventRequest
        }) => metaCrmDatasetApi.retryMetaCrmDatasetEvent(eventId, payload),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaCrmDatasetKeys.eventsSummary(24) })
            void queryClient.invalidateQueries({ queryKey: metaCrmDatasetKeys.all })
        },
    })
}
