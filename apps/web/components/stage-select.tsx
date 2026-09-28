"use client"

import * as React from "react"

import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectLabel,
    SelectSeparator,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    ALL_STAGES_VALUE,
    findStageOption,
    getStageOptionLabel,
    type StageOption,
} from "@/lib/stage-options"
import { cn } from "@/lib/utils"

function StageDot({
    color,
    className,
}: {
    color?: string | null | undefined
    className?: string | undefined
}) {
    return (
        <span
            aria-hidden="true"
            data-slot="stage-dot"
            className={cn(
                "inline-block size-2 shrink-0 rounded-full ring-1 ring-foreground/10",
                !color && !className && "bg-muted-foreground",
                className,
            )}
            style={color ? { backgroundColor: color } : undefined}
        />
    )
}

/** Dot plus label. Use it wherever a stage is listed, including radio lists and checkbox grids. */
function StageOptionLabel({ option, className }: { option: StageOption; className?: string }) {
    return (
        <span className={cn("flex min-w-0 items-center gap-2", className)}>
            <StageDot color={option.color} className={option.dotClassName} />
            <span className="truncate">{option.label}</span>
        </span>
    )
}

/** Buckets options by group, keeping first-appearance order of groups and options. */
function groupStageOptions(options: readonly StageOption[]) {
    const groups: Array<{ label: string | undefined; options: StageOption[] }> = []
    for (const option of options) {
        const existing = groups.find((group) => group.label === option.group)
        if (existing) {
            existing.options.push(option)
        } else {
            groups.push({ label: option.group, options: [option] })
        }
    }
    return groups
}

type StageSelectProps = {
    value: string | null | undefined
    onValueChange: (value: string) => void
    options: readonly StageOption[]
    /** Adds the "all" sentinel item first. Filters pass it; pickers that need a stage do not. */
    allLabel?: string | undefined
    placeholder?: string | undefined
    id?: string | undefined
    name?: string | undefined
    disabled?: boolean | undefined
    size?: "sm" | "default" | undefined
    className?: string | undefined
    contentClassName?: string | undefined
    "aria-label"?: string | undefined
    "aria-invalid"?: boolean | undefined
    "aria-describedby"?: string | undefined
}

function StageSelect({
    value,
    onValueChange,
    options,
    allLabel,
    placeholder = "Select a stage",
    id,
    name,
    disabled,
    size,
    className,
    contentClassName,
    "aria-label": ariaLabel,
    "aria-invalid": ariaInvalid,
    "aria-describedby": ariaDescribedBy,
}: StageSelectProps) {
    const groups = groupStageOptions(options)
    const hasAllOption = allLabel !== undefined
    const emptyValue = hasAllOption ? ALL_STAGES_VALUE : ""

    const renderValue = (selected: string | null) => {
        const option = findStageOption(selected, options)
        if (option) return <StageOptionLabel option={option} />
        return getStageOptionLabel(selected, options, {
            allLabel: allLabel ?? placeholder,
            emptyLabel: hasAllOption ? allLabel : placeholder,
        })
    }

    return (
        <Select
            value={value || null}
            onValueChange={(next) => onValueChange(typeof next === "string" && next ? next : emptyValue)}
            disabled={disabled}
            {...(name ? { name } : {})}
        >
            <SelectTrigger
                {...(id ? { id } : {})}
                {...(size ? { size } : {})}
                className={className}
                aria-label={ariaLabel}
                aria-invalid={ariaInvalid}
                aria-describedby={ariaDescribedBy}
            >
                <SelectValue placeholder={hasAllOption ? allLabel : placeholder}>
                    {renderValue}
                </SelectValue>
            </SelectTrigger>
            <SelectContent
                className={cn(
                    "w-max min-w-(--anchor-width) max-w-(--available-width) max-h-[min(28rem,var(--available-height))]",
                    contentClassName,
                )}
            >
                {hasAllOption ? (
                    <>
                        <SelectItem value={ALL_STAGES_VALUE}>{allLabel}</SelectItem>
                        {options.length > 0 ? <SelectSeparator /> : null}
                    </>
                ) : null}
                {groups.map((group, index) => (
                    <React.Fragment key={group.label ?? `group-${index}`}>
                        {index > 0 ? <SelectSeparator /> : null}
                        <SelectGroup className="p-0">
                            {group.label ? <SelectLabel>{group.label}</SelectLabel> : null}
                            {group.options.map((option) => (
                                <SelectItem
                                    key={option.value}
                                    value={option.value}
                                    label={option.label}
                                    disabled={option.disabled}
                                >
                                    {/* SelectItem's ItemText row does not center on the cross axis. */}
                                    <span className="flex flex-1 items-center gap-2">
                                        <StageDot color={option.color} className={option.dotClassName} />
                                        <span className="flex-1">{option.label}</span>
                                        {option.count !== undefined ? (
                                            <span className="text-muted-foreground ml-3 text-xs tabular-nums">
                                                {option.count}
                                            </span>
                                        ) : null}
                                    </span>
                                </SelectItem>
                            ))}
                        </SelectGroup>
                    </React.Fragment>
                ))}
            </SelectContent>
        </Select>
    )
}

export { StageDot, StageOptionLabel, StageSelect, groupStageOptions }
export type { StageSelectProps }
