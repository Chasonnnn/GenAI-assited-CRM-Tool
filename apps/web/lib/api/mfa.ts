/**
 * MFA API client - Multi-Factor Authentication endpoints.
 */

import api from '../api';

// =============================================================================
// Types
// =============================================================================

interface MFAStatus {
    mfa_enabled: boolean;
    totp_enabled: boolean;
    totp_enabled_at: string | null;
    duo_enabled: boolean;
    duo_enrolled_at: string | null;
    recovery_codes_remaining: number;
    mfa_required: boolean;
}

interface RecoveryCodesResponse {
    codes: string[];
    count: number;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get MFA enrollment status for the current user.
 */
export function getMFAStatus(): Promise<MFAStatus> {
    return api.get<MFAStatus>('/mfa/status');
}

/**
 * Regenerate recovery codes (invalidates previous codes).
 */
export function regenerateRecoveryCodes(): Promise<RecoveryCodesResponse> {
    return api.post<RecoveryCodesResponse>('/mfa/recovery/regenerate');
}

interface MFACompleteResponse {
    success: boolean;
    message: string;
}

/**
 * Complete MFA challenge and upgrade session.
 * On success, issues a new session cookie with mfa_verified=True.
 */
export function completeMFAChallenge(code: string): Promise<MFACompleteResponse> {
    return api.post<MFACompleteResponse>('/mfa/complete', { code });
}

/**
 * Disable MFA for the current user.
 */
export function disableMFA(): Promise<{ message: string }> {
    return api.post<{ message: string }>('/mfa/disable');
}

// =============================================================================
// Duo API Functions
// =============================================================================

interface DuoStatus {
    available: boolean;
    enrolled: boolean;
    enrolled_at: string | null;
}

interface DuoInitiateResponse {
    auth_url: string;
    state: string;
}

interface DuoCallbackResponse {
    success: boolean;
    message: string;
    recovery_codes?: string[];
}

/**
 * Check if Duo is available and user's enrollment status.
 */
export function getDuoStatus(): Promise<DuoStatus> {
    return api.get<DuoStatus>('/mfa/duo/status');
}

/**
 * Initiate Duo authentication flow.
 * Returns a URL to redirect the user to for Duo Universal Prompt.
 */
export function initiateDuoAuth(returnTo?: 'app' | 'ops'): Promise<DuoInitiateResponse> {
    const query = returnTo ? `?return_to=${returnTo}` : '';
    return api.post<DuoInitiateResponse>(`/mfa/duo/initiate${query}`);
}

/**
 * Verify Duo callback after user completes authentication.
 */
export function verifyDuoCallback(
    code: string,
    state: string,
    returnTo?: 'app' | 'ops'
): Promise<DuoCallbackResponse> {
    const query = returnTo ? `?return_to=${returnTo}` : ''
    return api.post<DuoCallbackResponse>(`/mfa/duo/callback${query}`, {
        code,
        state,
    });
}
