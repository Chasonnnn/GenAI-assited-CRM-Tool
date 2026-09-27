"use client"

import type * as React from "react"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

type SegmentedToggleOption<T extends string> = {
    value: T
    label: string
    icon?: React.ReactNode
}

/**
 * Single-choice toggle for list toolbars (My/All, List/Calendar). Pressing the active item keeps
 * it selected. With `iconOnlyOnMobile`, labels hide below sm and stay as the accessible name.
 */
export function SegmentedToggle<T extends string>({
    value,
    onValueChange,
    options,
    iconOnlyOnMobile = false,
    "aria-label": ariaLabel,
}: {
    value: T
    onValueChange: (value: T) => void
    options: ReadonlyArray<SegmentedToggleOption<T>>
    iconOnlyOnMobile?: boolean
    "aria-label": string
}) {
    return (
        <ToggleGroup
            value={[value]}
            aria-label={ariaLabel}
            variant="outline"
            spacing={0}
            onValueChange={(next) => {
                const nextValue = Array.isArray(next) ? next[0] : next
                const option = options.find((candidate) => candidate.value === nextValue)
                if (option) onValueChange(option.value)
            }}
        >
            {options.map((option) => (
                <ToggleGroupItem
                    key={option.value}
                    value={option.value}
                    aria-label={iconOnlyOnMobile ? option.label : undefined}
                    className="h-9 bg-background"
                >
                    {option.icon}
                    <span className={iconOnlyOnMobile ? "hidden sm:inline" : undefined}>{option.label}</span>
                </ToggleGroupItem>
            ))}
        </ToggleGroup>
    )
}
