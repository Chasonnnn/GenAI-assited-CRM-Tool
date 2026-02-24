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
    type?: "text" | "email" | "tel"
    className?: string
    displayClassName?: string
    validate?: (value: string) => string | null
    label?: string
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
            inputRef.current.select()
        }
    }, [isEditing])

    const handleStartEdit = () => {
        setIsEditing(true)
        setError(null)
    }

    const handleCancel = () => {
        setEditValue(value || "")
        setIsEditing(false)
        setError(null)
    }

    const handleSave = async () => {
        // Validate if provided
        if (validate) {
            const validationError = validate(editValue)
            if (validationError) {
                setError(validationError)
                return
            }
        }

        // Only save if value changed
        if (editValue === (value || "")) {
            setIsEditing(false)
            return
        }

        setIsSaving(true)
        try {
            await onSave(editValue)
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

    const handleDisplayKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
            e.preventDefault()
            handleStartEdit()
        }
    }

    const fieldLabel = label?.trim() || (placeholder && placeholder !== "-" ? placeholder : "field")

    if (!isEditing) {
        return (
            <div
                className={cn(
                    "group flex items-center gap-1 cursor-pointer rounded px-1 -mx-1 hover:bg-muted/50 transition-colors",
                    displayClassName
                )}
                onClick={handleStartEdit}
                role="button"
                tabIndex={0}
                onKeyDown={handleDisplayKeyDown}
                aria-label={`Edit ${fieldLabel}`}
            >
                <span className={cn("text-sm", !value && "text-muted-foreground", className)}>
                    {value || placeholder}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-hidden="true"
                />
            </div>
        )
    }

    return (
        <div className="flex items-center gap-1">
            <div className="flex-1">
                <Input
                    ref={inputRef}
                    type={type}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onBlur={() => {
                        // Delay to allow button clicks
                        setTimeout(() => {
                            if (isEditing && !isSaving) handleSave()
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
                className="h-6 w-6"
                onClick={handleSave}
                disabled={isSaving}
                aria-label={`Save ${fieldLabel}`}
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
                aria-label={`Cancel ${fieldLabel}`}
            >
                <XIcon className="size-3 text-destructive" />
            </Button>
        </div>
    )
}
