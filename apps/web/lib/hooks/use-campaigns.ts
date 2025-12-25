/**
 * Campaign hooks using TanStack Query
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    listCampaigns,
    getCampaign,
    createCampaign,
    updateCampaign,
    deleteCampaign,
    duplicateCampaign,
    previewRecipients,
    previewFilters,
    sendCampaign,
    cancelCampaign,
    listCampaignRuns,
    getCampaignRun,
    listRunRecipients,
    listSuppressions,
    addSuppression,
    removeSuppression,
    type CampaignCreate,
    type CampaignUpdate,
    type Campaign,
    type CampaignListItem,
    type FilterCriteria,
} from "@/lib/api/campaigns";

// =============================================================================
// Query Keys
// =============================================================================

export const campaignKeys = {
    all: ["campaigns"] as const,
    lists: () => [...campaignKeys.all, "list"] as const,
    list: (filters?: { status?: string }) => [...campaignKeys.lists(), filters] as const,
    details: () => [...campaignKeys.all, "detail"] as const,
    detail: (id: string) => [...campaignKeys.details(), id] as const,
    preview: (id: string) => [...campaignKeys.detail(id), "preview"] as const,
    runs: (id: string) => [...campaignKeys.detail(id), "runs"] as const,
    run: (campaignId: string, runId: string) => [...campaignKeys.runs(campaignId), runId] as const,
    runRecipients: (campaignId: string, runId: string) =>
        [...campaignKeys.run(campaignId, runId), "recipients"] as const,
    suppressions: ["suppressions"] as const,
};

// =============================================================================
// List Campaigns
// =============================================================================

export function useCampaigns(status?: string) {
    return useQuery({
        queryKey: campaignKeys.list({ status }),
        queryFn: () => listCampaigns({ status }),
    });
}

// =============================================================================
// Campaign Detail
// =============================================================================

export function useCampaign(id: string | undefined) {
    return useQuery({
        queryKey: campaignKeys.detail(id!),
        queryFn: () => getCampaign(id!),
        enabled: !!id,
    });
}

// =============================================================================
// Campaign Preview
// =============================================================================

export function useCampaignPreview(id: string | undefined) {
    return useQuery({
        queryKey: campaignKeys.preview(id!),
        queryFn: () => previewRecipients(id!),
        enabled: !!id,
        staleTime: 30000, // 30 seconds
    });
}

/**
 * Preview recipients matching filter criteria BEFORE creating a campaign.
 * Use as a mutation since filters are provided dynamically.
 */
export function usePreviewFilters() {
    return useMutation({
        mutationFn: ({
            recipientType,
            filterCriteria,
            limit,
        }: {
            recipientType: "case" | "intended_parent";
            filterCriteria: FilterCriteria;
            limit?: number;
        }) => previewFilters(recipientType, filterCriteria, limit),
    });
}

// =============================================================================
// Campaign Runs
// =============================================================================

export function useCampaignRuns(campaignId: string | undefined) {
    return useQuery({
        queryKey: campaignKeys.runs(campaignId!),
        queryFn: () => listCampaignRuns(campaignId!),
        enabled: !!campaignId,
    });
}

export function useCampaignRun(campaignId: string | undefined, runId: string | undefined) {
    return useQuery({
        queryKey: campaignKeys.run(campaignId!, runId!),
        queryFn: () => getCampaignRun(campaignId!, runId!),
        enabled: !!campaignId && !!runId,
    });
}

export function useRunRecipients(
    campaignId: string | undefined,
    runId: string | undefined,
    params?: { status?: string; limit?: number }
) {
    return useQuery({
        queryKey: campaignKeys.runRecipients(campaignId!, runId!),
        queryFn: () => listRunRecipients(campaignId!, runId!, params),
        enabled: !!campaignId && !!runId,
    });
}

// =============================================================================
// Mutations
// =============================================================================

export function useCreateCampaign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CampaignCreate) => createCampaign(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.lists() });
        },
    });
}

export function useUpdateCampaign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: CampaignUpdate }) =>
            updateCampaign(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.detail(id) });
            queryClient.invalidateQueries({ queryKey: campaignKeys.lists() });
        },
    });
}

export function useDeleteCampaign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => deleteCampaign(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.lists() });
        },
    });
}

export function useDuplicateCampaign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => duplicateCampaign(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.lists() });
        },
    });
}

export function useSendCampaign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, sendNow = true }: { id: string; sendNow?: boolean }) =>
            sendCampaign(id, sendNow),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.detail(id) });
            queryClient.invalidateQueries({ queryKey: campaignKeys.lists() });
        },
    });
}

export function useCancelCampaign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => cancelCampaign(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.detail(id) });
            queryClient.invalidateQueries({ queryKey: campaignKeys.lists() });
        },
    });
}

// =============================================================================
// Suppressions
// =============================================================================

export function useSuppressions() {
    return useQuery({
        queryKey: campaignKeys.suppressions,
        queryFn: () => listSuppressions(),
    });
}

export function useAddSuppression() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ email, reason }: { email: string; reason?: string }) =>
            addSuppression(email, reason || "opt_out"),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.suppressions });
        },
    });
}

export function useRemoveSuppression() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (email: string) => removeSuppression(email),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: campaignKeys.suppressions });
        },
    });
}
