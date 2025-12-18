/**
 * React Query hooks for Pipelines.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as pipelinesApi from '../api/pipelines';
import type { Pipeline, PipelineUpdate, PipelineVersion } from '../api/pipelines';

// Query keys
export const pipelineKeys = {
    all: ['pipelines'] as const,
    list: () => [...pipelineKeys.all, 'list'] as const,
    detail: (id: string) => [...pipelineKeys.all, 'detail', id] as const,
    versions: (id: string) => [...pipelineKeys.all, 'versions', id] as const,
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
        mutationFn: ({ name, stages }: { name: string; stages?: pipelinesApi.PipelineStage[] }) =>
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
