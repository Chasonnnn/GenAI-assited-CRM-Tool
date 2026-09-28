"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { EMPTY_VALUE_TEXT } from "@/components/ui/empty-value"
import { useAuth } from "@/lib/auth-context"
import { serializeHeightSelection, splitHeightFt } from "@/lib/height"
import { formatRace } from "@/lib/formatters"
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

const RACE_OPTIONS = [
    "american_indian_or_alaska_native",
    "asian",
    "black_or_african_american",
    "hispanic_or_latino",
    "native_hawaiian_or_other_pacific_islander",
    "white",
    "other_please_specify",
] as const

const RACE_OPTION_ALIASES: Record<string, (typeof RACE_OPTIONS)[number]> = {
    american_indian_alaska_native: "american_indian_or_alaska_native",
    black_african_american: "black_or_african_american",
    native_hawaiian_or_pacific_islander: "native_hawaiian_or_other_pacific_islander",
    native_hawaiian_or_other_pacific_islanders: "native_hawaiian_or_other_pacific_islander",
    other: "other_please_specify",
    other_please_specified: "other_please_specify",
}

function normalizeRaceOptionKey(value: string | null | undefined): string {
    const normalized = value?.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") ?? ""
    if (!normalized) return ""
    const aliased = RACE_OPTION_ALIASES[normalized] ?? normalized
    return RACE_OPTIONS.includes(aliased as (typeof RACE_OPTIONS)[number]) ? aliased : ""
}

type FormSelectOption = {
    value: string
    label: string
}

function formatFormSelectValue(
    value: string | null | undefined,
    options: readonly FormSelectOption[],
    placeholder: string,
) {
    if (!value) return placeholder
    return options.find((option) => option.value === value)?.label ?? value
}

/** Label of the explicit item that clears an optional field. It is a real choice, not a placeholder. */
const CLEAR_VALUE_LABEL = "Not provided"

function FormSelect({
    id,
    name,
    defaultValue,
    options,
    placeholder,
    clearable = false,
}: {
    id: string
    name: string
    defaultValue: string | null | undefined
    options: readonly FormSelectOption[]
    placeholder: string
    clearable?: boolean
}) {
    const [value, setValue] = React.useState(defaultValue ?? "")

    return (
        <>
            <input type="hidden" name={name} value={value} />
            <Select value={value || null} onValueChange={(nextValue) => setValue(nextValue ?? "")}>
                <SelectTrigger id={id} className="w-full">
                    <SelectValue placeholder={placeholder}>
                        {(selectedValue: string | null) =>
                            formatFormSelectValue(selectedValue, options, placeholder)
                        }
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectGroup>
                        {clearable ? <SelectItem value="">{CLEAR_VALUE_LABEL}</SelectItem> : null}
                        {options.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                </SelectContent>
            </Select>
        </>
    )
}

const HEIGHT_FEET_OPTIONS = Array.from({ length: 9 }, (_, value) => ({
    value: String(value),
    label: String(value),
}))

const HEIGHT_INCH_OPTIONS = Array.from({ length: 12 }, (_, value) => ({
    value: String(value),
    label: String(value),
}))

/** One "Height" field: two compact selects with ft / in suffixes. Clearing feet clears the height. */
function HeightField({ defaultFeet, defaultInches }: { defaultFeet: string; defaultInches: string }) {
    const [feet, setFeet] = React.useState(defaultFeet)
    const [inches, setInches] = React.useState(defaultInches)

    return (
        <div className="space-y-2">
            <Label htmlFor="height_feet">Height</Label>
            <div className="flex items-center gap-2">
                <Select
                    name="height_feet"
                    value={feet || null}
                    onValueChange={(nextValue) => {
                        const next = nextValue ?? ""
                        setFeet(next)
                        if (!next) setInches("")
                    }}
                >
                    <SelectTrigger id="height_feet" aria-label="Height feet" className="w-20">
                        <SelectValue placeholder={EMPTY_VALUE_TEXT} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">{CLEAR_VALUE_LABEL}</SelectItem>
                        {HEIGHT_FEET_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <span className="text-sm text-muted-foreground" aria-hidden="true">ft</span>
                <Select
                    name="height_inches"
                    value={inches || null}
                    onValueChange={(nextValue) => setInches(nextValue ?? "")}
                    disabled={!feet}
                >
                    <SelectTrigger aria-label="Height inches" className="w-20">
                        <SelectValue placeholder={EMPTY_VALUE_TEXT} />
                    </SelectTrigger>
                    <SelectContent>
                        {HEIGHT_INCH_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <span className="text-sm text-muted-foreground" aria-hidden="true">in</span>
            </div>
        </div>
    )
}

function PriorityField({ defaultChecked }: { defaultChecked: boolean }) {
    return (
        <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2">
            <Label htmlFor="is_priority">Priority</Label>
            <Switch id="is_priority" name="is_priority" defaultChecked={defaultChecked} />
        </div>
    )
}

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
    const formRef = React.useRef<HTMLFormElement>(null)

    const isOpen = activeDialog.type === "edit_surrogate"

    if (!surrogate) return null

    const editableChecklistItems =
        surrogate.eligibility_checklist && surrogate.eligibility_checklist.length > 0
            ? surrogate.eligibility_checklist
            : FALLBACK_CHECKLIST_ITEMS
    const visibleChecklistKeys = new Set(editableChecklistItems.map((item) => item.key))
    const heightSelection = splitHeightFt(surrogate.height_ft)

    async function handleSave() {
        const form = formRef.current
        if (!form) return
        if (!form.reportValidity()) return

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
    }

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent key={surrogate.id} size="2xl">
                <DialogHeader>
                    <DialogTitle>Edit Surrogate: #{surrogate.surrogate_number}</DialogTitle>
                </DialogHeader>
                <form ref={formRef}>
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
                        {canManagePriority && <PriorityField defaultChecked={surrogate.is_priority} />}
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
                                <FormSelect
                                    id="race"
                                    name="race"
                                    defaultValue={normalizeRaceOptionKey(surrogate.race)}
                                    placeholder={EMPTY_VALUE_TEXT}
                                    clearable
                                    options={RACE_OPTIONS.map((raceKey) => ({
                                        value: raceKey,
                                        label: formatRace(raceKey),
                                    }))}
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <HeightField
                                defaultFeet={heightSelection.feet}
                                defaultInches={heightSelection.inches}
                            />
                            <div className="space-y-2">
                                <Label htmlFor="weight_lb">Weight (lb)</Label>
                                <Input id="weight_lb" name="weight_lb" type="number" defaultValue={surrogate.weight_lb ?? ""} />
                            </div>
                        </div>
                        <div className="space-y-3 pt-2">
                            <div className="text-sm font-medium text-foreground">Eligibility Checklist</div>
                            <div className="grid grid-cols-2 gap-4">
                                {editableChecklistItems.map((item) => {
                                    if (item.key === "journey_timing_preference") {
                                        return (
                                            <div key={item.key} className="space-y-2">
                                                <Label htmlFor={item.key}>{item.label}</Label>
                                                <FormSelect
                                                    id={item.key}
                                                    name={item.key}
                                                    defaultValue={surrogate.journey_timing_preference ?? ""}
                                                    placeholder={EMPTY_VALUE_TEXT}
                                                    clearable
                                                    options={JOURNEY_TIMING_OPTIONS}
                                                />
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
                        <Button type="button" disabled={isUpdatePending} onClick={() => void handleSave()}>
                            {isUpdatePending ? "Saving..." : "Save Changes"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
