"use client"

import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
    TrendingUpIcon,
    TrendingDownIcon,
    AlertCircleIcon,
    ChevronRightIcon,
} from "lucide-react"
import { Area, AreaChart, ResponsiveContainer } from "recharts"
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
    sparklineData?: number[] | undefined
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
            color: direction === "up" ? "text-green-600" : direction === "down" ? "text-red-600" : "text-muted-foreground",
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
        color: isPositive ? "text-green-600" : "text-muted-foreground",
        icon: <Icon className="size-3" />,
    }
}

// =============================================================================
// Components
// =============================================================================

function Sparkline({ data }: { data: number[] }) {
    if (!data || data.length < 2) return null

    const chartData = data.map((value, index) => ({ index, value }))
    const maxValue = Math.max(...data)
    const minValue = Math.min(...data)
    const hasVariance = maxValue !== minValue

    return (
        <div className="h-8 w-full">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                <AreaChart data={chartData} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
                    <defs>
                        <linearGradient id="sparklineGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.3} />
                            <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.05} />
                        </linearGradient>
                    </defs>
                    <Area
                        type="monotone"
                        dataKey="value"
                        stroke="var(--primary)"
                        strokeWidth={1.5}
                        fill="url(#sparklineGradient)"
                        isAnimationActive={false}
                        dot={false}
                        // If no variance, show a flat line in the middle
                        baseValue={hasVariance ? "dataMin" : (minValue - 1)}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )
}

export function KPICard({
    title,
    value,
    subtitle,
    change,
    sparklineData,
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
            "transition-all h-full flex flex-col gap-0 p-0",
            href && "hover:bg-muted/30 cursor-pointer",
            className
        )}>
            <CardHeader className="p-6 pb-0 gap-0">
                <div className="flex items-center justify-between mb-1">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2 min-w-0 flex-1">
                        {icon}
                        <span className="truncate" title={title}>{title}</span>
                    </CardTitle>
                    {changeDisplay && !isLoading && !isError && (
                        <div className={cn("flex items-center gap-1 text-xs font-medium whitespace-nowrap shrink-0", changeDisplay.color)}>
                            {changeDisplay.icon}
                            {changeDisplay.text}
                        </div>
                    )}
                    {attention && !isLoading && !isError && (
                        <AlertCircleIcon className="size-4 text-amber-500" />
                    )}
                </div>
                <div className="mb-4 h-0" aria-hidden="true" />
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-2 flex-1">
                {isLoading ? (
                    <div className="space-y-2">
                        <Skeleton className="h-8 w-20" />
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-8 w-full" />
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
                        <div className="flex items-baseline justify-between">
                            <div className="text-4xl font-semibold tracking-tight tabular-nums leading-none">
                                {typeof value === "number" ? value.toLocaleString() : value}
                            </div>
                            {href && (
                                <ChevronRightIcon className="size-5 text-muted-foreground" />
                            )}
                        </div>
                        {subtitle && (
                            <p className="text-xs text-muted-foreground">{subtitle}</p>
                        )}
                        {sparklineData && sparklineData.length >= 2 && (
                            <Sparkline data={sparklineData} />
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )

    if (href && !isLoading && !isError) {
        return (
            <Link href={href} className="block h-full">
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
        <Card className="gap-0 p-0">
            <CardHeader className="p-6 pb-0 gap-0">
                <div className="flex items-center justify-between mb-1">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-12" />
                </div>
                <div className="mb-4 h-0" aria-hidden="true" />
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-2">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-8 w-full" />
            </CardContent>
        </Card>
    )
}
