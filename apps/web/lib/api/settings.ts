/**
 * API client for settings endpoints.
 */

import { api } from '../api';
import type { User } from '@/lib/auth-context';

// =============================================================================
// Organization Types
// =============================================================================

export interface OrgSettings {
    id: string;
    name: string;
    slug: string;
    portal_base_url: string;
    address: string | null;
    phone: string | null;
    email: string | null;
}

export interface UpdateOrgRequest {
    name?: string;
    address?: string;
    phone?: string;
    email?: string;
}

export interface IntelligentSuggestionSettings {
    enabled: boolean;
    new_unread_enabled: boolean;
    new_unread_business_days: number;
    meeting_outcome_enabled: boolean;
    meeting_outcome_business_days: number;
    stuck_enabled: boolean;
    stuck_business_days: number;
    daily_digest_enabled: boolean;
    digest_hour_local: number;
}

export type UpdateIntelligentSuggestionSettingsRequest = Partial<IntelligentSuggestionSettings>;

// =============================================================================
// Profile Types
// =============================================================================

export interface UpdateProfileRequest {
    display_name?: string;
    phone?: string;
    title?: string;
}

// =============================================================================
// Session Types
// =============================================================================

export interface Session {
    id: string;
    device_info: string | null;
    ip_address: string | null;
    created_at: string;
    last_active_at: string;
    expires_at: string;
    is_current: boolean;
}

// =============================================================================
// Avatar Types
// =============================================================================

export interface AvatarResponse {
    avatar_url: string | null;
}

// =============================================================================
// Organization API
// =============================================================================

export async function getOrgSettings(): Promise<OrgSettings> {
    return api.get<OrgSettings>('/settings/organization');
}

export async function updateOrgSettings(data: UpdateOrgRequest): Promise<OrgSettings> {
    return api.patch<OrgSettings>('/settings/organization', data);
}

export async function getIntelligentSuggestionSettings(): Promise<IntelligentSuggestionSettings> {
    return api.get<IntelligentSuggestionSettings>('/settings/intelligent-suggestions');
}

export async function updateIntelligentSuggestionSettings(
    data: UpdateIntelligentSuggestionSettingsRequest
): Promise<IntelligentSuggestionSettings> {
    return api.patch<IntelligentSuggestionSettings>('/settings/intelligent-suggestions', data);
}

// =============================================================================
// Profile API
// =============================================================================

export async function updateProfile(data: UpdateProfileRequest): Promise<User> {
    return api.patch<User>('/auth/me', data);
}

// =============================================================================
// Sessions API
// =============================================================================

export async function getSessions(): Promise<Session[]> {
    return api.get<Session[]>('/auth/me/sessions');
}

export async function revokeSession(sessionId: string): Promise<{ status: string }> {
    return api.delete<{ status: string }>(`/auth/me/sessions/${sessionId}`);
}

export async function revokeAllSessions(): Promise<{ status: string; count: number }> {
    return api.delete<{ status: string; count: number }>('/auth/me/sessions');
}

// =============================================================================
// Avatar API
// =============================================================================

export async function uploadAvatar(file: File): Promise<AvatarResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<AvatarResponse>('/auth/me/avatar', formData);
}

export async function deleteAvatar(): Promise<AvatarResponse> {
    return api.delete<AvatarResponse>('/auth/me/avatar');
}
