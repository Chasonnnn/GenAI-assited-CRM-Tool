/**
 * API client for Pipelines endpoints.
 */

import { api } from '../api';

// Types
export type StageType = 'intake' | 'post_approval' | 'terminal';

export interface PipelineStage {
    id: string;
    stage_key: string;
    slug: string;
    label: string;
    color: string;
    order: number;
    stage_type: StageType;
    is_active: boolean;
}

export interface StageCreate {
    slug: string;
    label: string;
    color: string;
    stage_type: StageType;
    order?: number;
    expected_version?: number;
}

export interface StageUpdate {
    slug?: string;
    label?: string;
    color?: string;
    order?: number;
    expected_version?: number;
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
    expected_version?: number;
    comment?: string;
}

export interface PipelineVersion {
    id: string;
    version: number;
    payload: {
        name: string;
        stages: Array<{
            stage_key: string;
            slug: string;
            label: string;
            color: string;
            order: number;
            stage_type: StageType;
            is_active: boolean;
        }>;
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

export async function getDefaultPipeline(): Promise<Pipeline> {
    return api.get<Pipeline>('/settings/pipelines/default');
}

export async function getPipeline(id: string): Promise<Pipeline> {
    return api.get<Pipeline>(`/settings/pipelines/${id}`);
}

export async function createPipeline(name: string, stages?: StageCreate[]): Promise<Pipeline> {
    return api.post<Pipeline>('/settings/pipelines', { name, stages });
}

export async function updatePipeline(id: string, data: PipelineUpdate): Promise<Pipeline> {
    return api.patch<Pipeline>(`/settings/pipelines/${id}`, data);
}

export async function deletePipeline(id: string): Promise<void> {
    return api.delete(`/settings/pipelines/${id}`);
}

// ============================================================================
// Stage CRUD API
// ============================================================================

export async function listStages(pipelineId: string, includeInactive = false): Promise<PipelineStage[]> {
    const params = new URLSearchParams();
    if (includeInactive) params.set('include_inactive', 'true');
    const query = params.toString();
    return api.get<PipelineStage[]>(`/settings/pipelines/${pipelineId}/stages${query ? `?${query}` : ''}`);
}

export async function createStage(pipelineId: string, data: StageCreate): Promise<PipelineStage> {
    return api.post<PipelineStage>(`/settings/pipelines/${pipelineId}/stages`, data);
}

export async function updateStage(pipelineId: string, stageId: string, data: StageUpdate): Promise<PipelineStage> {
    return api.put<PipelineStage>(`/settings/pipelines/${pipelineId}/stages/${stageId}`, data);
}

export async function deleteStage(
    pipelineId: string,
    stageId: string,
    migrateToStageId: string,
    expectedVersion?: number,
): Promise<{ deleted: boolean; migrated_surrogates: number }> {
    return api.delete<{ deleted: boolean; migrated_surrogates: number }>(
        `/settings/pipelines/${pipelineId}/stages/${stageId}`,
        { body: { migrate_to_stage_id: migrateToStageId, expected_version: expectedVersion } }
    );
}

export async function reorderStages(
    pipelineId: string,
    orderedStageIds: string[],
    expectedVersion?: number
): Promise<PipelineStage[]> {
    return api.put<PipelineStage[]>(`/settings/pipelines/${pipelineId}/stages/reorder`, {
        ordered_stage_ids: orderedStageIds,
        expected_version: expectedVersion,
    });
}

// ============================================================================
// Version History API
// ============================================================================

export async function getPipelineVersions(id: string): Promise<PipelineVersion[]> {
    const response = await api.get<PipelineVersionsResponse>(`/settings/pipelines/${id}/versions`);
    return response?.versions ?? [];
}

export async function rollbackPipeline(id: string, version: number): Promise<Pipeline> {
    return api.post<Pipeline>(`/settings/pipelines/${id}/rollback`, { target_version: version });
}
