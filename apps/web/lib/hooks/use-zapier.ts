import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as zapierApi from '../api/zapier';

export const zapierKeys = {
    all: ['zapier'] as const,
    settings: () => [...zapierKeys.all, 'settings'] as const,
    outboundEventsSummary: (windowHours: number) =>
        [...zapierKeys.all, 'outbound-events-summary', windowHours] as const,
    outboundEvents: (params: zapierApi.ZapierOutboundEventsRequest) =>
        [...zapierKeys.all, 'outbound-events', params] as const,
};

export function useZapierSettings() {
    return useQuery({
        queryKey: zapierKeys.settings(),
        queryFn: zapierApi.getZapierSettings,
    });
}

export function useRotateZapierSecret() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.rotateZapierSecret,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useCreateZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.createZapierInboundWebhook,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useRotateZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ webhookId }: { webhookId: string }) =>
            zapierApi.rotateZapierInboundWebhookSecret(webhookId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useUpdateZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ webhookId, payload }: { webhookId: string; payload: zapierApi.ZapierInboundWebhookUpdateRequest }) =>
            zapierApi.updateZapierInboundWebhook(webhookId, payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useDeleteZapierInboundWebhook() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ webhookId }: { webhookId: string }) =>
            zapierApi.deleteZapierInboundWebhook(webhookId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useUpdateZapierOutboundSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.updateZapierOutboundSettings,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}

export function useZapierTestLead() {
    return useMutation({
        mutationFn: zapierApi.sendZapierTestLead,
    });
}

export function useZapierOutboundTest() {
    return useMutation({
        mutationFn: zapierApi.sendZapierOutboundTest,
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
            queryClient.invalidateQueries({ queryKey: zapierKeys.outboundEventsSummary(24) });
            queryClient.invalidateQueries({ queryKey: [...zapierKeys.all, 'outbound-events'] });
        },
    });
}

export function useZapierFieldPaste() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: zapierApi.parseZapierFieldPaste,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: zapierKeys.settings() });
        },
    });
}
