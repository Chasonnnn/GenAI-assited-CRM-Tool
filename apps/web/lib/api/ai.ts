/**
 * API client for AI Assistant endpoints.
 */

import { api } from '../api';
import type { JsonObject } from '../types/json';

// Types
export interface AISettings {
    is_enabled: boolean;
    provider: string;
    model: string | null;
    api_key_masked: string | null;
    vertex_wif: VertexWIFConfig | null;
    vertex_api_key?: VertexAPIKeyConfig | null;
    context_notes_limit: number;
    conversation_history_limit: number;
    anonymize_pii: boolean;
    consent_accepted_at: string | null;
    consent_required: boolean;
}

export interface VertexWIFConfig {
    project_id: string | null;
    location: string | null;
    audience: string | null;
    service_account_email: string | null;
}

export interface VertexAPIKeyConfig {
    project_id: string | null;
    location: string | null;
}

export interface AISettingsUpdate {
    is_enabled?: boolean;
    provider?: 'gemini' | 'vertex_wif' | 'vertex_api_key';
    api_key?: string;
    model?: string;
    vertex_wif?: VertexWIFConfig;
    vertex_api_key?: VertexAPIKeyConfig;
    context_notes_limit?: number;
    conversation_history_limit?: number;
    anonymize_pii?: boolean;
}

// ConsentInfo for GET, ConsentAcceptResponse for POST
export interface ConsentInfo {
    consent_text: string;
    consent_accepted_at: string | null;
    consent_accepted_by: string | null;
}

export interface ConsentAcceptResponse {
    accepted: boolean;
    accepted_at: string;
    accepted_by: string;
}

export interface ProposedAction {
    approval_id: string | null;
    action_type: string;
    action_data: JsonObject;
    status: string;
}

export interface ActionApproval {
    id: string;
    action_index: number;
    action_type: string;
    status: string;
}

export interface AIMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    created_at: string;
    proposed_actions?: ProposedAction[];
    action_approvals?: ActionApproval[];
}

export interface AIConversation {
    id: string;
    entity_type: string;
    entity_id: string;
    created_at: string;
    updated_at: string;
    messages: AIMessage[];
}

export interface ChatRequest {
    entity_type?: 'surrogate' | 'global' | 'task' | null;  // null/undefined = global mode
    entity_id?: string | null;
    message: string;
}

export interface ChatResponse {
    content: string;
    proposed_actions: ProposedAction[];
    tokens_used: {
        prompt: number;
        completion: number;
        total: number;
    };
    conversation_id?: string;
    assistant_message_id?: string;
}

export interface ActionApprovalResult {
    success: boolean;
    action_type: string;
    status: string;
    result?: JsonObject;
    error?: string;
}

// ============================================================================
// Settings API
// ============================================================================

export async function getAISettings(): Promise<AISettings> {
    return api.get<AISettings>('/ai/settings');
}

export async function updateAISettings(update: AISettingsUpdate): Promise<AISettings> {
    return api.patch<AISettings>('/ai/settings', update);
}

export async function testAPIKey(
    provider: 'gemini' | 'vertex_api_key',
    api_key: string,
    vertex_api_key?: VertexAPIKeyConfig
): Promise<{ valid: boolean }> {
    return api.post<{ valid: boolean }>('/ai/settings/test', { provider, api_key, vertex_api_key });
}

// ============================================================================
// Consent API
// ============================================================================

export async function getConsent(): Promise<ConsentInfo> {
    return api.get<ConsentInfo>('/ai/consent');
}

export async function acceptConsent(): Promise<ConsentAcceptResponse> {
    return api.post<ConsentAcceptResponse>('/ai/consent/accept');
}

// ============================================================================
// Chat API
// ============================================================================

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    return api.post<ChatResponse>('/ai/chat', request);
}

export async function getConversation(entityType: string, entityId: string): Promise<AIConversation> {
    return api.get<AIConversation>(`/ai/conversations/${entityType}/${entityId}`);
}

export async function getGlobalConversation(): Promise<AIConversation> {
    return api.get<AIConversation>('/ai/conversations/global');
}

// ============================================================================
// Action Approval API
// ============================================================================

export async function approveAction(approvalId: string): Promise<ActionApprovalResult> {
    return api.post<ActionApprovalResult>(`/ai/actions/${approvalId}/approve`);
}

export async function rejectAction(approvalId: string): Promise<ActionApprovalResult> {
    return api.post<ActionApprovalResult>(`/ai/actions/${approvalId}/reject`);
}

// ============================================================================
// Focused AI Endpoints (One-shot operations)
// ============================================================================

export type EmailType = 'follow_up' | 'status_update' | 'meeting_request' | 'document_request' | 'introduction';

export interface SummarizeSurrogateRequest {
    surrogate_id: string;
}

export interface SummarizeSurrogateResponse {
    surrogate_number: string;
    full_name: string;
    summary: string;
    current_status: string;
    key_dates: Record<string, string | null>;
    pending_tasks: Array<{ id: string; title: string; due_date: string | null }>;
    recent_activity: string;
    suggested_next_steps: string[];
}

export interface DraftEmailRequest {
    surrogate_id: string;
    email_type: EmailType;
    additional_context?: string;
}

export interface DraftEmailResponse {
    subject: string;
    body: string;
    recipient_email: string;
    recipient_name: string;
    email_type: string;
}

export interface AnalyzeDashboardResponse {
    insights: string[];
    surrogate_volume_trend: string;
    bottlenecks: Array<{ status: string; count: number; percentage: number }>;
    recommendations: string[];
    stats: {
        total_active_surrogates: number;
        surrogates_this_week: number;
        surrogates_last_week: number;
        overdue_tasks: number;
        status_breakdown: Record<string, number>;
    };
}

export async function summarizeSurrogate(surrogateId: string): Promise<SummarizeSurrogateResponse> {
    return api.post<SummarizeSurrogateResponse>('/ai/summarize-surrogate', { surrogate_id: surrogateId });
}

export async function draftEmail(request: DraftEmailRequest): Promise<DraftEmailResponse> {
    return api.post<DraftEmailResponse>('/ai/draft-email', request);
}

export async function analyzeDashboard(): Promise<AnalyzeDashboardResponse> {
    return api.post<AnalyzeDashboardResponse>('/ai/analyze-dashboard');
}

// ============================================================================
// AI Usage API
// ============================================================================

export interface AIUsageSummary {
    period_days: number;
    total_requests: number;
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
    total_cost_usd: number;
}

export async function getAIUsageSummary(days: number = 30): Promise<AIUsageSummary> {
    return api.get<AIUsageSummary>(`/ai/usage/summary?days=${days}`);
}

// ============================================================================
// AI Workflow Generation API
// ============================================================================

export interface GeneratedWorkflow {
    name: string;
    description: string | null;
    icon: string;
    trigger_type: string;
    trigger_config: JsonObject;
    conditions: Array<{ field: string; operator: string; value: unknown }>;
    condition_logic: string;
    actions: Array<{ action_type: string;[key: string]: unknown }>;
}

export interface GenerateWorkflowRequest {
    description: string;
    scope?: 'personal' | 'org';
}

export interface GenerateWorkflowResponse {
    success: boolean;
    workflow: GeneratedWorkflow | null;
    explanation: string | null;
    validation_errors: string[];
    warnings: string[];
}

export interface ValidateWorkflowRequest {
    workflow: GeneratedWorkflow;
    scope?: 'personal' | 'org';
}

export interface ValidateWorkflowResponse {
    valid: boolean;
    errors: string[];
    warnings: string[];
}

export interface SaveWorkflowRequest {
    workflow: GeneratedWorkflow;
    scope?: 'personal' | 'org';
}

export interface SaveWorkflowResponse {
    success: boolean;
    workflow_id: string | null;
    error: string | null;
}

export async function generateWorkflow(
    description: string,
    scope: 'personal' | 'org' = 'personal'
): Promise<GenerateWorkflowResponse> {
    return api.post<GenerateWorkflowResponse>('/ai/workflows/generate', { description, scope });
}

export async function validateWorkflow(
    workflow: GeneratedWorkflow,
    scope: 'personal' | 'org' = 'personal'
): Promise<ValidateWorkflowResponse> {
    return api.post<ValidateWorkflowResponse>('/ai/workflows/validate', { workflow, scope });
}

export async function saveAIWorkflow(
    workflow: GeneratedWorkflow,
    scope: 'personal' | 'org' = 'personal'
): Promise<SaveWorkflowResponse> {
    return api.post<SaveWorkflowResponse>('/ai/workflows/save', { workflow, scope });
}

// ============================================================================
// AI Email Template Generation API
// ============================================================================

export interface GeneratedEmailTemplate {
    name: string;
    subject: string;
    body_html: string;
    variables_used: string[];
}

export interface GenerateEmailTemplateResponse {
    success: boolean;
    template: GeneratedEmailTemplate | null;
    explanation: string | null;
    validation_errors: string[];
    warnings: string[];
}

export async function generateEmailTemplate(description: string): Promise<GenerateEmailTemplateResponse> {
    return api.post<GenerateEmailTemplateResponse>('/ai/email-templates/generate', { description });
}
