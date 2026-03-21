/**
 * React Query hooks for Pipelines.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as pipelinesApi from '../api/pipelines';
import type {
    PipelineDraft,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineUpdate,
    StageCreate,
    StageUpdate,
} from '../api/pipelines';

// Query keys
export const pipelineKeys = {
    all: ['pipelines'] as const,
    list: (entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'list', entityType] as const,
    detail: (id: string, entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'detail', entityType, id] as const,
    semantics: (id: string, entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'semantics', entityType, id] as const,
    dependencyGraph: (id: string, entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'dependency-graph', entityType, id] as const,
    preview: (id: string, entityType: PipelineEntityType, draftKey: string) =>
        [...pipelineKeys.all, 'preview', entityType, id, draftKey] as const,
    recommendedDraft: (id: string, entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'recommended-draft', entityType, id] as const,
    versions: (id: string, entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'versions', entityType, id] as const,
    default: (entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'default', entityType] as const,
    defaultSemantics: (entityType: PipelineEntityType = 'surrogate') =>
        [...pipelineKeys.all, 'default-semantics', entityType] as const,
    stages: (id: string) => [...pipelineKeys.all, 'stages', id] as const,
};

// ============================================================================
// Queries
// ============================================================================

export function usePipelines(entityType: PipelineEntityType = 'surrogate') {
    return useQuery({
        queryKey: pipelineKeys.list(entityType),
        queryFn: () => pipelinesApi.listPipelinesForEntity(entityType),
    });
}

export function useDefaultPipeline(entityType: PipelineEntityType = 'surrogate') {
    return useQuery({
        queryKey: pipelineKeys.default(entityType),
        queryFn: () => pipelinesApi.getDefaultPipeline(entityType),
    });
}

export function useDefaultPipelineSemantics(entityType: PipelineEntityType = 'surrogate') {
    return useQuery({
        queryKey: pipelineKeys.defaultSemantics(entityType),
        queryFn: () => pipelinesApi.getDefaultPipelineSemantics(entityType),
    });
}

export function usePipeline(id: string | null, entityType: PipelineEntityType = 'surrogate') {
    return useQuery({
        queryKey: pipelineKeys.detail(id || '', entityType),
        queryFn: () => pipelinesApi.getPipeline(id!, entityType),
        enabled: !!id,
    });
}

export function usePipelineSemantics(id: string | null, entityType: PipelineEntityType = 'surrogate') {
    return useQuery({
        queryKey: pipelineKeys.semantics(id || '', entityType),
        queryFn: () => pipelinesApi.getPipelineSemantics(id!, entityType),
        enabled: !!id,
    });
}

export function usePipelineDependencyGraph(
    id: string | null,
    entityType: PipelineEntityType = 'surrogate',
) {
    return useQuery({
        queryKey: pipelineKeys.dependencyGraph(id || '', entityType),
        queryFn: () => pipelinesApi.getPipelineDependencyGraph(id!, entityType),
        enabled: !!id,
    });
}

export function usePipelineChangePreview(
    id: string | null,
    draft: PipelineDraft | null,
    entityType: PipelineEntityType = 'surrogate',
) {
    const draftKey = draft ? JSON.stringify(draft) : '';
    return useQuery({
        queryKey: pipelineKeys.preview(id || '', entityType, draftKey),
        queryFn: () => pipelinesApi.previewPipelineChanges(id!, draft!, entityType),
        enabled: !!id && !!draft,
    });
}

export function usePipelineVersions(id: string | null, entityType: PipelineEntityType = 'surrogate') {
    return useQuery({
        queryKey: pipelineKeys.versions(id || '', entityType),
        queryFn: () => pipelinesApi.getPipelineVersions(id!, entityType),
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
            entity_type,
            stages,
            feature_config,
        }: {
            name: string;
            entity_type: PipelineEntityType;
            stages?: StageCreate[];
            feature_config?: PipelineFeatureConfig;
        }) => pipelinesApi.createPipeline(name, entity_type, stages, feature_config),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.all });
        },
    });
}

export function useUpdatePipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            id,
            data,
            entityType = 'surrogate',
        }: {
            id: string;
            data: PipelineUpdate;
            entityType?: PipelineEntityType;
        }) => pipelinesApi.updatePipeline(id, data, entityType),
        onSuccess: (_, { id, entityType = 'surrogate' }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list(entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default(entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics(entityType) });
        },
    });
}

export function useDeletePipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, entityType = 'surrogate' }: { id: string; entityType?: PipelineEntityType }) =>
            pipelinesApi.deletePipeline(id, entityType),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.all });
        },
    });
}

export function useRollbackPipeline() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            id,
            version,
            entityType = 'surrogate',
        }: {
            id: string;
            version: number;
            entityType?: PipelineEntityType;
        }) => pipelinesApi.rollbackPipeline(id, version, entityType),
        onSuccess: (_, { id, entityType = 'surrogate' }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list(entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default(entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics(entityType) });
        },
    });
}

export function useRecommendedPipelineDraft() {
    return useMutation({
        mutationFn: ({
            id,
            entityType = 'surrogate',
        }: {
            id: string;
            entityType?: PipelineEntityType;
        }) => pipelinesApi.getRecommendedPipelineDraft(id, entityType),
    });
}

export function useApplyPipelineDraft() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            id,
            data,
            entityType = 'surrogate',
        }: {
            id: string;
            data: PipelineDraft;
            entityType?: PipelineEntityType;
        }) => pipelinesApi.applyPipelineDraft(id, data, entityType),
        onSuccess: (_, { id, entityType = 'surrogate' }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.semantics(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.dependencyGraph(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id, entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list(entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.default(entityType) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.defaultSemantics(entityType) });
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
