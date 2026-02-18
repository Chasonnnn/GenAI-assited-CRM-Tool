"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { CheckIcon, XIcon, PencilIcon, Loader2Icon } from "lucide-react"
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

export function InlineDateField({
    value,
    onSave,
    placeholder = "Set date",
    className,
    displayClassName,
    label,
    disabled = false,
}: InlineDateFieldProps) {
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState(value || "")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)
    const inputRef = React.useRef<HTMLInputElement>(null)

    // Reset edit value when prop value changes
    React.useEffect(() => {
        setEditValue(value || "")
    }, [value])

    // Focus input when editing starts
    React.useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus()
        }
    }, [isEditing])

    const handleStartEdit = () => {
        if (disabled) return
        setIsEditing(true)
        setError(null)
    }

    const handleCancel = () => {
        setEditValue(value || "")
        setIsEditing(false)
        setError(null)
    }

    const handleSave = async () => {
        // Only save if value changed
        if (editValue === (value || "")) {
            setIsEditing(false)
            return
        }

        // Validate date if provided
        if (editValue) {
            const parsed = parseISO(editValue)
            if (!isValid(parsed)) {
                setError("Invalid date")
                return
            }
        }

        setIsSaving(true)
        try {
            await onSave(editValue || null)
            setIsEditing(false)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save")
        } finally {
            setIsSaving(false)
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

    if (!isEditing) {
        return (
            <div
                className={cn(
                    "group flex items-center gap-1 rounded px-1 -mx-1 transition-colors",
                    !disabled && "cursor-pointer hover:bg-muted/50",
                    disabled && "opacity-50 cursor-not-allowed",
                    displayClassName
                )}
                onClick={handleStartEdit}
                role="button"
                tabIndex={disabled ? -1 : 0}
                onKeyDown={(e) => {
                    if (!disabled && (e.key === "Enter" || e.key === " ")) {
                        e.preventDefault()
                        handleStartEdit()
                    }
                }}
                aria-label={`Edit ${label}`}
            >
                <span className={cn("text-sm", !displayValue && "text-muted-foreground", className)}>
                    {displayValue || placeholder}
                </span>
                {!disabled && (
                    <PencilIcon
                        className="size-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                        aria-hidden="true"
                    />
                )}
            </div>
        )
    }

    return (
        <div className="flex items-center gap-1">
            <div className="flex-1">
                <Input
                    ref={inputRef}
                    type="date"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className={cn("h-7 w-36 text-sm", error && "border-destructive")}
                    disabled={isSaving}
                    aria-label={label}
                />
                {error && (
                    <p className="text-xs text-destructive mt-1">{error}</p>
                )}
            </div>
            <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handleSave}
                disabled={isSaving}
                aria-label={`Save ${label}`}
            >
                {isSaving ? (
                    <Loader2Icon className="size-3 animate-spin" />
                ) : (
                    <CheckIcon className="size-3 text-green-600" />
                )}
            </Button>
            <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handleCancel}
                disabled={isSaving}
                aria-label={`Cancel ${label}`}
            >
                <XIcon className="size-3 text-destructive" />
            </Button>
        </div>
    )
}
