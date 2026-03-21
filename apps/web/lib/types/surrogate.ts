/**
 * Surrogate contracts generated from backend OpenAPI with a stable frontend facade.
 */

import type {
    SurrogateListItem as GeneratedSurrogateListItem,
    SurrogateListResponse as GeneratedSurrogateListResponse,
    SurrogateRead as GeneratedSurrogateRead,
    SurrogateSource as GeneratedSurrogateSource,
    SurrogateStatusChange as GeneratedSurrogateStatusChange,
    SurrogateStatusChangePayload as GeneratedSurrogateStatusChangePayload,
    SurrogateStatusChangeResponse as GeneratedSurrogateStatusChangeResponse,
    SurrogateStatusHistory as GeneratedSurrogateStatusHistory,
    SurrogateStatusHistoryRead as GeneratedSurrogateStatusHistoryRead,
} from './surrogate.generated';

export type SurrogateSource = GeneratedSurrogateSource;
export type SurrogateStatusChange = GeneratedSurrogateStatusChange;
export type SurrogateStatusChangePayload = GeneratedSurrogateStatusChangePayload;
export type SurrogateStatusHistoryRead = GeneratedSurrogateStatusHistoryRead;
export type SurrogateStatusHistory = GeneratedSurrogateStatusHistory;

export type SurrogateListItem = Omit<GeneratedSurrogateListItem, 'owner_type'> & {
    owner_type: 'user' | 'queue' | null;
};

export type SurrogateLeadIntakeWarning = {
    field_key: 'email' | 'phone' | 'state' | 'height_ft' | 'weight_lb';
    issue: 'missing_value' | 'invalid_value';
    raw_value: string;
};

export type SurrogateRead = Omit<
    GeneratedSurrogateRead,
    'owner_type' | 'height_ft' | 'delivery_baby_gender' | 'delivery_baby_weight' | 'lead_intake_warnings'
> & {
    owner_type: 'user' | 'queue' | null;
    stage_slug: string | null;
    stage_type: string | null;
    age: number | null;
    bmi: number | null;
    last_activity_at: string | null;
    height_ft: number | null;
    delivery_baby_gender: string | null;
    delivery_baby_weight: string | null;
    lead_intake_warnings?: SurrogateLeadIntakeWarning[];
};

export type SurrogateListResponse = Omit<GeneratedSurrogateListResponse, 'items'> & {
    items: SurrogateListItem[];
};

export type SurrogateStatusChangeResponse = Omit<
    GeneratedSurrogateStatusChangeResponse,
    'status' | 'surrogate'
> & {
    status: 'applied' | 'pending_approval';
    surrogate?: SurrogateRead | null;
};
