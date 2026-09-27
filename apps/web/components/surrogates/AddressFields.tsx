"use client"

import { InlineEditField } from "@/components/inline-edit-field"

interface AddressFieldsProps<T extends object> {
    readOnly?: boolean
    prefix: string  // e.g., 'clinic', 'monitoring_clinic', 'ob', 'delivery_hospital'
    data: T
    onUpdate: (field: string, value: string | null) => Promise<void>
    /** Section name for the field labels, so repeated address blocks have distinct names. */
    labelPrefix?: string
}

export function AddressFields<T extends object>({ prefix, data, onUpdate, labelPrefix, readOnly = false }: AddressFieldsProps<T>) {
    const field = (name: string) => `${prefix}_${name}`
    const dataRecord = data as unknown as Record<string, string | null | undefined>
    const getValue = (name: string) => dataRecord[field(name)] ?? null
    const label = (name: string) => (labelPrefix ? `${labelPrefix} ${name}` : name)

    return (
        <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-16 shrink-0">Line 1:</span>
                <InlineEditField
                    readOnly={readOnly}
                    value={getValue('address_line1')}
                    onSave={(v) => onUpdate(field('address_line1'), v || null)}
                    label={label("Street address")}
                    placeholder="Street address"
                />
            </div>
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-16 shrink-0">Line 2:</span>
                <InlineEditField
                    readOnly={readOnly}
                    value={getValue('address_line2')}
                    onSave={(v) => onUpdate(field('address_line2'), v || null)}
                    label={label("Address line 2")}
                    placeholder="Suite, unit, etc."
                />
            </div>
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-16 shrink-0">City:</span>
                <InlineEditField
                    readOnly={readOnly}
                    value={getValue('city')}
                    onSave={(v) => onUpdate(field('city'), v || null)}
                    label={label("City")}
                    placeholder="City"
                />
            </div>
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">State:</span>
                    <InlineEditField
                        readOnly={readOnly}
                        value={getValue('state')}
                        onSave={(v) => onUpdate(field('state'), v || null)}
                        label={label("State")}
                        placeholder="XX"
                        validate={(v) => v && v.length !== 2 ? 'Use 2-letter code' : null}
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">ZIP:</span>
                    <InlineEditField
                        readOnly={readOnly}
                        value={getValue('postal')}
                        onSave={(v) => onUpdate(field('postal'), v || null)}
                        label={label("ZIP")}
                        placeholder="00000"
                    />
                </div>
            </div>
        </div>
    )
}
