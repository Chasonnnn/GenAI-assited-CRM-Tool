/**
 * API client for settings endpoints.
 */

import { api } from '../api';

// Types
export interface OrgSettings {
    id: string;
    name: string;
    address: string | null;
    phone: string | null;
    email: string | null;
}

export interface UpdateProfileRequest {
    display_name?: string;
    phone?: string;
}

export interface UpdateOrgRequest {
    name?: string;
    address?: string;
    phone?: string;
    email?: string;
}

// API Functions
export async function updateProfile(data: UpdateProfileRequest) {
    return api.patch<{ user_id: string }>('/auth/me', data);
}

export async function getOrgSettings(): Promise<OrgSettings> {
    return api.get<OrgSettings>('/settings/organization');
}

export async function updateOrgSettings(data: UpdateOrgRequest): Promise<OrgSettings> {
    return api.patch<OrgSettings>('/settings/organization', data);
}
