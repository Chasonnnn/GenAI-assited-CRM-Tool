"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button, buttonVariants } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import {
    TrendingUpIcon,
    AlertCircleIcon,
    PlusIcon,
    LockIcon,
} from "lucide-react"
import { useSurrogatesTrend } from "@/lib/hooks/use-analytics"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useDashboardFilters } from "../context/dashboard-filters"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { ApiError } from "@/lib/api"

type TrendPeriod = "day" | "week" | "month"

const periodLabels: Record<TrendPeriod, string> = {
    day: "Daily",
    week: "Weekly",
    month: "Monthly",
}

export function TrendChart() {
    const { getDateParams, filters, setDateRange } = useDashboardFilters()
    const [period, setPeriod] = useState<TrendPeriod>("day")

    const dateParams = getDateParams()
    const trendParams = {
        period,
        ...dateParams,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const { data, isLoading, isError, error, refetch } = useSurrogatesTrend(trendParams)
    const orgStatsQuery = useSurrogateStats()
    const isRestricted = error instanceof ApiError && error.status === 403
    const orgTotal = orgStatsQuery.data?.total
    const hasOrgSurrogates = (orgTotal ?? 0) > 0

    // Transform data for chart
    const chartData = useMemo(() => {
        if (!data?.length) return []
        return data.map((item) => ({
            date: parseDateInput(item.date).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
            }),
            surrogates: item.count,
        }))
    }, [data])

    // Calculate total for subtitle
    const totalCount = useMemo(() => {
        if (!data?.length) return 0
        return data.reduce((sum, item) => sum + item.count, 0)
    }, [data])

    const buildSurrogatesUrl = () => {
        const params = new URLSearchParams()
        if (filters.dateRange !== "all") {
            params.set("range", filters.dateRange)
        }
        if (filters.dateRange === "custom" && filters.customRange.from) {
            params.set("from", formatLocalDate(filters.customRange.from))
            if (filters.customRange.to) {
                params.set("to", formatLocalDate(filters.customRange.to))
            }
        }
        const query = params.toString()
        return `/surrogates${query ? `?${query}` : ""}`
    }

    const handleAdjustRange = () => {
        if (filters.dateRange !== "all") {
            setDateRange("all")
        }
    }

    return (
        <Card className="h-full flex flex-col gap-0 p-0">
            <CardHeader className="p-6 pb-0 gap-0">
                <div className="flex items-center justify-between mb-1">
                    <CardTitle className="text-base font-semibold">Surrogates Trend</CardTitle>
                    <ToggleGroup
                        value={[period]}
                        onValueChange={(value) => {
                            const nextValue = Array.isArray(value) ? value[0] : value
                            if (nextValue === "day" || nextValue === "week" || nextValue === "month") {
                                setPeriod(nextValue)
                            }
                        }}
                        variant="outline"
                        size="sm"
                        spacing={0}
                        className="h-8"
                    >
                        <ToggleGroupItem value="day" className="h-8">Day</ToggleGroupItem>
                        <ToggleGroupItem value="week" className="h-8">Week</ToggleGroupItem>
                        <ToggleGroupItem value="month" className="h-8">Month</ToggleGroupItem>
                    </ToggleGroup>
                </div>
                <CardDescription className="text-sm text-muted-foreground mb-4">
                    {periodLabels[period]} new surrogates
                    {totalCount > 0 && ` (${totalCount} total)`}
                </CardDescription>
            </CardHeader>
            <CardContent className="px-4 pb-6 pt-0 flex-1">
                {isLoading ? (
                    <div className="h-[320px] flex items-center justify-center">
                        <div className="space-y-3 w-full">
                            <Skeleton className="h-[280px] w-full" />
                            <div className="flex justify-between">
                                <Skeleton className="h-4 w-12" />
                                <Skeleton className="h-4 w-12" />
                                <Skeleton className="h-4 w-12" />
                                <Skeleton className="h-4 w-12" />
                            </div>
                        </div>
                    </div>
                ) : isRestricted ? (
                    <div className="flex flex-col items-center justify-center h-[320px] gap-3 text-center">
                        <LockIcon className="size-8 text-muted-foreground" />
                        <div>
                            <p className="text-sm font-medium">Analytics unavailable</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                Ask an admin to grant access to analytics.
                            </p>
                        </div>
                    </div>
                ) : isError ? (
                    <div className="flex flex-col items-center justify-center h-[320px] gap-3">
                        <AlertCircleIcon className="size-8 text-destructive" />
                        <div className="text-center">
                            <p className="text-sm font-medium text-destructive">Analytics unavailable</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                We couldn’t load trend data.
                            </p>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => refetch()}>
                            Retry
                        </Button>
                    </div>
                ) : chartData.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-[320px] text-center">
                        <TrendingUpIcon className="size-12 text-muted-foreground/50 mb-4" />
                        {orgTotal === 0 ? (
                            <>
                                <h4 className="font-medium text-foreground">No surrogates yet</h4>
                                <p className="text-sm text-muted-foreground mt-1 mb-4">
                                    Add your first surrogate to start tracking trends.
                                </p>
                                <Link href="/surrogates?new=true" className={buttonVariants({ size: "sm" })}>
                                    <PlusIcon className="size-4 mr-2" />
                                    Add Surrogate
                                </Link>
                            </>
                        ) : (
                            <>
                                <h4 className="font-medium text-foreground">No new surrogates in this period</h4>
                                <p className="text-sm text-muted-foreground mt-1 mb-4">
                                    Try a wider range or review existing surrogates.
                                </p>
                                <div className="flex flex-wrap items-center justify-center gap-2">
                                    <Link
                                        href={buildSurrogatesUrl()}
                                        className={buttonVariants({ size: "sm" })}
                                    >
                                        View surrogates
                                    </Link>
                                    <Button variant="ghost" size="sm" onClick={handleAdjustRange}>
                                        Adjust date range
                                    </Button>
                                </div>
                            </>
                        )}
                    </div>
                ) : (
                    <ChartContainer
                        config={{
                            surrogates: {
                                label: "Surrogates",
                                color: "var(--primary)",
                            },
                        }}
                        className="h-[320px] w-full"
                    >
                        <AreaChart
                            accessibilityLayer
                            data={chartData}
                            margin={{ left: 0, right: 8, top: 12, bottom: 8 }}
                        >
                            <defs>
                                <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="var(--color-surrogates)" stopOpacity={0.12} />
                                    <stop offset="100%" stopColor="var(--color-surrogates)" stopOpacity={0.02} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid
                                vertical={false}
                                strokeDasharray="3 3"
                                stroke="var(--border)"
                                strokeOpacity={0.15}
                            />
                            <XAxis
                                dataKey="date"
                                tickLine={false}
                                axisLine={false}
                                tickMargin={8}
                                tick={{ fontSize: 11 }}
                                tickCount={5}
                                interval="preserveStartEnd"
                                minTickGap={20}
                            />
                            <YAxis
                                tickLine={false}
                                axisLine={false}
                                width={32}
                                tickMargin={6}
                                tick={{ fontSize: 12 }}
                                allowDecimals={false}
                            />
                            <ChartTooltip
                                cursor={{ stroke: "var(--border)" }}
                                content={<ChartTooltipContent indicator="line" />}
                            />
                            <Area
                                dataKey="surrogates"
                                type="monotone"
                                fill="url(#trendGradient)"
                                stroke="var(--color-surrogates)"
                                strokeWidth={2}
                            />
                        </AreaChart>
                    </ChartContainer>
                )}
            </CardContent>
        </Card>
    )
}
