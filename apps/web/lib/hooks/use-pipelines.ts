/**
 * React Query hooks for Pipelines.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as pipelinesApi from '../api/pipelines';
import type {
    Pipeline,
    PipelineUpdate,
    PipelineVersion,
    StageCreate,
    StageUpdate,
} from '../api/pipelines';

// Query keys
export const pipelineKeys = {
    all: ['pipelines'] as const,
    list: () => [...pipelineKeys.all, 'list'] as const,
    detail: (id: string) => [...pipelineKeys.all, 'detail', id] as const,
    versions: (id: string) => [...pipelineKeys.all, 'versions', id] as const,
    default: () => [...pipelineKeys.all, 'default'] as const,
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

export function usePipeline(id: string | null) {
    return useQuery({
        queryKey: pipelineKeys.detail(id || ''),
        queryFn: () => pipelinesApi.getPipeline(id!),
        enabled: !!id,
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
        mutationFn: ({ name, stages }: { name: string; stages?: StageCreate[] }) =>
            pipelinesApi.createPipeline(name, stages),
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
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
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
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(id) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
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
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
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
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
        },
    });
}

export function useDeleteStage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pipelineId, stageId, migrateToStageId }: { pipelineId: string; stageId: string; migrateToStageId: string }) =>
            pipelinesApi.deleteStage(pipelineId, stageId, migrateToStageId),
        onSuccess: (_, { pipelineId }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.list() });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
        },
    });
}

export function useReorderStages() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ pipelineId, orderedStageIds }: { pipelineId: string; orderedStageIds: string[] }) =>
            pipelinesApi.reorderStages(pipelineId, orderedStageIds),
        onSuccess: (_, { pipelineId }) => {
            queryClient.invalidateQueries({ queryKey: pipelineKeys.detail(pipelineId) });
            queryClient.invalidateQueries({ queryKey: pipelineKeys.versions(pipelineId) });
        },
    });
}
