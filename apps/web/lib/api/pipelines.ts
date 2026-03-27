/**
 * API client for Pipelines endpoints.
 */

import { api } from '../api';

// Types
export type PipelineEntityType = 'surrogate' | 'intended_parent';
export type StageType = 'intake' | 'paused' | 'post_approval' | 'terminal';
export type StageCapabilityKey =
    | 'counts_as_contacted'
    | 'eligible_for_matching'
    | 'locks_match_state'
    | 'shows_pregnancy_tracking'
    | 'requires_delivery_details'
    | 'tracks_interview_outcome';
export type PauseBehavior = 'none' | 'resume_previous_stage';
export type TerminalOutcome = 'none' | 'lost' | 'disqualified';
export type IntegrationBucket = 'none' | 'intake' | 'qualified' | 'converted' | 'lost' | 'not_qualified';

export interface StageCapabilities {
    counts_as_contacted: boolean;
    eligible_for_matching: boolean;
    locks_match_state: boolean;
    shows_pregnancy_tracking: boolean;
    requires_delivery_details: boolean;
    tracks_interview_outcome: boolean;
}

export interface StageSemantics {
    capabilities: StageCapabilities;
    pause_behavior: PauseBehavior;
    terminal_outcome: TerminalOutcome;
    integration_bucket: IntegrationBucket;
    analytics_bucket: string | null;
    suggestion_profile_key: string | null;
    requires_reason_on_enter: boolean;
}

export interface JourneyMilestoneDefinition {
    slug: string;
    label: string;
    description: string;
    mapped_stage_keys: string[];
    is_soft: boolean;
}

export interface JourneyPhaseDefinition {
    slug: string;
    label: string;
    milestone_slugs: string[];
}

export interface RoleStageRule {
    stage_types: StageType[];
    stage_keys: string[];
    capabilities: StageCapabilityKey[];
}

export interface PipelineFeatureConfig {
    schema_version: number;
    journey: {
        phases: JourneyPhaseDefinition[];
        milestones: JourneyMilestoneDefinition[];
    };
    analytics: {
        funnel_stage_keys: string[];
        performance_stage_keys: string[];
        qualification_stage_key: string | null;
        conversion_stage_key: string | null;
    };
    role_visibility: Record<string, RoleStageRule>;
    role_mutation: Record<string, RoleStageRule>;
}

export interface PipelineStage {
    id: string;
    stage_key: string;
    slug: string;
    label: string;
    color: string;
    order: number;
    category?: StageType;
    stage_type: StageType;
    is_active: boolean;
    semantics?: StageSemantics;
    is_locked?: boolean;
    system_role?: string | null;
    lock_reason?: string | null;
    locked_fields?: string[];
}

export interface StageCreate {
    slug: string;
    label: string;
    color: string;
    category?: StageType;
    stage_type: StageType;
    semantics?: StageSemantics;
    order?: number;
    expected_version?: number;
}

export interface StageUpdate {
    slug?: string;
    label?: string;
    color?: string;
    order?: number;
    category?: StageType;
    stage_type?: StageType;
    semantics?: StageSemantics;
    expected_version?: number;
}

export interface Pipeline {
    id: string;
    entity_type: PipelineEntityType;
    name: string;
    is_default: boolean;
    stages: PipelineStage[];
    feature_config?: PipelineFeatureConfig;
    current_version: number;
    created_at: string;
    updated_at: string;
}

export interface PipelineUpdate {
    name?: string;
    feature_config?: PipelineFeatureConfig;
    expected_version?: number;
    comment?: string;
}

export interface PipelineSemanticsSnapshot {
    pipeline_id: string;
    entity_type: PipelineEntityType;
    version: number;
    feature_config?: PipelineFeatureConfig;
    stages: PipelineStage[];
}

export interface PipelineStageDependency {
    stage_id: string;
    stage_key: string;
    slug: string;
    label: string;
    category: StageType;
    stage_type: StageType;
    is_active: boolean;
    surrogate_count: number;
    journey_milestone_slugs: string[];
    analytics_funnel: boolean;
    intelligent_suggestion_rules: Array<{
        id: string;
        name: string;
        enabled: boolean;
    }>;
    integration_refs: string[];
    campaign_refs: Array<{
        id: string;
        name: string;
        status: string;
        reference_modes: string[];
    }>;
    workflow_refs: Array<{
        id: string;
        name: string;
        scope: string;
        is_enabled: boolean;
        reference_paths: string[];
    }>;
    role_visibility_roles: string[];
    role_mutation_roles: string[];
}

export interface PipelineDependencyGraph {
    pipeline_id: string;
    entity_type: PipelineEntityType;
    version: number;
    stages: PipelineStageDependency[];
}

export interface PipelineDraftStage {
    id?: string;
    stage_key?: string;
    slug: string;
    label: string;
    color: string;
    order?: number;
    category?: StageType;
    stage_type?: StageType;
    is_active?: boolean;
    semantics?: StageSemantics;
}

export interface PipelineStageRemap {
    removed_stage_key: string;
    target_stage_key?: string | null;
}

export interface PipelineDraft {
    name: string;
    stages: PipelineDraftStage[];
    feature_config: PipelineFeatureConfig;
    remaps?: PipelineStageRemap[];
    expected_version?: number;
    comment?: string;
}

export interface PipelineRequiredRemap {
    stage_key: string;
    label: string;
    surrogate_count: number;
    reasons: string[];
}

export interface PipelineChangePreview {
    impact_areas: string[];
    validation_errors: string[];
    blocking_issues: string[];
    required_remaps: PipelineRequiredRemap[];
    safe_auto_fixes: string[];
    dependency_graph: PipelineDependencyGraph;
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
    return listPipelinesForEntity('surrogate');
}

function withEntityType(path: string, entityType: PipelineEntityType): string {
    const params = new URLSearchParams({ entity_type: entityType });
    return `${path}?${params.toString()}`;
}

function withOptionalEntityType(path: string, entityType?: PipelineEntityType): string {
    return entityType ? withEntityType(path, entityType) : path;
}

export async function listPipelinesForEntity(entityType: PipelineEntityType): Promise<Pipeline[]> {
    return api.get<Pipeline[]>(withEntityType('/settings/pipelines', entityType));
}

export async function getDefaultPipeline(entityType: PipelineEntityType = 'surrogate'): Promise<Pipeline> {
    return api.get<Pipeline>(withEntityType('/settings/pipelines/default', entityType));
}

export async function getDefaultPipelineSemantics(
    entityType: PipelineEntityType = 'surrogate'
): Promise<PipelineSemanticsSnapshot> {
    return api.get<PipelineSemanticsSnapshot>(withEntityType('/settings/pipelines/default/semantics', entityType));
}

export async function getPipeline(id: string, entityType?: PipelineEntityType): Promise<Pipeline> {
    return api.get<Pipeline>(withOptionalEntityType(`/settings/pipelines/${id}`, entityType));
}

export async function getPipelineSemantics(
    id: string,
    entityType?: PipelineEntityType,
): Promise<PipelineSemanticsSnapshot> {
    return api.get<PipelineSemanticsSnapshot>(
        withOptionalEntityType(`/settings/pipelines/${id}/semantics`, entityType),
    );
}

export async function getPipelineDependencyGraph(
    id: string,
    entityType?: PipelineEntityType,
): Promise<PipelineDependencyGraph> {
    return api.get<PipelineDependencyGraph>(
        withOptionalEntityType(`/settings/pipelines/${id}/dependency-graph`, entityType),
    );
}

export async function getRecommendedPipelineDraft(
    id: string,
    entityType?: PipelineEntityType,
): Promise<PipelineDraft> {
    return api.get<PipelineDraft>(
        withOptionalEntityType(`/settings/pipelines/${id}/recommended-draft`, entityType),
    );
}

export async function previewPipelineChanges(
    id: string,
    data: PipelineDraft,
    entityType?: PipelineEntityType,
): Promise<PipelineChangePreview> {
    return api.post<PipelineChangePreview>(
        withOptionalEntityType(`/settings/pipelines/${id}/change-preview`, entityType),
        data,
    );
}

export async function applyPipelineDraft(
    id: string,
    data: PipelineDraft,
    entityType?: PipelineEntityType,
): Promise<Pipeline> {
    return api.put<Pipeline>(
        withOptionalEntityType(`/settings/pipelines/${id}/apply-draft`, entityType),
        data,
    );
}

export async function createPipeline(
    name: string,
    entity_type: PipelineEntityType,
    stages?: StageCreate[],
    feature_config?: PipelineFeatureConfig,
): Promise<Pipeline> {
    return api.post<Pipeline>('/settings/pipelines', { name, entity_type, stages, feature_config });
}

export async function updatePipeline(
    id: string,
    data: PipelineUpdate,
    entityType?: PipelineEntityType,
): Promise<Pipeline> {
    return api.patch<Pipeline>(withOptionalEntityType(`/settings/pipelines/${id}`, entityType), data);
}

export async function deletePipeline(id: string, entityType?: PipelineEntityType): Promise<void> {
    return api.delete(withOptionalEntityType(`/settings/pipelines/${id}`, entityType));
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

export async function getPipelineVersions(
    id: string,
    entityType?: PipelineEntityType,
): Promise<PipelineVersion[]> {
    const response = await api.get<PipelineVersionsResponse>(
        withOptionalEntityType(`/settings/pipelines/${id}/versions`, entityType),
    );
    return response?.versions ?? [];
}

export async function rollbackPipeline(
    id: string,
    version: number,
    entityType?: PipelineEntityType,
): Promise<Pipeline> {
    return api.post<Pipeline>(
        withOptionalEntityType(`/settings/pipelines/${id}/rollback`, entityType),
        { target_version: version },
    );
}
