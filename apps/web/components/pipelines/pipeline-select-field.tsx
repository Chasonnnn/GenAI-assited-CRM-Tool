"use client"

import type * as React from "react"

import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    denormalizeSelectValue,
    getPipelineSelectLabel,
    normalizeSelectValue,
    type PipelineSelectOption,
} from "@/lib/pipelines/stage-editor"
import { cn } from "@/lib/utils"

/** Inline table trigger: reads as text until hovered or focused. */
export const INLINE_SELECT_TRIGGER_CLASS =
    "h-7 w-auto max-w-full justify-start gap-1 border-transparent bg-transparent px-1.5 shadow-none hover:border-input dark:bg-transparent dark:hover:bg-input/30 *:data-[slot=select-value]:truncate"

export function PipelineSelectField({
    id,
    label,
    ariaLabel,
    value,
    options,
    onValueChange,
    disabled = false,
    srOnlyLabel = false,
    labelAddon,
    triggerClassName,
    className,
}: {
    id: string
    label: string
    ariaLabel?: string
    value: string | null | undefined
    options: PipelineSelectOption[]
    onValueChange: (value: string) => void
    disabled?: boolean
    srOnlyLabel?: boolean
    labelAddon?: React.ReactNode
    triggerClassName?: string
    className?: string
}) {
    return (
        <div className={cn(srOnlyLabel ? "min-w-0 text-sm" : "min-w-0 space-y-1.5 text-sm", className)}>
            <Label
                htmlFor={id}
                className={srOnlyLabel ? "sr-only" : "text-muted-foreground flex items-center gap-1 text-xs font-medium"}
            >
                {label}
                {labelAddon}
            </Label>
            <Select
                value={normalizeSelectValue(value)}
                onValueChange={(nextValue) => onValueChange(denormalizeSelectValue(nextValue))}
                disabled={disabled}
            >
                <SelectTrigger
                    id={id}
                    aria-label={ariaLabel ?? label}
                    size="sm"
                    className={cn("w-full", triggerClassName)}
                >
                    <SelectValue placeholder={label}>
                        {(nextValue: string | null) => getPipelineSelectLabel(options, nextValue, label)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false} className="min-w-44">
                    {options.map((option) => (
                        <SelectItem
                            key={normalizeSelectValue(option.value)}
                            value={normalizeSelectValue(option.value)}
                            disabled={option.disabled}
                        >
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}
