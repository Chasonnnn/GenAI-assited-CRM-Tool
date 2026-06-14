import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as zapierApi from '../api/zapier';
import { metaFormsKeys } from './use-meta-forms';
import { invalidateSurrogateCrmCaches, surrogateKeys } from './use-surrogates';

export const zapierKeys = {
    all: ['zapier'] as const,
    settings: () => [...zapierKeys.all, 'settings'] as const,
    outboundEventsSummary: (windowHours: number) =>
        [...zapierKeys.all, 'outbound-events-summary', windowHours] as const,
    outboundEvents: (params: zapierApi.ZapierOutboundEventsRequest) =>
        [...zapierKeys.all, 'outbound-events', params] as const,
};

export function useZapierSettings(enabled = true) {
    return useQuery({
        queryKey: zapierKeys.settings(),
        queryFn: zapierApi.getZapierSettings,
        enabled,
    });
}

export function useCreateZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.createZapierInboundWebhook,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useRotateZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ webhookId }: { webhookId: string }) =>
            zapierApi.rotateZapierInboundWebhookSecret(webhookId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useUpdateZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ webhookId, payload }: { webhookId: string; payload: zapierApi.ZapierInboundWebhookUpdateRequest }) =>
            zapierApi.updateZapierInboundWebhook(webhookId, payload),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useDeleteZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ webhookId }: { webhookId: string }) =>
            zapierApi.deleteZapierInboundWebhook(webhookId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useUpdateZapierOutboundSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.updateZapierOutboundSettings,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useZapierTestLead() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: zapierApi.sendZapierTestLead,
        onSuccess: (result) => {
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.intelligentSummary() });
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.all });
            if (result.surrogate_id) {
                invalidateSurrogateCrmCaches(queryClient, result.surrogate_id);
            }
        },
    });
}

export function useZapierOutboundTest() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: zapierApi.sendZapierOutboundTest,
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: [...zapierKeys.all, 'outbound-events'],
                exact: false,
            });
            void queryClient.invalidateQueries({
                queryKey: [...zapierKeys.all, 'outbound-events-summary'],
                exact: false,
            });
        },
    });
}

export function useZapierOutboundEventsSummary(windowHours = 24) {
    return useQuery({
        queryKey: zapierKeys.outboundEventsSummary(windowHours),
        queryFn: () => zapierApi.getZapierOutboundEventsSummary(windowHours),
    });
}

export function useZapierOutboundEvents(params: zapierApi.ZapierOutboundEventsRequest = {}) {
    return useQuery({
        queryKey: zapierKeys.outboundEvents(params),
        queryFn: () => zapierApi.getZapierOutboundEvents(params),
    });
}

export function useRetryZapierOutboundEvent() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({
            eventId,
            payload,
        }: {
            eventId: string;
            payload?: zapierApi.RetryZapierOutboundEventRequest;
        }) => zapierApi.retryZapierOutboundEvent(eventId, payload),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.outboundEventsSummary(24) });
            void queryClient.invalidateQueries({ queryKey: [...zapierKeys.all, 'outbound-events'] });
        },
    });
}

export function useZapierFieldPaste() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.parseZapierFieldPaste,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}
