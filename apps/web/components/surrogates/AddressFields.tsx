"use client"

import { InlineEditField } from "@/components/inline-edit-field"
import { SurrogateRead } from "@/lib/types/surrogate"

interface AddressFieldsProps {
    prefix: string  // e.g., 'clinic', 'monitoring_clinic', 'ob', 'delivery_hospital'
    data: SurrogateRead
    onUpdate: (field: string, value: string | null) => Promise<void>
}

export function AddressFields({ prefix, data, onUpdate }: AddressFieldsProps) {
    const field = (name: string) => `${prefix}_${name}`
    const dataRecord = data as unknown as Record<string, string | null | undefined>
    const getValue = (name: string) => dataRecord[field(name)] ?? null

    return (
        <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-16 shrink-0">Line 1:</span>
                <InlineEditField
                    value={getValue('address_line1')}
                    onSave={(v) => onUpdate(field('address_line1'), v || null)}
                    placeholder="Street address"
                />
            </div>
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-16 shrink-0">Line 2:</span>
                <InlineEditField
                    value={getValue('address_line2')}
                    onSave={(v) => onUpdate(field('address_line2'), v || null)}
                    placeholder="Suite, unit, etc."
                />
            </div>
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-16 shrink-0">City:</span>
                <InlineEditField
                    value={getValue('city')}
                    onSave={(v) => onUpdate(field('city'), v || null)}
                    placeholder="City"
                />
            </div>
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">State:</span>
                    <InlineEditField
                        value={getValue('state')}
                        onSave={(v) => onUpdate(field('state'), v || null)}
                        placeholder="XX"
                        validate={(v) => v && v.length !== 2 ? 'Use 2-letter code' : null}
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">ZIP:</span>
                    <InlineEditField
                        value={getValue('postal')}
                        onSave={(v) => onUpdate(field('postal'), v || null)}
                        placeholder="00000"
                    />
                </div>
            </div>
        </div>
    )
}
