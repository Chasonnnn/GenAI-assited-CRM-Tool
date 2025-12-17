/**
 * API client for AI Assistant endpoints.
 */

import { api } from '../api';

// Types
export interface AISettings {
    is_enabled: boolean;
    provider: string;
    model: string | null;
    api_key_masked: string | null;
    context_notes_limit: number;
    conversation_history_limit: number;
    anonymize_pii: boolean;
    consent_accepted_at: string | null;
    consent_required: boolean;
}

export interface AISettingsUpdate {
    is_enabled?: boolean;
    provider?: 'openai' | 'gemini';
    api_key?: string;
    model?: string;
    context_notes_limit?: number;
    conversation_history_limit?: number;
    anonymize_pii?: boolean;
}

export interface ConsentInfo {
    consent_text: string;
    consent_accepted_at: string | null;
    consent_accepted_by: string | null;
}

export interface ProposedAction {
    approval_id: string;
    action_type: string;
    action_data: Record<string, unknown>;
    status: string;
}

export interface AIMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    created_at: string;
    proposed_actions?: ProposedAction[];
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
    entity_type: 'case';
    entity_id: string;
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
}

export interface ActionApprovalResult {
    success: boolean;
    action_type: string;
    status: string;
    result?: Record<string, unknown>;
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

export async function testAPIKey(provider: 'openai' | 'gemini', api_key: string): Promise<{ valid: boolean }> {
    return api.post<{ valid: boolean }>('/ai/test-key', { provider, api_key });
}

// ============================================================================
// Consent API
// ============================================================================

export async function getConsent(): Promise<ConsentInfo> {
    return api.get<ConsentInfo>('/ai/consent');
}

export async function acceptConsent(): Promise<ConsentInfo> {
    return api.post<ConsentInfo>('/ai/consent');
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

// ============================================================================
// Action Approval API
// ============================================================================

export async function approveAction(approvalId: string): Promise<ActionApprovalResult> {
    return api.post<ActionApprovalResult>(`/ai/actions/${approvalId}/approve`);
}

export async function rejectAction(approvalId: string): Promise<ActionApprovalResult> {
    return api.post<ActionApprovalResult>(`/ai/actions/${approvalId}/reject`);
}
