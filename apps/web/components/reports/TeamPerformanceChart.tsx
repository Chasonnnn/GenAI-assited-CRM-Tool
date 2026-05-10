"use client"

import { useMemo } from "react"
import dynamic from "next/dynamic"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2Icon, BarChart3Icon } from "lucide-react"
import type { UserPerformanceData } from "@/lib/api/analytics"

interface TeamPerformanceChartProps {
    data: UserPerformanceData[] | undefined
    conversionStageKey?: string | null
    isLoading?: boolean
    isError?: boolean
    title?: string
}

type TeamPerformanceChartDatum = {
    userId: string
    name: string
    fullName: string
    conversion_rate: number
    total_surrogates: number
    converted_count: number
    fill: string
}

type TeamPerformanceBarsProps = {
    chartData: TeamPerformanceChartDatum[]
}

// Color scale for conversion rates
const getConversionColor = (rate: number) => {
    if (rate >= 30) return "#22c55e" // green-500
    if (rate >= 20) return "#3b82f6" // blue-500
    if (rate >= 10) return "#f59e0b" // amber-500
    return "#94a3b8" // slate-400
}

const chartConfig = {
    conversion_rate: { label: "Conversion Rate" },
}

const TeamPerformanceBars = dynamic<TeamPerformanceBarsProps>(
    () =>
        Promise.all([
            import("recharts"),
            import("@/components/ui/chart"),
        ]).then(([{
            Bar,
            BarChart,
            CartesianGrid,
            XAxis,
            YAxis,
            Cell,
        }, { ChartContainer, ChartTooltip, ChartTooltipContent }]) => {
            function TeamPerformanceBarsComponent({ chartData }: TeamPerformanceBarsProps) {
                return (
                    <ChartContainer config={chartConfig} className="h-[300px] w-full">
                        <BarChart data={chartData} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                            <XAxis
                                type="number"
                                domain={[0, Math.max(50, Math.ceil(Math.max(...chartData.map((d) => d.conversion_rate)) / 10) * 10)]}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(value) => `${value}%`}
                            />
                            <YAxis
                                dataKey="name"
                                type="category"
                                tickLine={false}
                                axisLine={false}
                                width={80}
                                fontSize={12}
                            />
                            <ChartTooltip
                                content={<ChartTooltipContent />}
                                cursor={{ fill: "hsl(var(--muted))", opacity: 0.3 }}
                            />
                            <Bar
                                dataKey="conversion_rate"
                                radius={[0, 4, 4, 0]}
                            >
                                {chartData.map((entry) => (
                                    <Cell key={entry.userId} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ChartContainer>
                )
            }

            return TeamPerformanceBarsComponent
        }),
    {
        ssr: false,
        loading: () => (
            <div className="flex h-[300px] items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        ),
    }
)

export function TeamPerformanceChart({
    data,
    conversionStageKey = null,
    isLoading = false,
    isError = false,
    title = "Conversion Rate by Team Member",
}: TeamPerformanceChartProps) {
    const chartData = useMemo(() => {
        if (!data) return []
        return data
            .filter((user) => user.total_surrogates > 0)
            .toSorted((a, b) => b.conversion_rate - a.conversion_rate)
            .slice(0, 10)
            .map((user) => ({
                userId: user.user_id,
                name: user.user_name.split(" ")[0] ?? user.user_name,
                fullName: user.user_name,
                conversion_rate: user.conversion_rate,
                total_surrogates: user.total_surrogates,
                converted_count: conversionStageKey
                    ? (user.stage_counts[conversionStageKey] ?? 0)
                    : 0,
                fill: getConversionColor(user.conversion_rate),
            }))
    }, [conversionStageKey, data])

    const avgConversionRate = useMemo(() => {
        if (!data || data.length === 0) return 0
        const usersWithSurrogates = data.filter((u) => u.total_surrogates > 0)
        if (usersWithSurrogates.length === 0) return 0
        const totalConverted = usersWithSurrogates.reduce(
            (sum, u) =>
                sum + (conversionStageKey ? (u.stage_counts[conversionStageKey] ?? 0) : 0),
            0
        )
        const totalSurrogates = usersWithSurrogates.reduce(
            (sum, u) => sum + u.total_surrogates,
            0
        )
        return totalSurrogates > 0 ? (totalConverted / totalSurrogates) * 100 : 0
    }, [conversionStageKey, data])

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <BarChart3Icon className="size-5" />
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (isError) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <BarChart3Icon className="size-5" />
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-destructive">
                        Unable to load performance data
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (!chartData || chartData.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <BarChart3Icon className="size-5" />
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                        No performance data available
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <BarChart3Icon className="size-5" />
                    {title}
                </CardTitle>
                <CardDescription>
                    Team average: {avgConversionRate.toFixed(1)}% conversion rate
                </CardDescription>
            </CardHeader>
            <CardContent>
                <TeamPerformanceBars chartData={chartData} />

                {/* Legend */}
                <div className="mt-4 flex items-center justify-center gap-6 text-xs">
                    <div className="flex items-center gap-1.5">
                        <div className="size-3 rounded-sm bg-green-500" />
                        <span className="text-muted-foreground">30%+</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="size-3 rounded-sm bg-blue-500" />
                        <span className="text-muted-foreground">20-30%</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="size-3 rounded-sm bg-amber-500" />
                        <span className="text-muted-foreground">10-20%</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="size-3 rounded-sm bg-muted-foreground/60" />
                        <span className="text-muted-foreground">&lt;10%</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
