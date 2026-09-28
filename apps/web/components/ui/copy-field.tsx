"use client"

import * as React from "react"

import { CopyButton } from "@/components/ui/copy-button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type CopyFieldProps = {
    value: string
    /** Accessible name of the copy button, for example "Copy webhook URL". */
    copyLabel: string
    className?: string | undefined
    inputClassName?: string | undefined
} & (
    /** Pair `id` with a visible <Label htmlFor>, or name the input with `aria-label`. */
    | { id: string; "aria-label"?: string | undefined }
    | { id?: string | undefined; "aria-label": string }
)

// Setting an input's value leaves the caret at the end, so focusing it would scroll a long URL
// past its scheme and host. Moving the caret to 0 keeps the start of the value in view.
function showValueStart(event: React.FocusEvent<HTMLInputElement>) {
    const input = event.currentTarget
    input.setSelectionRange(0, 0)
    input.scrollLeft = 0
}

/** Read-only monospace value with the shared CopyButton, for URLs, ids and header templates. */
function CopyField({
    value,
    copyLabel,
    id,
    "aria-label": ariaLabel,
    className,
    inputClassName,
}: CopyFieldProps) {
    return (
        <div data-slot="copy-field" className={cn("flex min-w-0 items-center gap-2", className)}>
            {/* Input keeps its text-base md:text-sm sizing: a smaller mobile font makes iOS zoom on focus. */}
            <Input
                readOnly
                value={value}
                onFocus={showValueStart}
                className={cn("min-w-0 flex-1 text-ellipsis font-mono", inputClassName)}
                {...(id ? { id } : {})}
                {...(ariaLabel ? { "aria-label": ariaLabel } : {})}
            />
            <CopyButton
                value={value}
                variant="outline"
                size="icon"
                aria-label={copyLabel}
                disabled={!value}
            />
        </div>
    )
}

export { CopyField }
export type { CopyFieldProps }
