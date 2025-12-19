/**
 * API client for Pipelines endpoints.
 */

import { api } from '../api';

// Types
export interface PipelineStage {
    status: string;
    label: string;
    color: string;
}

export interface Pipeline {
    id: string;
    name: string;
    is_default: boolean;
    stages: PipelineStage[];
    current_version: number;
    created_at: string;
    updated_at: string;
}

export interface PipelineUpdate {
    name?: string;
    stages?: PipelineStage[];
    expected_version?: number;
    comment?: string;
}

export interface PipelineVersion {
    id: string;
    version: number;
    payload: {
        name: string;
        stages: PipelineStage[];
    };
    comment: string | null;
    created_by_user_id: string | null;
    created_at: string;
}

export interface PipelineVersionsResponse {
    versions: PipelineVersion[];
}

// ============================================================================
// Pipelines API
// ============================================================================

export async function listPipelines(): Promise<Pipeline[]> {
    return api.get<Pipeline[]>('/settings/pipelines');
}

export async function getPipeline(id: string): Promise<Pipeline> {
    return api.get<Pipeline>(`/settings/pipelines/${id}`);
}

export async function createPipeline(name: string, stages?: PipelineStage[]): Promise<Pipeline> {
    return api.post<Pipeline>('/settings/pipelines', { name, stages });
}

export async function updatePipeline(id: string, data: PipelineUpdate): Promise<Pipeline> {
    return api.patch<Pipeline>(`/settings/pipelines/${id}`, data);
}

export async function deletePipeline(id: string): Promise<void> {
    return api.delete(`/settings/pipelines/${id}`);
}

// ============================================================================
// Version History API
// ============================================================================

export async function getPipelineVersions(id: string): Promise<PipelineVersion[]> {
    const response = await api.get<PipelineVersionsResponse>(`/settings/pipelines/${id}/versions`);
    return response.versions;
}

export async function rollbackPipeline(id: string, version: number): Promise<Pipeline> {
    return api.post<Pipeline>(`/settings/pipelines/${id}/rollback`, { target_version: version });
}
