"use client"

import type * as React from "react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/** Button that stays focusable while disabled so the blocking reason shows in a tooltip. */
export function ReasonButton({
    reason,
    disabled,
    className,
    children,
    ...props
}: React.ComponentProps<typeof Button> & { reason: string | null }) {
    if (!reason) {
        return (
            <Button size="sm" disabled={disabled} className={className} {...props}>
                {children}
            </Button>
        )
    }
    return (
        <Tooltip>
            <TooltipTrigger
                render={
                    <Button
                        size="sm"
                        disabled
                        focusableWhenDisabled
                        className={cn("data-disabled:cursor-not-allowed data-disabled:opacity-50", className)}
                        {...props}
                    />
                }
            >
                {children}
            </TooltipTrigger>
            <TooltipContent>{reason}</TooltipContent>
        </Tooltip>
    )
}
