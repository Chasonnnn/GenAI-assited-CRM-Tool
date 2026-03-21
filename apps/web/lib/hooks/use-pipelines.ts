/**
 * React Query hooks for Pipelines.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as pipelinesApi from '../api/pipelines';
import type {
    PipelineDraft,
    PipelineFeatureConfig,
    PipelineUpdate,
    StageCreate,
    StageUpdate,
} from '../api/pipelines';

// Query keys
export const pipelineKeys = {
    all: ['pipelines'] as const,
    list: () => [...pipelineKeys.all, 'list'] as const,
    detail: (id: string) => [...pipelineKeys.all, 'detail', id] as const,
    semantics: (id: string) => [...pipelineKeys.all, 'semantics', id] as const,
    dependencyGraph: (id: string) => [...pipelineKeys.all, 'dependency-graph', id] as const,
    preview: (id: string, draftKey: string) => [...pipelineKeys.all, 'preview', id, draftKey] as const,
    recommendedDraft: (id: string) => [...pipelineKeys.all, 'recommended-draft', id] as const,
    versions: (id: string) => [...pipelineKeys.all, 'versions', id] as const,
    default: () => [...pipelineKeys.all, 'default'] as const,
    defaultSemantics: () => [...pipelineKeys.all, 'default-semantics'] as const,
    stages: (id: string) => [...pipelineKeys.all, 'stages', id] as const,
};

// ============================================================================
// Queries
// ============================================================================

export function usePipelines() {
    return useQuery({
        queryKey: pipelineKeys.list(),
        queryFn: pipelinesApi.listPipelines,
    });
}

export function useDefaultPipeline() {
    return useQuery({
        queryKey: pipelineKeys.default(),
        queryFn: pipelinesApi.getDefaultPipeline,
    });
}

export function useDefaultPipelineSemantics() {
    return useQuery({
        queryKey: pipelineKeys.defaultSemantics(),
        queryFn: pipelinesApi.getDefaultPipelineSemantics,
    });
}

export function usePipeline(id: string | null) {
    return useQuery({
        queryKey: pipelineKeys.detail(id || ''),
        queryFn: () => pipelinesApi.getPipeline(id!),
        enabled: !!id,
    });
}

export function usePipelineSemantics(id: string | null) {
    return useQuery({
        queryKey: pipelineKeys.semantics(id || ''),
        queryFn: () => pipelinesApi.getPipelineSemantics(id!),
        enabled: !!id,
    });
}

export function usePipelineDependencyGraph(id: string | null) {
    return useQuery({
        queryKey: pipelineKeys.dependencyGraph(id || ''),
        queryFn: () => pipelinesApi.getPipelineDependencyGraph(id!),
        enabled: !!id,
    });
}

export function usePipelineChangePreview(id: string | null, draft: PipelineDraft | null) {
    const draftKey = draft ? JSON.stringify(draft) : '';
    return useQuery({
        queryKey: pipelineKeys.preview(id || '', draftKey),
        queryFn: () => pipelinesApi.previewPipelineChanges(id!, draft!),
        enabled: !!id && !!draft,
    });
}

export function usePipelineVersions(id: string | null) {
    return useQuery({
        queryKey: pipelineKeys.versions(id || ''),
        queryFn: () => pipelinesApi.getPipelineVersions(id!),
        enabled: !!id,
    });
}

// ============================================================================
// Mutations
// ============================================================================

export function useCreatePipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            name,
            stages,
            feature_config,
        }: {
            name: string;
            stages?: StageCreate[];
            feature_config?: PipelineFeatureConfig;
        }) => pipelinesApi.createPipeline(name, stages, feature_config),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.all });
        },
    });
}

export function useUpdatePipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: PipelineUpdate }) =>
            pipelinesApi.updatePipeline(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}

export function useDeletePipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => pipelinesApi.deletePipeline(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.all });
        },
    });
}

export function useRollbackPipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, version }: { id: string; version: number }) =>
            pipelinesApi.rollbackPipeline(id, version),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}

export function useRecommendedPipelineDraft() {
    return useMutation({
        mutationFn: (id: string) => pipelinesApi.getRecommendedPipelineDraft(id),
    });
}

export function useApplyPipelineDraft() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: PipelineDraft }) =>
            pipelinesApi.applyPipelineDraft(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.dependencyGraph(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}

// ============================================================================
// Stage Mutations
// ============================================================================

export function useCreateStage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pipelineId, data }: { pipelineId: string; data: StageCreate }) =>
            pipelinesApi.createStage(pipelineId, data),
        onSuccess: (_, { pipelineId }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}

export function useUpdateStage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pipelineId, stageId, data }: { pipelineId: string; stageId: string; data: StageUpdate }) =>
            pipelinesApi.updateStage(pipelineId, stageId, data),
        onSuccess: (_, { pipelineId }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}

export function useDeleteStage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            pipelineId,
            stageId,
            migrateToStageId,
            expectedVersion,
        }: {
            pipelineId: string;
            stageId: string;
            migrateToStageId: string;
            expectedVersion?: number;
        }) =>
            pipelinesApi.deleteStage(pipelineId, stageId, migrateToStageId, expectedVersion),
        onSuccess: (_, { pipelineId }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}

export function useReorderStages() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            pipelineId,
            orderedStageIds,
            expectedVersion,
        }: {
            pipelineId: string;
            orderedStageIds: string[];
            expectedVersion?: number;
        }) =>
            pipelinesApi.reorderStages(pipelineId, orderedStageIds, expectedVersion),
        onSuccess: (_, { pipelineId }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics() });
        },
    });
}
