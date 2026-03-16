"use client"

import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
    TrendingUpIcon,
    TrendingDownIcon,
    AlertCircleIcon,
    ArrowUpRightIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

// =============================================================================
// Types
// =============================================================================

interface ChangeIndicator {
    currentValue: number
    previousValue: number
    percentChange?: number | null
    period: string
}

interface KPICardProps {
    title: string
    value: number | string
    subtitle?: string | undefined
    change?: ChangeIndicator | undefined
    href?: string | undefined
    attention?: boolean | undefined
    isLoading?: boolean | undefined
    isError?: boolean | undefined
    onRetry?: (() => void) | undefined
    className?: string | undefined
    icon?: React.ReactNode | undefined
}

// =============================================================================
// Helpers
// =============================================================================

function formatChange(change: ChangeIndicator): { text: string; color: string; icon: React.ReactNode } | null {
    const { currentValue, previousValue, percentChange, period } = change

    // Handle no prior data
    if (previousValue === 0) {
        return null
    }

    if (currentValue === previousValue) {
        return {
            text: "No change",
            color: "text-muted-foreground",
            icon: null,
        }
    }

    if (currentValue === 0) {
        return {
            text: `0 vs ${previousValue} ${period}`,
            color: "text-muted-foreground",
            icon: null,
        }
    }

    // For small absolute numbers, show "X vs Y" instead of percentage
    if (previousValue < 3) {
        const delta = currentValue - previousValue
        const direction = delta > 0 ? "up" : delta < 0 ? "down" : "same"
        const icon = direction === "up" ? (
            <TrendingUpIcon className="size-3" />
        ) : direction === "down" ? (
            <TrendingDownIcon className="size-3" />
        ) : null

        return {
            text: `${currentValue} vs ${previousValue} ${period}`,
            color:
                direction === "up"
                    ? "text-[var(--status-success)]"
                    : direction === "down"
                      ? "text-[var(--status-danger)]"
                      : "text-muted-foreground",
            icon,
        }
    }

    // Standard percentage display
    const effectivePercent = percentChange ?? ((currentValue - previousValue) / previousValue) * 100
    const isPositive = effectivePercent >= 0
    const Icon = isPositive ? TrendingUpIcon : TrendingDownIcon
    const sign = isPositive ? "+" : ""

    return {
        text: `${sign}${Math.round(effectivePercent)}%`,
        color: isPositive ? "text-[var(--status-success)]" : "text-muted-foreground",
        icon: <Icon className="size-3" />,
    }
}

export function KPICard({
    title,
    value,
    subtitle,
    change,
    href,
    attention,
    isLoading,
    isError,
    onRetry,
    className,
    icon,
}: KPICardProps) {
    const changeDisplay = change ? formatChange(change) : null
    const content = (
        <Card className={cn(
            "gap-0 rounded-2xl border border-border/80 bg-card/95 p-0 shadow-none transition-colors",
            href && "cursor-pointer hover:border-primary/30 hover:bg-card",
            className
        )}>
            <CardHeader className="gap-0 px-5 pb-0 pt-5">
                <div className="mb-2 flex items-start justify-between gap-3">
                    <CardTitle className="flex min-w-0 flex-1 items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        {icon && (
                            <span className="flex size-7 items-center justify-center rounded-full border border-border/70 bg-background text-foreground/80">
                                {icon}
                            </span>
                        )}
                        <span className="truncate" title={title}>{title}</span>
                    </CardTitle>
                    {changeDisplay && !isLoading && !isError && (
                        <div className={cn("shrink-0 whitespace-nowrap text-xs font-medium", changeDisplay.color)}>
                            <div className="flex items-center gap-1 rounded-full bg-muted/60 px-2.5 py-1">
                            {changeDisplay.icon}
                            {changeDisplay.text}
                            </div>
                        </div>
                    )}
                    {attention && !isLoading && !isError && (
                        <AlertCircleIcon className="size-4 text-[var(--status-warning)]" />
                    )}
                </div>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col gap-3 px-5 pb-5 pt-0">
                {isLoading ? (
                    <div className="space-y-2">
                        <Skeleton className="h-7 w-20" />
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-4 w-24" />
                    </div>
                ) : isError ? (
                    <div className="flex items-center justify-between text-xs text-destructive">
                        <div className="flex items-center gap-1">
                            <AlertCircleIcon className="size-4" />
                            Unable to load
                        </div>
                        {onRetry && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    onRetry()
                                }}
                            >
                                Retry
                            </Button>
                        )}
                    </div>
                ) : (
                    <>
                        <div className="flex items-end justify-between gap-3">
                            <div className="text-3xl font-semibold leading-none tracking-tight tabular-nums text-foreground sm:text-[2.15rem]">
                                {typeof value === "number" ? value.toLocaleString() : value}
                            </div>
                            {href && (
                                <span className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                                    Open
                                    <ArrowUpRightIcon className="size-3.5" />
                                </span>
                            )}
                        </div>
                        {subtitle && (
                            <p className="max-w-[18rem] text-sm leading-6 text-muted-foreground">{subtitle}</p>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )

    if (href && !isLoading && !isError) {
        return (
            <Link href={href} className="block">
                {content}
            </Link>
        )
    }

    return content
}

// =============================================================================
// Loading Skeleton
// =============================================================================

export function KPICardSkeleton() {
    return (
        <Card className="gap-0 rounded-2xl p-0 shadow-none">
            <CardHeader className="gap-0 px-5 pb-0 pt-5">
                <div className="mb-2 flex items-center justify-between">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-12" />
                </div>
            </CardHeader>
            <CardContent className="space-y-3 px-5 pb-5 pt-0">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-24" />
            </CardContent>
        </Card>
    )
}
