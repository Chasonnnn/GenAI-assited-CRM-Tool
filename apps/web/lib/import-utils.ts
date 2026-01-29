import type { ColumnAction, ColumnMappingItem, ColumnSuggestion, ConfidenceLevel } from '@/lib/api/import'
import type { SurrogateSource } from '@/lib/types/surrogate'

export interface ColumnMappingDraft extends ColumnMappingItem {
    custom_field_key: string | null
    confidence: number
    confidence_level: ConfidenceLevel
    sample_values: string[]
    reason: string
    warnings: string[]
    needs_inversion: boolean
}

export type UnknownColumnBehavior = 'ignore' | 'metadata' | 'warn'

export function buildColumnMappingsFromSuggestions(
    suggestions: ColumnSuggestion[]
): ColumnMappingDraft[] {
    return suggestions.map((suggestion) => {
        let action: ColumnAction
        let surrogateField = suggestion.suggested_field
        let customFieldKey: string | null = null

        if (surrogateField && surrogateField.startsWith('custom.')) {
            action = 'custom'
            customFieldKey = surrogateField.replace(/^custom\./, '')
            surrogateField = null
        } else if (suggestion.default_action) {
            action = suggestion.default_action
        } else if (suggestion.suggested_field) {
            action = 'map'
        } else {
            action = 'ignore'
        }

        if (action !== 'map') {
            surrogateField = null
        }

        let transformation = suggestion.transformation ?? null
        if (suggestion.needs_inversion && !transformation) {
            transformation = 'boolean_inverted'
        }

        return {
            csv_column: suggestion.csv_column,
            surrogate_field: surrogateField,
            transformation,
            action,
            custom_field_key: customFieldKey,
            confidence: suggestion.confidence,
            confidence_level: suggestion.confidence_level,
            sample_values: suggestion.sample_values,
            reason: suggestion.reason,
            warnings: suggestion.warnings,
            needs_inversion: suggestion.needs_inversion,
        }
    })
}

export function applyUnknownColumnBehavior(
    mappings: ColumnMappingDraft[],
    behavior: UnknownColumnBehavior,
    touchedColumns: Set<string>
): ColumnMappingDraft[] {
    return mappings.map((mapping) => {
        if (touchedColumns.has(mapping.csv_column)) {
            return mapping
        }
        if (mapping.action === 'custom' || mapping.custom_field_key) {
            return mapping
        }
        if (mapping.surrogate_field) {
            return mapping
        }
        if (behavior === 'metadata') {
            return { ...mapping, action: 'metadata', transformation: null }
        }
        if (behavior === 'ignore' || behavior === 'warn') {
            return { ...mapping, action: 'ignore', transformation: null }
        }
        return mapping
    })
}

export function buildImportSubmitPayload(
    mappings: ColumnMappingDraft[],
    behavior: UnknownColumnBehavior,
    touchedColumns: Set<string>,
    backdateCreatedAt = false,
    defaultSource: SurrogateSource = 'manual'
): {
    column_mappings: ColumnMappingItem[]
    unknown_column_behavior: UnknownColumnBehavior
    backdate_created_at: boolean
    default_source: SurrogateSource
} {
    const column_mappings = mappings
        .filter((mapping) => {
            if (behavior !== 'warn') return true
            const isUntouched = !touchedColumns.has(mapping.csv_column)
            const isUnknown = !mapping.surrogate_field && mapping.action !== 'custom'
            return !(isUntouched && isUnknown)
        })
        .map((mapping) => ({
            csv_column: mapping.csv_column,
            surrogate_field: mapping.action === 'map' ? mapping.surrogate_field : null,
            transformation: mapping.action === 'map' ? mapping.transformation : null,
            action: mapping.action,
            custom_field_key: mapping.action === 'custom' ? mapping.custom_field_key ?? null : null,
        }))

    return {
        column_mappings,
        unknown_column_behavior: behavior,
        backdate_created_at: backdateCreatedAt,
        default_source: defaultSource,
    }
}
