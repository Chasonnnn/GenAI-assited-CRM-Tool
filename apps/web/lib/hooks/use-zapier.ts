import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as zapierApi from '../api/zapier';

export const zapierKeys = {
    all: ['zapier'] as const,
    settings: () => [...zapierKeys.all, 'settings'] as const,
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
