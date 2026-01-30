/**
 * Journey API client - typed functions for surrogate journey timeline endpoints.
 */

import api from './index';
import { getCsrfHeaders } from '@/lib/csrf';

// ============================================================================
// TYPES
// ============================================================================

export type JourneyMilestoneStatus = 'completed' | 'current' | 'upcoming';
export type JourneyExportVariant = 'internal' | 'client';

export interface JourneyMilestone {
    slug: string;
    label: string;
    description: string;
    status: JourneyMilestoneStatus;
    completed_at: string | null;  // ISO datetime
    is_soft: boolean;
    default_image_url: string;    // Absolute URL to default image
    featured_image_url: string | null;  // Signed URL to custom featured image
    featured_image_id: string | null;   // Attachment ID if featured image is set
}

export interface JourneyPhase {
    slug: string;
    label: string;
    milestones: JourneyMilestone[];
}

export interface JourneyResponse {
    surrogate_id: string;
    surrogate_name: string;
    journey_version: number;
    is_terminal: boolean;
    terminal_message: string | null;
    terminal_date: string | null;  // ISO date
    phases: JourneyPhase[];
    organization_name: string;
    organization_logo_url: string | null;
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

/**
 * Get the journey timeline for a surrogate.
 * Returns phases and milestones with computed statuses.
 */
export async function getSurrogateJourney(surrogateId: string): Promise<JourneyResponse> {
    return api.get<JourneyResponse>(`/journey/surrogates/${surrogateId}`);
}

// ============================================================================
// FEATURED IMAGE MANAGEMENT
// ============================================================================

export interface JourneyFeaturedImageUpdate {
    attachment_id: string | null;  // null to clear
}

export interface JourneyFeaturedImageResponse {
    success: boolean;
    milestone_slug: string;
    attachment_id: string | null;
}

/**
 * Update the featured image for a journey milestone.
 * Requires case_manager or higher role.
 */
export async function updateMilestoneFeaturedImage(
    surrogateId: string,
    milestoneSlug: string,
    attachmentId: string | null,
): Promise<JourneyFeaturedImageResponse> {
    return api.patch<JourneyFeaturedImageResponse>(
        `/journey/surrogates/${surrogateId}/milestones/${milestoneSlug}/featured-image`,
        { attachment_id: attachmentId },
    );
}

export async function exportJourneyPdf(
    surrogateId: string,
    variant: JourneyExportVariant = 'internal',
): Promise<void> {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    const url = `${baseUrl}/journey/surrogates/${surrogateId}/export?variant=${encodeURIComponent(variant)}`;

    const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: { ...getCsrfHeaders() },
    });

    if (!response.ok) {
        throw new Error(`Export failed (${response.status})`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/pdf')) {
        const errorText = await response.text();
        throw new Error(errorText || 'Export failed (unexpected response)');
    }

    const buffer = await response.arrayBuffer();
    const headerBytes = new Uint8Array(buffer.slice(0, 4));
    const headerText = String.fromCharCode(...headerBytes);
    if (headerText !== '%PDF') {
        const errorText = new TextDecoder().decode(buffer);
        throw new Error(errorText || 'Export failed (invalid PDF)');
    }

    const blob = new Blob([buffer], { type: 'application/pdf' });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = variant === 'client' ? 'journey_shared.pdf' : `journey_${surrogateId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objectUrl);
}

export default {
    getSurrogateJourney,
    updateMilestoneFeaturedImage,
    exportJourneyPdf,
};
