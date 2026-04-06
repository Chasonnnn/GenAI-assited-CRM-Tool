"use client"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { useAuth } from "@/lib/auth-context"
import { serializeHeightSelection, splitHeightFt } from "@/lib/height"
import {
    useSurrogateDetailActions,
    useSurrogateDetailData,
    useSurrogateDetailDialogs,
} from "../context"

const JOURNEY_TIMING_OPTIONS = [
    { label: "0–3 months", value: "months_0_3" },
    { label: "3–6 months", value: "months_3_6" },
    { label: "Still deciding", value: "still_deciding" },
] as const

const FALLBACK_CHECKLIST_ITEMS = [
    { key: "is_age_eligible", label: "Age Eligible", type: "boolean" },
    { key: "is_citizen_or_pr", label: "US Citizen/PR", type: "boolean" },
    { key: "has_child", label: "Has Child", type: "boolean" },
    { key: "is_non_smoker", label: "Non-Smoker", type: "boolean" },
    { key: "has_surrogate_experience", label: "Surrogate Experience", type: "boolean" },
    { key: "num_deliveries", label: "Number of Deliveries", type: "number" },
    { key: "num_csections", label: "Number of C-Sections", type: "number" },
] as const

export function EditDialog() {
    const { user } = useAuth()
    const { surrogate } = useSurrogateDetailData()
    const { activeDialog, closeDialog } = useSurrogateDetailDialogs()
    const { updateSurrogate, isUpdatePending } = useSurrogateDetailActions()
    const canManagePriority = user?.role === "admin" || user?.role === "developer"

    const isOpen = activeDialog.type === "edit_surrogate"

    if (!surrogate) return null

    const editableChecklistItems =
        surrogate.eligibility_checklist && surrogate.eligibility_checklist.length > 0
            ? surrogate.eligibility_checklist
            : FALLBACK_CHECKLIST_ITEMS
    const visibleChecklistKeys = new Set(editableChecklistItems.map((item) => item.key))
    const heightSelection = splitHeightFt(surrogate.height_ft)

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Edit Surrogate: #{surrogate.surrogate_number}</DialogTitle>
                </DialogHeader>
                <form
                    onSubmit={async (event: React.FormEvent<HTMLFormElement>) => {
                        event.preventDefault()
                        const form = event.currentTarget
                        const formData = new FormData(form)
                        const data: Record<string, unknown> = {}
                        const getString = (key: string) => {
                            const value = formData.get(key)
                            return typeof value === "string" ? value : ""
                        }

                        const fullName = getString("full_name")
                        if (fullName) data.full_name = fullName
                        const email = getString("email")
                        if (email) data.email = email
                        const phone = getString("phone")
                        data.phone = phone || null
                        const state = getString("state")
                        data.state = state || null
                        const dateOfBirth = getString("date_of_birth")
                        data.date_of_birth = dateOfBirth || null
                        const race = getString("race")
                        data.race = race || null

                        data.height_ft = serializeHeightSelection(
                            getString("height_feet"),
                            getString("height_inches"),
                        )
                        const weightLb = getString("weight_lb")
                        data.weight_lb = weightLb ? parseFloat(weightLb) : null
                        const numDeliveries = getString("num_deliveries")
                        const numCsections = getString("num_csections")
                        const journeyTimingPreference = getString("journey_timing_preference")

                        if (visibleChecklistKeys.has("num_deliveries")) {
                            data.num_deliveries = numDeliveries ? parseInt(numDeliveries, 10) : null
                        }
                        if (visibleChecklistKeys.has("num_csections")) {
                            data.num_csections = numCsections ? parseInt(numCsections, 10) : null
                        }
                        if (visibleChecklistKeys.has("journey_timing_preference")) {
                            data.journey_timing_preference = journeyTimingPreference || null
                        }

                        if (visibleChecklistKeys.has("is_age_eligible")) {
                            data.is_age_eligible = formData.get("is_age_eligible") === "on"
                        }
                        if (visibleChecklistKeys.has("is_citizen_or_pr")) {
                            data.is_citizen_or_pr = formData.get("is_citizen_or_pr") === "on"
                        }
                        if (visibleChecklistKeys.has("has_child")) {
                            data.has_child = formData.get("has_child") === "on"
                        }
                        if (visibleChecklistKeys.has("is_non_smoker")) {
                            data.is_non_smoker = formData.get("is_non_smoker") === "on"
                        }
                        if (visibleChecklistKeys.has("has_surrogate_experience")) {
                            data.has_surrogate_experience = formData.get("has_surrogate_experience") === "on"
                        }
                        if (canManagePriority) {
                            data.is_priority = formData.get("is_priority") === "on"
                        }

                        await updateSurrogate(data)
                    }}
                >
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="full_name">Full Name *</Label>
                                <Input id="full_name" name="full_name" defaultValue={surrogate.full_name} required />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="email">Email *</Label>
                                <Input id="email" name="email" type="email" defaultValue={surrogate.email} required />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="phone">Phone</Label>
                                <Input id="phone" name="phone" defaultValue={surrogate.phone ?? ""} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="state">State</Label>
                                <Input id="state" name="state" defaultValue={surrogate.state ?? ""} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="date_of_birth">Date of Birth</Label>
                                <Input id="date_of_birth" name="date_of_birth" type="date" defaultValue={surrogate.date_of_birth ?? ""} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="race">Race</Label>
                                <Input id="race" name="race" defaultValue={surrogate.race ?? ""} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="height_feet">Height Feet</Label>
                                    <NativeSelect
                                        id="height_feet"
                                        name="height_feet"
                                        defaultValue={heightSelection.feet}
                                        className="w-full"
                                    >
                                        <NativeSelectOption value="">ft</NativeSelectOption>
                                        {Array.from({ length: 9 }, (_, value) => value).map((value) => (
                                            <NativeSelectOption key={`height-feet-${value}`} value={String(value)}>
                                                {value} ft
                                            </NativeSelectOption>
                                        ))}
                                    </NativeSelect>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="height_inches">Height Inches</Label>
                                    <NativeSelect
                                        id="height_inches"
                                        name="height_inches"
                                        defaultValue={heightSelection.inches}
                                        className="w-full"
                                    >
                                        <NativeSelectOption value="">in</NativeSelectOption>
                                        {Array.from({ length: 12 }, (_, value) => value).map((value) => (
                                            <NativeSelectOption key={`height-inches-${value}`} value={String(value)}>
                                                {value} in
                                            </NativeSelectOption>
                                        ))}
                                    </NativeSelect>
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="weight_lb">Weight (lb)</Label>
                                <Input id="weight_lb" name="weight_lb" type="number" defaultValue={surrogate.weight_lb ?? ""} />
                            </div>
                        </div>
                        <div className="space-y-3 pt-2">
                            <div className="text-sm font-medium text-foreground">Eligibility Checklist</div>
                            <div className="grid grid-cols-2 gap-4">
                                {canManagePriority && (
                                    <div className="flex items-center gap-2">
                                        <Checkbox id="is_priority" name="is_priority" defaultChecked={surrogate.is_priority} />
                                        <Label htmlFor="is_priority">Priority Surrogate</Label>
                                    </div>
                                )}
                                {editableChecklistItems.map((item) => {
                                    if (item.key === "journey_timing_preference") {
                                        return (
                                            <div key={item.key} className="space-y-2">
                                                <Label htmlFor={item.key}>{item.label}</Label>
                                                <NativeSelect
                                                    id={item.key}
                                                    name={item.key}
                                                    defaultValue={surrogate.journey_timing_preference ?? ""}
                                                    className="w-full"
                                                >
                                                    <NativeSelectOption value="">Not provided</NativeSelectOption>
                                                    {JOURNEY_TIMING_OPTIONS.map((option) => (
                                                        <NativeSelectOption key={option.value} value={option.value}>
                                                            {option.label}
                                                        </NativeSelectOption>
                                                    ))}
                                                </NativeSelect>
                                            </div>
                                        )
                                    }

                                    if (item.type === "number" && (item.key === "num_deliveries" || item.key === "num_csections")) {
                                        const isDeliveries = item.key === "num_deliveries"
                                        return (
                                            <div key={item.key} className="space-y-2">
                                                <Label htmlFor={item.key}>{item.label}</Label>
                                                <Input
                                                    id={item.key}
                                                    name={item.key}
                                                    type="number"
                                                    min="0"
                                                    max={isDeliveries ? "20" : "10"}
                                                    defaultValue={
                                                        isDeliveries
                                                            ? surrogate.num_deliveries ?? ""
                                                            : surrogate.num_csections ?? ""
                                                    }
                                                />
                                            </div>
                                        )
                                    }

                                    if (item.type === "boolean") {
                                        const checked =
                                            item.key === "is_age_eligible"
                                                ? surrogate.is_age_eligible ?? false
                                                : item.key === "is_citizen_or_pr"
                                                    ? surrogate.is_citizen_or_pr ?? false
                                                    : item.key === "has_child"
                                                        ? surrogate.has_child ?? false
                                                        : item.key === "is_non_smoker"
                                                            ? surrogate.is_non_smoker ?? false
                                                            : surrogate.has_surrogate_experience ?? false

                                        return (
                                            <div key={item.key} className="flex items-center gap-2">
                                                <Checkbox id={item.key} name={item.key} defaultChecked={checked} />
                                                <Label htmlFor={item.key}>{item.label}</Label>
                                            </div>
                                        )
                                    }

                                    return null
                                })}
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
                        <Button type="submit" disabled={isUpdatePending}>
                            {isUpdatePending ? "Saving..." : "Save Changes"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
