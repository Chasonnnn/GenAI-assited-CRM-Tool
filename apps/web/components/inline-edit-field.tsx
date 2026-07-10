"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { CheckIcon, XIcon, PencilIcon, Loader2Icon } from "lucide-react"
import { Button } from "@/components/ui/button"

interface InlineEditFieldProps {
    value: string | null | undefined
    onSave: (value: string) => Promise<void>
    placeholder?: string
    type?: "text" | "email" | "tel" | "url"
    className?: string
    displayClassName?: string
    validate?: (value: string) => string | null
    label?: string
}

type InlineEditFieldState = {
    isEditing: boolean
    editValue: string
    isSaving: boolean
    error: string | null
}

type InlineEditFieldAction =
    | { type: "startEdit"; value: string }
    | { type: "cancel"; value: string }
    | { type: "closeWithoutSave" }
    | { type: "setEditValue"; value: string }
    | { type: "setError"; error: string | null }
    | { type: "startSaving" }
    | { type: "saveSuccess" }
    | { type: "saveError"; error: string }

const INITIAL_INLINE_EDIT_FIELD_STATE: InlineEditFieldState = {
    isEditing: false,
    editValue: "",
    isSaving: false,
    error: null,
}

function inlineEditFieldReducer(
    state: InlineEditFieldState,
    action: InlineEditFieldAction,
): InlineEditFieldState {
    switch (action.type) {
        case "startEdit":
            return { ...state, isEditing: true, editValue: action.value, error: null }
        case "cancel":
            return { ...state, isEditing: false, editValue: action.value, error: null }
        case "closeWithoutSave":
            return { ...state, isEditing: false }
        case "setEditValue":
            return { ...state, editValue: action.value }
        case "setError":
            return { ...state, error: action.error }
        case "startSaving":
            return { ...state, isSaving: true }
        case "saveSuccess":
            return { ...state, isEditing: false, isSaving: false, error: null }
        case "saveError":
            return { ...state, isSaving: false, error: action.error }
    }
}

export function InlineEditField({
    value,
    onSave,
    placeholder = "-",
    type = "text",
    className,
    displayClassName,
    validate,
    label,
}: InlineEditFieldProps) {
    const [state, dispatch] = React.useReducer(
        inlineEditFieldReducer,
        INITIAL_INLINE_EDIT_FIELD_STATE,
    )
    const { isEditing, editValue, isSaving, error } = state
    const inputRef = React.useRef<HTMLInputElement>(null)

    // Focus input when editing starts
    React.useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus()
            inputRef.current.select()
        }
    }, [isEditing])

    const handleStartEdit = () => {
        dispatch({ type: "startEdit", value: value || "" })
    }

    const handleCancel = () => {
        dispatch({ type: "cancel", value: value || "" })
    }

    const handleSave = async () => {
        // Validate if provided
        if (validate) {
            const validationError = validate(editValue)
            if (validationError) {
                dispatch({ type: "setError", error: validationError })
                return
            }
        }

        // Only save if value changed
        if (editValue === (value || "")) {
            dispatch({ type: "closeWithoutSave" })
            return
        }

        dispatch({ type: "startSaving" })
        try {
            await onSave(editValue)
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
            void handleSave()
        } else if (e.key === "Escape") {
            handleCancel()
        }
    }

    const fieldLabel = label?.trim() || (placeholder && placeholder !== "-" ? placeholder : "field")

    if (!isEditing) {
        return (
            <Button unstyled
                type="button"
                className={cn(
                    "group flex items-center gap-1 rounded px-1 -mx-1 hover:bg-muted/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    displayClassName
                )}
                onClick={handleStartEdit}
                aria-label={`Edit ${fieldLabel}`}
            >
                <span className={cn("text-sm", !value && "text-muted-foreground", className)}>
                    {value || placeholder}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </Button>
        )
    }

    return (
        <div className="flex items-center gap-1">
            <div className="flex-1">
                <Input
                    ref={inputRef}
                    type={type}
                    value={editValue}
                    onChange={(e) => dispatch({ type: "setEditValue", value: e.target.value })}
                    onKeyDown={handleKeyDown}
                    onBlur={() => {
                        // Delay to allow button clicks
                        setTimeout(() => {
                            if (isEditing && !isSaving) void handleSave()
                        }, 200)
                    }}
                    className={cn("h-7 text-sm", error && "border-destructive")}
                    disabled={isSaving}
                    aria-label={fieldLabel}
                />
                {error && (
                    <p className="text-xs text-destructive mt-1">{error}</p>
                )}
            </div>
            <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-6"
                onClick={handleSave}
                disabled={isSaving}
                aria-label={`Save ${fieldLabel}`}
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
                aria-label={`Cancel ${fieldLabel}`}
            >
                <XIcon className="size-3 text-destructive" aria-hidden="true" />
            </Button>
        </div>
    )
}
