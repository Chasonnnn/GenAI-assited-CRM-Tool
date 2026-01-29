import api from './index'
import type { ColumnMappingItem, ColumnSuggestion } from './import'

export interface MetaFormSummary {
    id: string
    form_external_id: string
    form_name: string
    page_id: string
    page_name: string | null
    mapping_status: string
    current_version_id: string | null
    mapping_version_id: string | null
    mapping_updated_at: string | null
    mapping_updated_by_name: string | null
    is_active: boolean
    synced_at: string
    unconverted_leads: number
    total_leads: number
    last_lead_at: string | null
}

export interface MetaFormColumn {
    key: string
    label: string | null
    question_type: string | null
}

export interface MetaFormMappingPreview {
    form: MetaFormSummary
    columns: MetaFormColumn[]
    column_suggestions: ColumnSuggestion[]
    sample_rows: Array<Record<string, string>>
    has_live_leads: boolean
    available_fields: string[]
    ai_available: boolean
    mapping_rules: ColumnMappingItem[] | null
    unknown_column_behavior: 'ignore' | 'metadata' | 'warn'
}

export interface MetaFormMappingUpdate {
    column_mappings: ColumnMappingItem[]
    unknown_column_behavior: 'ignore' | 'metadata' | 'warn'
}

export async function listMetaForms(): Promise<MetaFormSummary[]> {
    return api.get<MetaFormSummary[]>('/integrations/meta/forms')
}

export async function syncMetaForms(payload?: { page_id?: string }): Promise<{
    success: boolean
    message: string
}> {
    return api.post('/integrations/meta/forms/sync', payload ?? {})
}

export async function getMetaFormMapping(formId: string): Promise<MetaFormMappingPreview> {
    return api.get<MetaFormMappingPreview>(`/integrations/meta/forms/${formId}/mapping`)
}

export async function updateMetaFormMapping(
    formId: string,
    payload: MetaFormMappingUpdate
): Promise<{ success: boolean; message?: string }> {
    return api.put(`/integrations/meta/forms/${formId}/mapping`, payload)
}
