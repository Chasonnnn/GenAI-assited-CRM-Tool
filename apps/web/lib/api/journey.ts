/**
 * Journey API client - typed functions for surrogate journey timeline endpoints.
 */

import api from './index';

// ============================================================================
// TYPES
// ============================================================================

export type JourneyMilestoneStatus = 'completed' | 'current' | 'upcoming';

export interface JourneyMilestone {
    slug: string;
    label: string;
    description: string;
    status: JourneyMilestoneStatus;
    completed_at: string | null;  // ISO datetime
    is_soft: boolean;
    featured_image_url: string | null;  // Phase 2
    featured_image_id: string | null;   // Phase 2
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

export default {
    getSurrogateJourney,
};
