"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { CheckIcon, XIcon, PencilIcon, Loader2Icon, CalendarIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { format, parseISO, isValid } from "date-fns"

interface InlineDateFieldProps {
    value: string | null | undefined
    onSave: (value: string | null) => Promise<void>
    placeholder?: string
    className?: string
    displayClassName?: string
    label: string
    disabled?: boolean
}

type InlineDateFieldState = {
    isEditing: boolean
    editValue: string
    isSaving: boolean
    error: string | null
    pickerOpen: boolean
}

type InlineDateFieldAction =
    | { type: "startEdit"; value: string }
    | { type: "cancel" }
    | { type: "closeWithoutSave" }
    | { type: "setEditValue"; value: string }
    | { type: "setError"; error: string | null }
    | { type: "setPickerOpen"; pickerOpen: boolean }
    | { type: "startSaving" }
    | { type: "saveSuccess" }
    | { type: "saveError"; error: string }

const INITIAL_INLINE_DATE_FIELD_STATE: InlineDateFieldState = {
    isEditing: false,
    editValue: "",
    isSaving: false,
    error: null,
    pickerOpen: false,
}

function inlineDateFieldReducer(
    state: InlineDateFieldState,
    action: InlineDateFieldAction,
): InlineDateFieldState {
    switch (action.type) {
        case "startEdit":
            return { ...state, isEditing: true, editValue: action.value, error: null }
        case "cancel":
            return { ...state, isEditing: false, editValue: "", error: null, pickerOpen: false }
        case "closeWithoutSave":
            return { ...state, isEditing: false }
        case "setEditValue":
            return { ...state, editValue: action.value }
        case "setError":
            return { ...state, error: action.error }
        case "setPickerOpen":
            return { ...state, pickerOpen: action.pickerOpen }
        case "startSaving":
            return { ...state, isSaving: true }
        case "saveSuccess":
            return { ...state, isEditing: false, isSaving: false, error: null, pickerOpen: false }
        case "saveError":
            return { ...state, isSaving: false, error: action.error }
    }
}

export function InlineDateField({
    value,
    onSave,
    placeholder = "Set date",
    className,
    displayClassName,
    label,
    disabled = false,
}: InlineDateFieldProps) {
    const [state, dispatch] = React.useReducer(
        inlineDateFieldReducer,
        INITIAL_INLINE_DATE_FIELD_STATE,
    )
    const { isEditing, editValue, isSaving, error, pickerOpen } = state

    const handleStartEdit = () => {
        if (disabled) return
        dispatch({ type: "startEdit", value: value || "" })
    }

    const handleCancel = () => {
        dispatch({ type: "cancel" })
    }

    const handleSave = async () => {
        // Only save if value changed
        if (editValue === (value || "")) {
            dispatch({ type: "closeWithoutSave" })
            return
        }

        // Validate date if provided
        if (editValue) {
            const parsed = parseISO(editValue)
            if (!isValid(parsed)) {
                dispatch({ type: "setError", error: "Invalid date" })
                return
            }
        }

        dispatch({ type: "startSaving" })
        try {
            await onSave(editValue || null)
            dispatch({ type: "saveSuccess" })
        } catch (err) {
            dispatch({
                type: "saveError",
                error: err instanceof Error ? err.message : "Failed to save",
            })
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            e.preventDefault()
            handleSave()
        } else if (e.key === "Escape") {
            handleCancel()
        }
    }

    const handleDisplayKeyDown = (e: React.KeyboardEvent) => {
        if (disabled) return
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
            e.preventDefault()
            handleStartEdit()
        }
    }

    // Format display value
    const displayValue = React.useMemo(() => {
        if (!value) return null
        try {
            const parsed = parseISO(value)
            if (isValid(parsed)) {
                return format(parsed, "MMM d, yyyy")
            }
        } catch {
            // Fall through to null
        }
        return null
    }, [value])

    const selectedEditDate = React.useMemo(() => {
        if (!editValue) return undefined
        try {
            const parsed = parseISO(editValue)
            return isValid(parsed) ? parsed : undefined
        } catch {
            return undefined
        }
    }, [editValue])

    if (!isEditing) {
        return (
            <div
                className={cn(
                    "group flex items-center gap-1 rounded px-1 -mx-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    !disabled && "cursor-pointer hover:bg-muted/50",
                    disabled && "opacity-50 cursor-not-allowed",
                    displayClassName
                )}
                onClick={handleStartEdit}
                role="button"
                tabIndex={disabled ? -1 : 0}
                onKeyDown={handleDisplayKeyDown}
                aria-label={disabled ? label : `Edit ${label}`}
            >
                <span className={cn("text-sm", !displayValue && "text-muted-foreground", className)}>
                    {displayValue || placeholder}
                </span>
                {!disabled && (
                    <PencilIcon
                        className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                        aria-hidden="true"
                    />
                )}
            </div>
        )
    }

    return (
        <div className="flex max-w-full flex-col items-start gap-1">
            <div className="min-w-0 max-w-full">
                <Popover
                    open={pickerOpen}
                    onOpenChange={(nextOpen) => dispatch({ type: "setPickerOpen", pickerOpen: nextOpen })}
                >
                    <PopoverTrigger
                        className={cn(
                            "inline-flex h-7 w-40 max-w-full items-center justify-start gap-2 rounded-md border border-input bg-input/30 px-2.5 text-sm font-normal transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            !selectedEditDate && "text-muted-foreground",
                            error && "border-destructive"
                        )}
                        disabled={isSaving}
                        aria-label={label}
                        onKeyDown={handleKeyDown}
                    >
                        <CalendarIcon className="size-3.5" />
                        {selectedEditDate ? format(selectedEditDate, "MMM d, yyyy") : "Select date"}
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                            mode="single"
                            selected={selectedEditDate}
                            onSelect={(date) => {
                                dispatch({
                                    type: "setEditValue",
                                    value: date ? format(date, "yyyy-MM-dd") : "",
                                })
                                dispatch({ type: "setError", error: null })
                                dispatch({ type: "setPickerOpen", pickerOpen: false })
                            }}
                            {...(selectedEditDate ? { defaultMonth: selectedEditDate } : {})}
                        />
                        <div className="flex items-center justify-between border-t px-3 py-2">
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    dispatch({ type: "setEditValue", value: "" })
                                    dispatch({ type: "setError", error: null })
                                    dispatch({ type: "setPickerOpen", pickerOpen: false })
                                }}
                            >
                                Clear
                            </Button>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => dispatch({ type: "setPickerOpen", pickerOpen: false })}
                            >
                                Close calendar
                            </Button>
                        </div>
                    </PopoverContent>
                </Popover>
                {error && (
                    <p className="text-xs text-destructive mt-1">{error}</p>
                )}
            </div>
            <div className="flex items-center gap-2">
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label={`Save ${label}`}
                >
                    {isSaving ? (
                        <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
                    ) : (
                        <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                    )}
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label={`Cancel ${label}`}
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
        </div>
    )
}
