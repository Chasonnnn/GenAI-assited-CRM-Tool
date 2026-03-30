"use client"

import { ChevronDownIcon } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import type { ActionConfig, Condition } from "@/lib/api/workflows"
import type { JsonObject, JsonValue } from "@/lib/types/json"

export type SelectOption = { value: string; label: string }

export type EditableCondition = Condition & { clientId: string }
export type EditableAction = ActionConfig & { clientId: string }

export const BOOLEAN_FIELDS = new Set([
    "is_priority",
    "has_child",
    "is_citizen_or_pr",
    "is_non_smoker",
    "has_surrogate_experience",
    "is_age_eligible",
])

export const NUMBER_FIELDS = new Set([
    "age",
    "bmi",
    "height_ft",
    "weight_lb",
    "num_deliveries",
    "num_csections",
])

export const DATE_FIELDS = new Set(["created_at", "date_of_birth"])
export const LIST_OPERATORS = new Set(["in", "not_in"])
export const VALUELESS_OPERATORS = new Set(["is_empty", "is_not_empty"])

export const MULTISELECT_FIELDS = new Set([
    "stage_id",
    "status_label",
    "owner_id",
    "owner_type",
    "state",
    "source",
    "source_mode",
    "match_status",
])

export const SOURCE_OPTIONS: SelectOption[] = [
    { value: "manual", label: "Manual" },
    { value: "meta", label: "Meta" },
    { value: "website", label: "Website" },
    { value: "referral", label: "Referral" },
    { value: "import", label: "Import" },
    { value: "agency", label: "Agency" },
]

export const FORM_SOURCE_MODE_OPTIONS: SelectOption[] = [
    { value: "dedicated", label: "Dedicated Link" },
    { value: "shared", label: "Shared Link" },
]

export const FORM_MATCH_STATUS_OPTIONS: SelectOption[] = [
    { value: "linked", label: "Linked" },
    { value: "ambiguous_review", label: "Ambiguous Review" },
    { value: "lead_created", label: "Lead Created" },
]

export const OWNER_TYPE_OPTIONS: SelectOption[] = [
    { value: "user", label: "User" },
    { value: "queue", label: "Queue" },
]

export const EMAIL_RECIPIENT_OPTIONS: SelectOption[] = [
    { value: "surrogate", label: "Surrogate" },
    { value: "owner", label: "Case Owner" },
    { value: "creator", label: "Creator" },
    { value: "all_admins", label: "All Admins" },
    { value: "user", label: "Specific User" },
]

export function createClientRowId(): string {
    if (typeof globalThis.crypto?.randomUUID === "function") {
        return globalThis.crypto.randomUUID()
    }
    return `row-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function withConditionClientId(condition: Condition): EditableCondition {
    const existingClientId =
        "clientId" in condition && typeof condition.clientId === "string" ? condition.clientId : ""
    return {
        ...condition,
        clientId: existingClientId || createClientRowId(),
    }
}

function withActionClientId(action: ActionConfig): EditableAction {
    const existingClientId =
        "clientId" in action && typeof action.clientId === "string" ? action.clientId : ""
    return {
        ...action,
        clientId: existingClientId || createClientRowId(),
    }
}

function stripConditionClientId(condition: EditableCondition): Condition {
    const { clientId, ...rest } = condition
    void clientId
    return rest
}

function stripActionClientId(action: EditableAction): ActionConfig {
    const { clientId, ...rest } = action
    void clientId
    return rest
}

export function toListArray(value: JsonValue): string[] {
    if (Array.isArray(value)) {
        return value.map((item) => String(item).trim()).filter(Boolean)
    }
    if (typeof value === "string") {
        return value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
    }
    if (value === null || value === undefined) {
        return []
    }
    const asString = String(value).trim()
    return asString ? [asString] : []
}

function isJsonObject(value: JsonValue | undefined): value is JsonObject {
    return typeof value === "object" && value !== null && !Array.isArray(value)
}

function areJsonValuesEqual(left: JsonValue | undefined, right: JsonValue | undefined): boolean {
    if (Array.isArray(left) && Array.isArray(right)) {
        return left.length === right.length && left.every((value, index) => areJsonValuesEqual(value, right[index]))
    }
    if (isJsonObject(left) && isJsonObject(right)) {
        return areJsonObjectsEqual(left, right)
    }
    return Object.is(left, right)
}

export function areJsonObjectsEqual(left: JsonObject, right: JsonObject): boolean {
    const leftKeys = Object.keys(left)
    const rightKeys = Object.keys(right)

    if (leftKeys.length !== rightKeys.length) return false

    for (const key of leftKeys) {
        if (!(key in right)) return false
        if (!areJsonValuesEqual(left[key], right[key])) return false
    }

    return true
}

export function normalizeEditableConditionsForUi(conditions: Condition[]): EditableCondition[] {
    return conditions.map((condition) => {
        const conditionWithId = withConditionClientId(condition)
        if (!LIST_OPERATORS.has(conditionWithId.operator)) {
            return conditionWithId
        }
        if (MULTISELECT_FIELDS.has(conditionWithId.field)) {
            if (Array.isArray(conditionWithId.value)) {
                return conditionWithId
            }
            if (typeof conditionWithId.value === "string") {
                return {
                    ...conditionWithId,
                    value: conditionWithId.value
                        .split(",")
                        .map((value) => value.trim())
                        .filter(Boolean),
                }
            }
            return { ...conditionWithId, value: [] }
        }
        if (Array.isArray(conditionWithId.value)) {
            return { ...conditionWithId, value: conditionWithId.value.join(", ") }
        }
        return conditionWithId
    })
}

export function normalizeEditableConditionsForSave(conditions: EditableCondition[]): Condition[] {
    return conditions.map((condition) => {
        if (VALUELESS_OPERATORS.has(condition.operator)) {
            return stripConditionClientId({ ...condition, value: null })
        }
        if (LIST_OPERATORS.has(condition.operator)) {
            const raw =
                typeof condition.value === "string"
                    ? condition.value
                    : Array.isArray(condition.value)
                        ? condition.value.join(", ")
                        : ""
            return stripConditionClientId({
                ...condition,
                value: raw
                    .split(",")
                    .map((value) => value.trim())
                    .filter(Boolean),
            })
        }
        return stripConditionClientId(condition)
    })
}

export function normalizeEditableActionsForUi(actions: ActionConfig[]): EditableAction[] {
    return actions.map((action) => {
        const actionWithId = withActionClientId(action)
        const stageId = actionWithId.stage_id
        if (actionWithId.action_type === "update_status" && typeof stageId === "string" && stageId) {
            const normalized: EditableAction = {
                ...actionWithId,
                action_type: "update_field",
                field: "stage_id",
                value: stageId,
            }
            delete normalized.stage_id
            return normalized
        }
        return actionWithId
    })
}

export function normalizeEditableActionsForSave(actions: EditableAction[]): ActionConfig[] {
    return actions.map((action) => stripActionClientId(action))
}

export function getEmailRecipientKind(action: ActionConfig): string {
    const recipients = action.recipients
    if (Array.isArray(recipients)) return "user"
    if (typeof recipients === "string") return recipients
    return "surrogate"
}

export function getEmailRecipientUserId(action: ActionConfig): string {
    const recipients = action.recipients
    if (Array.isArray(recipients)) {
        return typeof recipients[0] === "string" ? recipients[0] : ""
    }
    return ""
}

export function WorkflowMultiSelect({
    options,
    value,
    onChange,
    placeholder = "Select values",
}: {
    options: SelectOption[]
    value: string[]
    onChange: (next: string[]) => void
    placeholder?: string
}) {
    const selectedValues = new Set(value)
    const selectedLabels = options
        .filter((option) => selectedValues.has(option.value))
        .map((option) => option.label)
    const label = selectedLabels.length > 0 ? `${selectedLabels.length} selected` : placeholder

    return (
        <Popover>
            <PopoverTrigger
                type="button"
                className={buttonVariants({ variant: "outline", className: "flex-1 justify-between" })}
            >
                <span className="truncate">{label}</span>
                <ChevronDownIcon className="size-4 text-muted-foreground" />
            </PopoverTrigger>
            <PopoverContent className="w-72">
                <ScrollArea className="h-48">
                    <div className="space-y-2">
                        {options.map((option) => {
                            const checked = selectedValues.has(option.value)
                            return (
                                <label key={option.value} className="flex items-center gap-2 text-sm">
                                    <Checkbox
                                        checked={checked}
                                        onCheckedChange={(next) => {
                                            const nextChecked = next === true
                                            const updated = new Set(selectedValues)
                                            if (nextChecked) {
                                                updated.add(option.value)
                                            } else {
                                                updated.delete(option.value)
                                            }
                                            onChange(Array.from(updated))
                                        }}
                                    />
                                    <span>{option.label}</span>
                                </label>
                            )
                        })}
                        {options.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No options available.</p>
                        ) : null}
                    </div>
                </ScrollArea>
            </PopoverContent>
        </Popover>
    )
}

export function ConditionValueInput({
    condition,
    options,
    onChange,
}: {
    condition: Pick<Condition, "field" | "operator" | "value">
    options: SelectOption[] | null
    onChange: (value: JsonValue) => void
}) {
    const operator = condition.operator
    const field = condition.field
    const isListOperator = LIST_OPERATORS.has(operator)
    const isValueless = VALUELESS_OPERATORS.has(operator)

    if (isValueless) {
        return (
            <Input
                className="flex-1"
                value=""
                disabled
                placeholder="No value needed"
            />
        )
    }

    if (!isListOperator && BOOLEAN_FIELDS.has(field)) {
        const checked = Boolean(condition.value)
        return (
            <div className="flex flex-1 items-center gap-2 rounded-md border px-3 py-2">
                <Switch checked={checked} onCheckedChange={onChange} />
                <span className="text-sm">{checked ? "Yes" : "No"}</span>
            </div>
        )
    }

    if (!isListOperator && NUMBER_FIELDS.has(field)) {
        return (
            <Input
                type="number"
                className="flex-1"
                value={typeof condition.value === "number" ? condition.value : ""}
                onChange={(event) => onChange(Number(event.target.value))}
            />
        )
    }

    if (!isListOperator && DATE_FIELDS.has(field)) {
        return (
            <Input
                type="date"
                className="flex-1"
                value={typeof condition.value === "string" ? condition.value : ""}
                onChange={(event) => onChange(event.target.value)}
            />
        )
    }

    if (isListOperator && options && MULTISELECT_FIELDS.has(field)) {
        const selectedValues = Array.isArray(condition.value)
            ? condition.value.map((item) => String(item))
            : toListArray(condition.value as JsonValue)
        return (
            <WorkflowMultiSelect
                options={options}
                value={selectedValues}
                onChange={onChange}
                placeholder="Select values"
            />
        )
    }

    if (options && !isListOperator) {
        return (
            <Select
                value={typeof condition.value === "string" ? condition.value : ""}
                onValueChange={onChange}
            >
                <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Select value">
                        {(value: string | null) => {
                            if (!value) return "Select value"
                            const option = options.find((item) => item.value === value)
                            return option?.label ?? "Unknown option"
                        }}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        )
    }

    const inputValue =
        typeof condition.value === "string"
            ? condition.value
            : Array.isArray(condition.value)
                ? condition.value.join(", ")
                : ""

    return (
        <Input
            placeholder={isListOperator ? "Comma-separated values" : "Value"}
            className="flex-1"
            value={inputValue}
            onChange={(event) => onChange(event.target.value)}
        />
    )
}
