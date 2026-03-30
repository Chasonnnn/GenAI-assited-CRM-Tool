"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    EyeIcon,
    EyeOffIcon,
    PencilIcon,
    XIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { getFormOptionLabel, getFormOptionLabels } from "@/lib/forms/option-labels"
import { useProfileCardEdits, useProfileCardMode } from "./context"
import type { FormSchema } from "@/lib/api/forms"

interface FieldRowProps {
    fieldKey: string
    field: FormSchema["pages"][number]["fields"][number]
    mergedValue: unknown
    baseValue: unknown
}

type FieldRowValueProps = {
    fieldKey: string
    field: FormSchema["pages"][number]["fields"][number]
    mergedValue: unknown
    isEditMode: boolean
    editingField: string | null
    isHidden: boolean
    isRevealed: boolean
    displayValue: unknown
    isOverridden: boolean
    isStaged: boolean
    editedValue: unknown
    setFieldValue: (fieldKey: string, value: string) => void
    cancelFieldEdit: (fieldKey: string) => void
}

function FieldRowValue({
    fieldKey,
    field,
    mergedValue,
    isEditMode,
    editingField,
    isHidden,
    isRevealed,
    displayValue,
    isOverridden,
    isStaged,
    editedValue,
    setFieldValue,
    cancelFieldEdit,
}: FieldRowValueProps) {
    if (isEditMode && editingField === fieldKey) {
        return (
            <div className="flex items-center gap-2">
                <Input
                    value={String(editedValue ?? mergedValue ?? "")}
                    onChange={(event) => setFieldValue(fieldKey, event.target.value)}
                    className="h-8 text-sm"
                />
                <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0"
                    onClick={() => cancelFieldEdit(fieldKey)}
                    aria-label={`Cancel editing ${field.label}`}
                >
                    <XIcon className="h-3.5 w-3.5" />
                </Button>
            </div>
        )
    }

    if (isHidden && !isRevealed) {
        return <span className="text-sm text-muted-foreground font-mono">******</span>
    }

    const valueClass = cn(
        "text-sm text-right",
        (isOverridden || isStaged) && "bg-yellow-100 dark:bg-yellow-900/30 px-1.5 py-0.5 rounded",
        isHidden && "text-muted-foreground"
    )

    if (displayValue === null || displayValue === undefined || displayValue === "") {
        return <span className="text-sm text-muted-foreground">—</span>
    }

    if (field.type === "date" && typeof displayValue === "string") {
        return <span className={valueClass}>{formatLocalDate(parseDateInput(displayValue))}</span>
    }

    if (typeof displayValue === "boolean") {
        const badge = displayValue ? (
            <Badge variant="default" className="bg-green-500 hover:bg-green-500/80">Yes</Badge>
        ) : (
            <Badge variant="secondary">No</Badge>
        )
        return <span className={valueClass}>{badge}</span>
    }

    if (
        typeof displayValue === "string" &&
        (field.type === "select" || field.type === "radio")
    ) {
        return (
            <span className={valueClass}>
                {getFormOptionLabel(field.options, displayValue) ?? displayValue}
            </span>
        )
    }

    if (Array.isArray(displayValue)) {
        return displayValue.length ? (
            <span className={valueClass}>
                {getFormOptionLabels(field.options, displayValue).join(", ")}
            </span>
        ) : (
            <span className="text-sm text-muted-foreground">—</span>
        )
    }

    return <span className={valueClass}>{String(displayValue)}</span>
}

export function FieldRow({ fieldKey, field, mergedValue, baseValue }: FieldRowProps) {
    const { mode, setEditingField } = useProfileCardMode()
    const {
        editedFields,
        setFieldValue,
        cancelFieldEdit,
        hiddenFields,
        toggleHidden,
        revealedFields,
        toggleReveal,
        stagedChanges,
    } = useProfileCardEdits()

    const isEditMode = mode.type === "edit"
    const editingField = mode.type === "edit" ? mode.editingField : null
    const isHidden = hiddenFields.includes(fieldKey)
    const isRevealed = revealedFields.has(fieldKey)
    const editedValue = editedFields[fieldKey]
    const displayValue = editedValue !== undefined ? editedValue : mergedValue
    const isOverridden = baseValue !== displayValue
    const isStaged = stagedChanges.some(c => c.field_key === fieldKey)

    return (
        <div className="flex items-center justify-between gap-4 py-1.5 border-b border-border/50 last:border-0 group">
            <span className="text-sm text-muted-foreground flex-shrink-0">
                {field.label}
            </span>
            <div className="flex items-center gap-2">
                <FieldRowValue
                    fieldKey={fieldKey}
                    field={field}
                    mergedValue={mergedValue}
                    isEditMode={isEditMode}
                    editingField={editingField}
                    isHidden={isHidden}
                    isRevealed={isRevealed}
                    displayValue={displayValue}
                    isOverridden={isOverridden}
                    isStaged={isStaged}
                    editedValue={editedValue}
                    setFieldValue={setFieldValue}
                    cancelFieldEdit={cancelFieldEdit}
                />

                {/* Edit button */}
                {isEditMode && !isHidden && editingField !== fieldKey && (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => setEditingField(fieldKey)}
                        aria-label={`Edit ${field.label}`}
                    >
                        <PencilIcon className="h-3 w-3" />
                    </Button>
                )}

                {/* Temporary reveal for hidden fields */}
                {isHidden && (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => toggleReveal(fieldKey)}
                        aria-label={isRevealed ? "Hide field value" : "Reveal field value"}
                        title={isRevealed ? "Hide field value" : "Reveal field value"}
                    >
                        {isRevealed ? (
                            <EyeOffIcon className="h-3 w-3" />
                        ) : (
                            <EyeIcon className="h-3 w-3" />
                        )}
                    </Button>
                )}

                {/* Persistent hide/unhide toggle (edit mode only) */}
                {isEditMode && (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => toggleHidden(fieldKey)}
                        aria-label={isHidden ? "Unhide field" : "Hide field"}
                        title={isHidden ? "Unhide field" : "Hide field"}
                    >
                        {isHidden ? (
                            <EyeIcon className="h-3 w-3" />
                        ) : (
                            <EyeOffIcon className="h-3 w-3" />
                        )}
                    </Button>
                )}
            </div>
        </div>
    )
}
