"use client"

import type * as React from "react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

/** Button that stays focusable while disabled so the blocking reason shows in a tooltip. */
export function ReasonButton({
    reason,
    disabled,
    children,
    ...props
}: React.ComponentProps<typeof Button> & { reason: string | null }) {
    if (!reason) {
        return (
            <Button size="sm" disabled={disabled} {...props}>
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
                        className="data-disabled:cursor-not-allowed data-disabled:opacity-50"
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
