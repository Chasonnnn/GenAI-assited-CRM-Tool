import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { FieldSensitivity, FormLeadKind } from "@/lib/api/forms"
import { getBuilderFieldSensitivity, type BuilderFormField } from "@/lib/forms/form-builder-document"

const labels: Record<FieldSensitivity, string> = {
    identity: "Identity",
    contact: "Contact",
    campaign_safe: "Campaign safe",
    operational: "Operational",
    sensitive_health: "Health",
    sensitive_reproductive: "Reproductive health",
    sensitive_financial: "Financial",
    sensitive_legal: "Legal",
    free_text_unclassified: "Unclassified free text",
    file: "File",
}

export function DonorFieldSensitivitySelect({ field, leadKind, onChange }: {
    leadKind: FormLeadKind
    field: BuilderFormField
    onChange: (sensitivity: FieldSensitivity) => void
}) {
    if (leadKind === "surrogate") return null
    const value = getBuilderFieldSensitivity(field)
    return (
        <div className="space-y-2">
            <Label htmlFor="field-sensitivity">Data classification</Label>
            <Select value={value} onValueChange={(next) => {
                if (next && Object.hasOwn(labels, next)) onChange(next as FieldSensitivity)
            }}>
                <SelectTrigger id="field-sensitivity" aria-label="Data classification">
                    <SelectValue>{(selected: string | null) => labels[(selected ?? value) as FieldSensitivity]}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {Object.entries(labels).map(([key, label]) => (
                        <SelectItem key={key} value={key}>{label}</SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}
