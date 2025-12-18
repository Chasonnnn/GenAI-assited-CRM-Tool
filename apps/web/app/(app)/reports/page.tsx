"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ChevronDownIcon, TrendingUpIcon, TrendingDownIcon, SparklesIcon, UsersIcon, CheckCircle2Icon, Loader2Icon, AlertCircleIcon, FacebookIcon, DollarSignIcon } from "lucide-react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Line, LineChart, Pie, PieChart } from "recharts"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent,
} from "@/components/ui/chart"
import { useAnalyticsSummary, useCasesByStatus, useCasesByAssignee, useCasesTrend, useMetaPerformance, useFunnelCompare, useCasesByStateCompare, useCampaigns, useMetaSpend } from "@/lib/hooks/use-analytics"
import { FunnelChart } from "@/components/charts/funnel-chart"
import { USMapChart } from "@/components/charts/us-map-chart"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { useAuth } from "@/lib/auth-context"

// Chart configs
const casesOverviewConfig = {
    count: { label: "Cases" },
}

const monthlyTrendsConfig = {
    count: { label: "Cases", color: "hsl(var(--chart-1))" },
}

const casesByAssigneeConfig = {
    count: { label: "Cases" },
}

// Color palette for charts
const chartColors = [
    "hsl(var(--chart-1))",
    "hsl(var(--chart-2))",
    "hsl(var(--chart-3))",
    "hsl(var(--chart-4))",
    "hsl(var(--chart-5))",
    "hsl(var(--chart-6))",
]

export default function ReportsPage() {
    const { user } = useAuth()
    const aiEnabled = user?.ai_enabled ?? false

    const [dateRange, setDateRange] = useState<DateRangePreset>('all')
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>({
        from: undefined,
        to: undefined,
    })
    const [selectedCampaign, setSelectedCampaign] = useState<string>('')

    // Compute date range based on selected option
    const { fromDate, toDate } = useMemo(() => {
        const now = new Date()

        switch (dateRange) {
            case 'all':
                return { fromDate: undefined, toDate: undefined }
            case 'today':
                return {
                    fromDate: now.toISOString().split('T')[0],
                    toDate: now.toISOString().split('T')[0],
                }
            case 'week':
                return {
                    fromDate: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                    toDate: now.toISOString().split('T')[0],
                }
            case 'custom':
                if (customRange.from && customRange.to) {
                    return {
                        fromDate: customRange.from.toISOString().split('T')[0],
                        toDate: customRange.to.toISOString().split('T')[0],
                    }
                }
                return { fromDate: undefined, toDate: undefined }
            case 'month':
            default:
                return {
                    fromDate: new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                    toDate: now.toISOString().split('T')[0],
                }
        }
    }, [dateRange, customRange])

    // Fetch data
    const { data: summary, isLoading: summaryLoading } = useAnalyticsSummary({ from_date: fromDate, to_date: toDate })
    const { data: byStatus, isLoading: byStatusLoading } = useCasesByStatus()
    const { data: byAssignee, isLoading: byAssigneeLoading } = useCasesByAssignee()
    const { data: trend, isLoading: trendLoading } = useCasesTrend({ from_date: fromDate, to_date: toDate })
    const { data: metaPerf, isLoading: metaLoading } = useMetaPerformance({ from_date: fromDate, to_date: toDate })
    const { data: metaSpend, isLoading: spendLoading } = useMetaSpend({ from_date: fromDate, to_date: toDate })

    // New hooks for funnel and map
    const { data: campaigns } = useCampaigns()
    const { data: funnel, isLoading: funnelLoading } = useFunnelCompare({
        from_date: fromDate,
        to_date: toDate,
        ad_id: selectedCampaign || undefined
    })
    const { data: byState, isLoading: byStateLoading } = useCasesByStateCompare({
        from_date: fromDate,
        to_date: toDate,
        ad_id: selectedCampaign || undefined
    })

    // Transform data for charts
    const statusChartData = (byStatus || []).map((item, i) => ({
        status: item.status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        count: item.count,
        fill: chartColors[i % chartColors.length],
    }))

    const assigneeChartData = (byAssignee || [])
        .filter(item => item.user_email)
        .slice(0, 5)
        .map((item, i) => ({
            member: item.user_email?.split('@')[0] || 'Unassigned',
            count: item.count,
            fill: chartColors[i % chartColors.length],
        }))

    const trendChartData = (trend || []).map(item => ({
        date: item.date,
        count: item.count,
    }))

    // Compute trend statistics from real data
    const computeTrendPercentage = useMemo(() => {
        if (!trend || trend.length < 2) return null
        const midpoint = Math.floor(trend.length / 2)
        const firstHalf = trend.slice(0, midpoint).reduce((sum, d) => sum + d.count, 0)
        const secondHalf = trend.slice(midpoint).reduce((sum, d) => sum + d.count, 0)
        if (firstHalf === 0) return secondHalf > 0 ? 100 : 0
        return Math.round(((secondHalf - firstHalf) / firstHalf) * 100)
    }, [trend])

    const topStatus = useMemo(() => {
        if (!statusChartData.length) return null
        return statusChartData.reduce((max, item) => item.count > max.count ? item : max, statusChartData[0])
    }, [statusChartData])

    const topPerformer = useMemo(() => {
        if (!assigneeChartData.length) return null
        return assigneeChartData.reduce((max, item) => item.count > max.count ? item : max, assigneeChartData[0])
    }, [assigneeChartData])

    const totalCasesInPeriod = useMemo(() => {
        return trendChartData.reduce((sum, d) => sum + d.count, 0)
    }, [trendChartData])

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Reports</h1>
                    <div className="flex items-center gap-3">
                        <DateRangePicker
                            preset={dateRange}
                            onPresetChange={setDateRange}
                            customRange={customRange}
                            onCustomRangeChange={setCustomRange}
                        />
                        <Select value={selectedCampaign} onValueChange={(v) => setSelectedCampaign(v || '')}>
                            <SelectTrigger className="w-48">
                                <SelectValue placeholder="All" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="">All</SelectItem>
                                {campaigns?.map(c => (
                                    <SelectItem key={c.ad_id} value={c.ad_id}>
                                        {c.ad_name} ({c.lead_count})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <DropdownMenu>
                            <DropdownMenuTrigger className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                                Export
                                <ChevronDownIcon className="size-4" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem>Export PDF</DropdownMenuItem>
                                <DropdownMenuItem>Export CSV</DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {/* Quick Stats Row */}
                <div className="grid gap-4 md:grid-cols-4">
                    <Card className="animate-in fade-in-50 duration-500">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Total Cases</CardTitle>
                            <TrendingUpIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">{summary?.total_cases ?? 0}</div>
                                    <p className="text-xs text-muted-foreground">Active cases</p>
                                </>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-100">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">New This Period</CardTitle>
                            <UsersIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">{summary?.new_this_period ?? 0}</div>
                                    <p className="text-xs text-muted-foreground">Last 30 days</p>
                                </>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-200">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Qualified Rate</CardTitle>
                            <CheckCircle2Icon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">{summary?.qualified_rate ?? 0}%</div>
                                    <p className="text-xs text-muted-foreground">Qualified + approved</p>
                                </>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-300">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Meta Conversion</CardTitle>
                            <FacebookIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {metaLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">{metaPerf?.conversion_rate ?? 0}%</div>
                                    <p className="text-xs text-muted-foreground">
                                        {metaPerf?.leads_converted ?? 0} / {metaPerf?.leads_received ?? 0} leads
                                    </p>
                                </>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-400">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Ad Spend</CardTitle>
                            <DollarSignIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {spendLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">
                                        ${metaSpend?.total_spend?.toLocaleString() ?? '0'}
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        CPL: ${metaSpend?.cost_per_lead?.toFixed(2) ?? 'N/A'}
                                    </p>
                                </>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Charts Grid */}
                <div className="grid gap-6 md:grid-cols-2">
                    {/* Cases by Status */}
                    <Card className="animate-in fade-in-50 duration-500 delay-400">
                        <CardHeader>
                            <CardTitle>Cases by Status</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {byStatusLoading ? (
                                <div className="flex h-[300px] items-center justify-center">
                                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                                </div>
                            ) : statusChartData.length > 0 ? (
                                <ChartContainer config={casesOverviewConfig} className="h-[300px] w-full">
                                    <BarChart data={statusChartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="status" tickLine={false} axisLine={false} fontSize={12} />
                                        <YAxis tickLine={false} axisLine={false} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                        <Bar dataKey="count" radius={[8, 8, 0, 0]} />
                                    </BarChart>
                                </ChartContainer>
                            ) : (
                                <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                                    <AlertCircleIcon className="mr-2 size-4" /> No data available
                                </div>
                            )}
                        </CardContent>
                        <CardFooter className="flex-col items-start gap-2">
                            <div className="flex gap-2 leading-none font-medium">
                                {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                                {topStatus ? `${topStatus.status}: ${topStatus.count} cases` : 'No data yet'}
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {aiEnabled ? 'AI insight coming soon' : 'Current distribution by status'}
                            </div>
                        </CardFooter>
                    </Card>

                    {/* Cases Trend */}
                    <Card className="animate-in fade-in-50 duration-500 delay-500">
                        <CardHeader>
                            <CardTitle>Cases Trend</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {trendLoading ? (
                                <div className="flex h-[300px] items-center justify-center">
                                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                                </div>
                            ) : trendChartData.length > 0 ? (
                                <ChartContainer config={monthlyTrendsConfig} className="h-[300px] w-full">
                                    <LineChart data={trendChartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={12} />
                                        <YAxis tickLine={false} axisLine={false} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                        <Line
                                            type="monotone"
                                            dataKey="count"
                                            stroke="hsl(var(--chart-1))"
                                            strokeWidth={2}
                                            dot={{ r: 4 }}
                                        />
                                    </LineChart>
                                </ChartContainer>
                            ) : (
                                <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                                    <AlertCircleIcon className="mr-2 size-4" /> No data available
                                </div>
                            )}
                        </CardContent>
                        <CardFooter className="flex-col items-start gap-2">
                            <div className="flex gap-2 leading-none font-medium">
                                {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                                {computeTrendPercentage !== null ? (
                                    <>
                                        {computeTrendPercentage >= 0 ? 'Trending up' : 'Trending down'} by {Math.abs(computeTrendPercentage)}%
                                        {computeTrendPercentage >= 0 ? <TrendingUpIcon className="size-4" /> : <TrendingDownIcon className="size-4" />}
                                    </>
                                ) : (
                                    `${totalCasesInPeriod} cases in period`
                                )}
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {aiEnabled ? 'AI insight coming soon' : `${trendChartData.length} data points`}
                            </div>
                        </CardFooter>
                    </Card>

                    {/* Team Performance */}
                    <Card className="animate-in fade-in-50 duration-500 delay-[600ms]">
                        <CardHeader>
                            <CardTitle>Team Performance</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {byAssigneeLoading ? (
                                <div className="flex h-[300px] items-center justify-center">
                                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                                </div>
                            ) : assigneeChartData.length > 0 ? (
                                <ChartContainer config={casesByAssigneeConfig} className="h-[300px] w-full">
                                    <BarChart data={assigneeChartData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tickLine={false} axisLine={false} />
                                        <YAxis dataKey="member" type="category" tickLine={false} axisLine={false} width={100} fontSize={12} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                        <Bar dataKey="count" radius={[0, 8, 8, 0]} />
                                    </BarChart>
                                </ChartContainer>
                            ) : (
                                <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                                    <AlertCircleIcon className="mr-2 size-4" /> No assigned cases
                                </div>
                            )}
                        </CardContent>
                        <CardFooter className="flex-col items-start gap-2">
                            <div className="flex gap-2 leading-none font-medium">
                                {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                                {topPerformer ? `Top: ${topPerformer.member} (${topPerformer.count} cases)` : 'No assignments yet'}
                                {topPerformer && <TrendingUpIcon className="size-4" />}
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {aiEnabled ? 'AI insight coming soon' : `${assigneeChartData.length} team members`}
                            </div>
                        </CardFooter>
                    </Card>

                    {/* Meta Performance */}
                    <Card className="animate-in fade-in-50 duration-500 delay-700">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <FacebookIcon className="size-5 text-blue-600" />
                                Meta Lead Ads Performance
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {metaLoading ? (
                                <div className="flex h-[300px] items-center justify-center">
                                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                                </div>
                            ) : (
                                <div className="grid h-[300px] grid-rows-2 gap-4 p-4">
                                    <div className="flex items-center justify-between rounded-lg border p-4">
                                        <div>
                                            <p className="text-sm text-muted-foreground">Leads Received</p>
                                            <p className="text-3xl font-bold">{metaPerf?.leads_received ?? 0}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Leads Converted</p>
                                            <p className="text-3xl font-bold text-green-600">{metaPerf?.leads_converted ?? 0}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Conversion Rate</p>
                                            <p className="text-3xl font-bold text-blue-600">{metaPerf?.conversion_rate ?? 0}%</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center justify-center rounded-lg bg-muted/50 p-4">
                                        <div className="text-center">
                                            <p className="text-sm text-muted-foreground">Avg Time to Convert</p>
                                            <p className="text-4xl font-bold">
                                                {metaPerf?.avg_time_to_convert_hours
                                                    ? `${metaPerf.avg_time_to_convert_hours}h`
                                                    : '—'
                                                }
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                        <CardFooter className="text-sm text-muted-foreground">Last 30 days</CardFooter>
                    </Card>
                </div>

                {/* Funnel & Map Charts */}
                <div className="mt-6 grid gap-6 lg:grid-cols-2">
                    <FunnelChart
                        data={funnel}
                        isLoading={funnelLoading}
                        title="Conversion Funnel"
                    />
                    <USMapChart
                        data={byState}
                        isLoading={byStateLoading}
                        title="Cases by State"
                    />
                </div>
            </div>
        </div>
    )
}
