import { describe, it, expect } from 'vitest'
import { applyUnknownColumnBehavior, buildColumnMappingsFromSuggestions, buildImportSubmitPayload } from '@/lib/import-utils'

describe('buildColumnMappingsFromSuggestions', () => {
    it('maps confident suggestions to map action', () => {
        const suggestions = [
            {
                csv_column: 'Email',
                suggested_field: 'email',
                confidence: 0.9,
                confidence_level: 'high',
                transformation: null,
                sample_values: [],
                reason: 'Exact match',
                warnings: [],
                default_action: null,
                needs_inversion: false,
            },
            {
                csv_column: 'Unknown',
                suggested_field: null,
                confidence: 0.0,
                confidence_level: 'none',
                transformation: null,
                sample_values: [],
                reason: 'No match',
                warnings: [],
                default_action: 'ignore',
                needs_inversion: false,
            },
        ]

        const mappings = buildColumnMappingsFromSuggestions(suggestions)

        expect(mappings[0]).toMatchObject({
            csv_column: 'Email',
            action: 'map',
            surrogate_field: 'email',
        })
        expect(mappings[1]).toMatchObject({
            csv_column: 'Unknown',
            action: 'ignore',
            surrogate_field: null,
        })
    })

    it('respects default_action metadata when no suggested field', () => {
        const suggestions = [
            {
                csv_column: 'Extra Column',
                suggested_field: null,
                confidence: 0.3,
                confidence_level: 'low',
                transformation: null,
                sample_values: ['foo'],
                reason: 'Type detected',
                warnings: [],
                default_action: 'metadata',
                needs_inversion: false,
            },
        ]

        const mappings = buildColumnMappingsFromSuggestions(suggestions)

        expect(mappings[0]).toMatchObject({
            csv_column: 'Extra Column',
            action: 'metadata',
            surrogate_field: null,
        })
    })
})

describe('applyUnknownColumnBehavior', () => {
    it('applies global behavior only to untouched unmapped columns', () => {
        const mappings = [
            {
                csv_column: 'Email',
                surrogate_field: 'email',
                transformation: null,
                action: 'map',
                custom_field_key: null,
                confidence: 0.9,
                confidence_level: 'high',
                sample_values: [],
                reason: 'Exact match',
                warnings: [],
                needs_inversion: false,
            },
            {
                csv_column: 'Unknown',
                surrogate_field: null,
                transformation: null,
                action: 'ignore',
                custom_field_key: null,
                confidence: 0,
                confidence_level: 'none',
                sample_values: [],
                reason: 'No match',
                warnings: [],
                needs_inversion: false,
            },
        ]

        const touched = new Set<string>(['Unknown'])
        const updated = applyUnknownColumnBehavior(mappings, 'metadata', touched)

        expect(updated[0].action).toBe('map')
        expect(updated[1].action).toBe('ignore')
    })
})

describe('buildImportSubmitPayload', () => {
    it('omits untouched unknown columns when behavior is warn', () => {
        const mappings = [
            {
                csv_column: 'Email',
                surrogate_field: 'email',
                transformation: null,
                action: 'map',
                custom_field_key: null,
                confidence: 0.9,
                confidence_level: 'high',
                sample_values: [],
                reason: 'Exact match',
                warnings: [],
                needs_inversion: false,
            },
            {
                csv_column: 'Unknown',
                surrogate_field: null,
                transformation: null,
                action: 'ignore',
                custom_field_key: null,
                confidence: 0,
                confidence_level: 'none',
                sample_values: [],
                reason: 'No match',
                warnings: [],
                needs_inversion: false,
            },
        ]

        const payload = buildImportSubmitPayload(mappings, 'warn', new Set(), true)
        const columns = payload.column_mappings.map((item) => item.csv_column)
        expect(columns).toEqual(['Email'])
        expect(payload.unknown_column_behavior).toBe('warn')
        expect(payload.backdate_created_at).toBe(true)
    })
})
