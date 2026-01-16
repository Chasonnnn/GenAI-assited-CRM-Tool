"use client"

import { PhoneIcon, MailIcon } from "lucide-react"
import { InlineEditField } from "@/components/inline-edit-field"
import { AddressFields } from "@/components/surrogates/AddressFields"
import { SurrogateRead } from "@/lib/types/surrogate"

interface MedicalContactSectionProps {
    title: string
    icon?: React.ReactNode
    prefix: string  // e.g., 'clinic', 'monitoring_clinic', 'ob', 'delivery_hospital'
    data: SurrogateRead
    onUpdate: (field: string, value: string | null) => Promise<void>
    showProviderName?: boolean  // For OB section: show doctor name
    showClinicName?: boolean    // Default true
}

export function MedicalContactSection({
    title,
    icon,
    prefix,
    data,
    onUpdate,
    showProviderName = false,
    showClinicName = true,
}: MedicalContactSectionProps) {
    const field = (name: string) => `${prefix}_${name}`
    const dataRecord = data as unknown as Record<string, string | null | undefined>
    const getValue = (name: string) => dataRecord[field(name)] ?? null

    // OB uses ob_clinic_name, others use {prefix}_name
    const clinicNameField = showProviderName ? `${prefix}_clinic_name` : `${prefix}_name`
    const getClinicNameValue = () => dataRecord[clinicNameField] ?? null

    // Check if this section has an email field (delivery_hospital may have one now)
    const hasEmailField = `${prefix}_email` in dataRecord

    return (
        <div className="space-y-3 p-3 rounded-lg border bg-card">
            <h4 className="text-sm font-medium flex items-center gap-2">
                {icon}
                {title}
            </h4>

            {showProviderName && (
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground w-16 shrink-0">Provider:</span>
                    <InlineEditField
                        value={getValue('provider_name')}
                        onSave={(v) => onUpdate(field('provider_name'), v || null)}
                        placeholder="Doctor name"
                    />
                </div>
            )}

            {showClinicName && (
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground w-16 shrink-0">Name:</span>
                    <InlineEditField
                        value={getClinicNameValue()}
                        onSave={(v) => onUpdate(clinicNameField, v || null)}
                        placeholder="Clinic/Hospital name"
                    />
                </div>
            )}

            <AddressFields prefix={prefix} data={data} onUpdate={onUpdate} />

            <div className="flex items-center gap-2 pt-1 border-t">
                <PhoneIcon className="size-3.5 text-muted-foreground shrink-0" />
                <InlineEditField
                    value={getValue('phone')}
                    onSave={(v) => onUpdate(field('phone'), v || null)}
                    type="tel"
                    placeholder="Phone"
                />
            </div>

            {hasEmailField && (
                <div className="flex items-center gap-2">
                    <MailIcon className="size-3.5 text-muted-foreground shrink-0" />
                    <InlineEditField
                        value={getValue('email')}
                        onSave={(v) => onUpdate(field('email'), v || null)}
                        type="email"
                        placeholder="Email"
                    />
                </div>
            )}
        </div>
    )
}
