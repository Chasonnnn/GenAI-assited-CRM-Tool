"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { TrendingUpIcon, TrendingDownIcon, SparklesIcon, UsersIcon, CheckCircle2Icon, Loader2Icon, AlertCircleIcon, FacebookIcon, DollarSignIcon } from "lucide-react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Line, LineChart, Pie, PieChart } from "recharts"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent,
} from "@/components/ui/chart"
import { useAnalyticsSummary, useSurrogatesByStatus, useSurrogatesByAssignee, useSurrogatesTrend, useMetaPerformance, useFunnelCompare, useSurrogatesByStateCompare, useCampaigns, useSpendTotals, usePerformanceByUser } from "@/lib/hooks/use-analytics"
import { FunnelChart } from "@/components/charts/funnel-chart"
import { USMapChart } from "@/components/charts/us-map-chart"
import { TeamPerformanceTable } from "@/components/reports/TeamPerformanceTable"
import { TeamPerformanceChart } from "@/components/reports/TeamPerformanceChart"
import { MetaSpendDashboard } from "@/components/reports/MetaSpendDashboard"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { useAuth } from "@/lib/auth-context"
import { useSetAIContext } from "@/lib/context/ai-context"
import { useAIUsageSummary } from "@/lib/hooks/use-ai"
import { toast } from "sonner"
import { formatLocalDate } from "@/lib/utils/date"
import { getCsrfHeaders } from "@/lib/csrf"

// Chart configs
const surrogatesOverviewConfig = {
    count: { label: "Surrogates" },
}

const monthlyTrendsConfig = {
    count: { label: "Surrogates", color: "#3b82f6" },
}

const surrogatesByAssigneeConfig = {
    count: { label: "Surrogates" },
}

// Color palette for charts
const chartColors = [
    "#3b82f6",
    "#22c55e",
    "#f59e0b",
    "#a855f7",
    "#06b6d4",
    "#ef4444",
]

// AI Usage Stats sub-component
function AIUsageStats() {
    const { data: usage, isLoading, isError } = useAIUsageSummary(30)

    if (isLoading) {
        return <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
    }

    if (isError) {
        return <p className="text-xs text-destructive">Unable to load AI usage</p>
    }

    if (!usage || usage.total_requests === 0) {
        return <p className="text-xs text-muted-foreground">No AI usage yet</p>
    }

    const formatTokens = (num: number) => {
        if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
        if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
        return num.toString()
    }

    return (
        <div className="space-y-1">
            <div className="text-2xl font-bold">{usage.total_requests}</div>
            <p className="text-xs text-muted-foreground">requests (30d)</p>
            <div className="flex items-center gap-2 pt-1 text-xs">
                <span className="text-muted-foreground">Tokens:</span>
                <span className="font-medium">{formatTokens(usage.total_tokens)}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Est. cost:</span>
                <span className="font-medium">${usage.total_cost_usd.toFixed(2)}</span>
            </div>
        </div>
    )
}

export default function ReportsPage() {
    const { user } = useAuth()
    const aiEnabled = user?.ai_enabled ?? false

    const [dateRange, setDateRange] = useState<DateRangePreset>('all')
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>({
        from: undefined,
        to: undefined,
    })
    const [selectedCampaign, setSelectedCampaign] = useState<string>('')
    const [isExporting, setIsExporting] = useState(false)
    type PerformanceMode = "cohort" | "activity"
    const isPerformanceMode = (value: string | null): value is PerformanceMode =>
        value === "cohort" || value === "activity"

    const [performanceMode, setPerformanceMode] = useState<PerformanceMode>("cohort")

    // Clear AI context for reports pages (use global mode)
    useSetAIContext(null)

    // Compute date range based on selected option
    const { fromDate, toDate } = useMemo(() => {
        const now = new Date()

        switch (dateRange) {
            case 'all':
                return { fromDate: undefined, toDate: undefined }
            case 'today':
                return {
                    fromDate: formatLocalDate(now),
                    toDate: formatLocalDate(now),
                }
            case 'week':
                return {
                    fromDate: formatLocalDate(new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)),
                    toDate: formatLocalDate(now),
                }
            case 'custom':
                if (customRange.from && customRange.to) {
                    return {
                        fromDate: formatLocalDate(customRange.from),
                        toDate: formatLocalDate(customRange.to),
                    }
                }
                return { fromDate: undefined, toDate: undefined }
            case 'month':
            default:
                return {
                    fromDate: formatLocalDate(new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)),
                    toDate: formatLocalDate(now),
                }
        }
    }, [dateRange, customRange])

    // Fetch data
    const dateParams = {
        ...(fromDate ? { from_date: fromDate } : {}),
        ...(toDate ? { to_date: toDate } : {}),
    }

    const { data: summary, isLoading: summaryLoading, isError: summaryError } = useAnalyticsSummary(dateParams)
    const { data: byStatus, isLoading: byStatusLoading, isError: byStatusError } = useSurrogatesByStatus()
    const { data: byAssignee, isLoading: byAssigneeLoading, isError: byAssigneeError } = useSurrogatesByAssignee()
    const { data: trend, isLoading: trendLoading, isError: trendError } = useSurrogatesTrend(dateParams)
    const { data: metaPerf, isLoading: metaLoading, isError: metaError } = useMetaPerformance(dateParams)
    const { data: spendTotals, isLoading: spendLoading, isError: spendError } = useSpendTotals(dateParams)

    // New hooks for funnel and map
    const { data: campaigns, isLoading: campaignsLoading, isError: campaignsError } = useCampaigns()
    const { data: funnel, isLoading: funnelLoading, isError: funnelError } = useFunnelCompare({
        ...dateParams,
        ...(selectedCampaign ? { ad_id: selectedCampaign } : {}),
    })
    const { data: byState, isLoading: byStateLoading, isError: byStateError } = useSurrogatesByStateCompare({
        ...dateParams,
        ...(selectedCampaign ? { ad_id: selectedCampaign } : {}),
    })

    // Performance by user
    const { data: performanceData, isLoading: performanceLoading, isError: performanceError } = usePerformanceByUser({
        ...dateParams,
        mode: performanceMode,
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

    const totalStatusCount = useMemo(() => {
        return statusChartData.reduce((sum, item) => sum + item.count, 0)
    }, [statusChartData])

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
        const [first] = statusChartData
        if (!first) return null
        return statusChartData.reduce((max, item) => item.count > max.count ? item : max, first)
    }, [statusChartData])

    const topPerformer = useMemo(() => {
        const [first] = assigneeChartData
        if (!first) return null
        return assigneeChartData.reduce((max, item) => item.count > max.count ? item : max, first)
    }, [assigneeChartData])

    const totalSurrogatesInPeriod = useMemo(() => {
        return trendChartData.reduce((sum, d) => sum + d.count, 0)
    }, [trendChartData])

    const formatShortDate = (value: string) => {
        if (!value) return ""
        const parsed = new Date(`${value}T00:00:00`)
        if (Number.isNaN(parsed.getTime())) return value
        return parsed.toLocaleDateString()
    }

    const insightSummary = useMemo(() => {
        const trendText =
            computeTrendPercentage === null
                ? "Trend: not enough data yet."
                : computeTrendPercentage >= 0
                    ? `Trend: up ${computeTrendPercentage}% vs prior period.`
                    : `Trend: down ${Math.abs(computeTrendPercentage)}% vs prior period.`

        let anomalyText = "Anomalies: not enough daily data."
        if (trendChartData.length >= 4) {
            const counts = trendChartData.map((point) => point.count)
            const average = counts.reduce((sum, value) => sum + value, 0) / counts.length
            if (average > 0) {
                const [firstPoint] = trendChartData
                if (!firstPoint) {
                    anomalyText = "Anomalies: no volume yet."
                } else {
                    const maxPoint = trendChartData.reduce((max, point) =>
                        point.count > max.count ? point : max, firstPoint)
                    const minPoint = trendChartData.reduce((min, point) =>
                        point.count < min.count ? point : min, firstPoint)
                const spikeDelta = (maxPoint.count - average) / average
                const dipDelta = (average - minPoint.count) / average

                if (spikeDelta >= 0.6) {
                    anomalyText = `Anomaly: spike on ${formatShortDate(maxPoint.date)} (${maxPoint.count} surrogates, +${Math.round(spikeDelta * 100)}% vs avg).`
                } else if (dipDelta >= 0.6) {
                    anomalyText = `Anomaly: dip on ${formatShortDate(minPoint.date)} (${minPoint.count} surrogates, -${Math.round(dipDelta * 100)}% vs avg).`
                } else {
                    anomalyText = "Anomalies: no major spikes or dips."
                }
                }
            } else {
                anomalyText = "Anomalies: no volume yet."
            }
        }

        const bottleneckText =
            topStatus && totalStatusCount > 0
                ? `Bottleneck: ${topStatus.status} holds ${Math.round((topStatus.count / totalStatusCount) * 100)}% of active surrogates.`
                : "Bottleneck: no dominant stage yet."

        return {
            trend: trendText,
            anomaly: anomalyText,
            bottleneck: bottleneckText,
        }
    }, [computeTrendPercentage, trendChartData, topStatus, totalStatusCount])

    const campaignLabelById = useMemo(() => {
        const map = new Map<string, string>()
        campaigns?.forEach((campaign) => {
            map.set(campaign.ad_id, `${campaign.ad_name} (${campaign.lead_count})`)
        })
        return map
    }, [campaigns])

    const handleExportPDF = async () => {
        setIsExporting(true)
        try {
            // Call backend API which generates PDF with native charts
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
            const params = new URLSearchParams()
            if (fromDate) params.set('from_date', fromDate)
            if (toDate) params.set('to_date', toDate)

            const url = `${baseUrl}/analytics/export/pdf${params.toString() ? `?${params}` : ''}`

            const response = await fetch(url, {
                credentials: 'include',
                headers: { ...getCsrfHeaders() },
            })

            if (!response.ok) {
                throw new Error(`Export failed (${response.status})`)
            }

            // Get filename from Content-Disposition or generate default
            const disposition = response.headers.get('content-disposition') || ''
            const filenameMatch = disposition.match(/filename="([^"]+)"/)
            const filename = filenameMatch?.[1] || `analytics_report_${new Date().toISOString().slice(0, 10)}.pdf`

            // Download the PDF
            const blob = await response.blob()
            const blobUrl = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = blobUrl
            link.download = filename
            document.body.appendChild(link)
            link.click()
            link.remove()
            URL.revokeObjectURL(blobUrl)
        } catch (error) {
            console.error("Failed to export PDF:", error)
            toast.error("Export failed", {
                description: error instanceof Error ? error.message : "Unable to export report.",
            })
        } finally {
            setIsExporting(false)
        }
    }

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
                                <SelectValue placeholder="All">
                                    {(value: string | null) => {
                                        if (!value) return "All"
                                        return campaignLabelById.get(value) ?? "Unknown campaign"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="">All</SelectItem>
                                {campaignsLoading && (
                                    <SelectItem value="__loading__" disabled>
                                        Loading campaigns...
                                    </SelectItem>
                                )}
                                {campaignsError && (
                                    <SelectItem value="__error__" disabled>
                                        Unable to load campaigns
                                    </SelectItem>
                                )}
                                {campaigns?.map(c => (
                                    <SelectItem key={c.ad_id} value={c.ad_id}>
                                        {c.ad_name} ({c.lead_count})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button
                            onClick={handleExportPDF}
                            disabled={isExporting}
                        >
                            {isExporting ? (
                                <>
                                    <Loader2Icon className="size-4 animate-spin" />
                                    Exporting...
                                </>
                            ) : (
                                'Export PDF'
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {/* Quick Stats Row */}
                <div className="grid gap-4 md:grid-cols-4">
                    <Card className="animate-in fade-in-50 duration-500">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Total Surrogates</CardTitle>
                            <TrendingUpIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : summaryError ? (
                                <div className="flex items-center text-xs text-destructive">
                                    <AlertCircleIcon className="mr-1 size-4" />
                                    Unable to load
                                </div>
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">{summary?.total_surrogates ?? 0}</div>
                                    <p className="text-xs text-muted-foreground">Active surrogates</p>
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
                            ) : summaryError ? (
                                <div className="flex items-center text-xs text-destructive">
                                    <AlertCircleIcon className="mr-1 size-4" />
                                    Unable to load
                                </div>
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
                            ) : summaryError ? (
                                <div className="flex items-center text-xs text-destructive">
                                    <AlertCircleIcon className="mr-1 size-4" />
                                    Unable to load
                                </div>
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
                            <CardTitle className="text-sm font-medium">Meta Funnel</CardTitle>
                            <FacebookIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            {metaLoading ? (
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            ) : metaError ? (
                                <div className="flex items-center text-xs text-destructive">
                                    <AlertCircleIcon className="mr-1 size-4" />
                                    Unable to load
                                </div>
                            ) : (
                                <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-muted-foreground">Qualified</span>
                                        <span className="text-sm font-semibold">{metaPerf?.qualification_rate ?? 0}%</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-muted-foreground">Converted</span>
                                        <span className="text-sm font-semibold text-green-600">{metaPerf?.conversion_rate ?? 0}%</span>
                                    </div>
                                    <p className="text-xs text-muted-foreground pt-1">
                                        {metaPerf?.leads_received ?? 0} leads received
                                    </p>
                                </div>
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
                            ) : spendError ? (
                                <div className="flex items-center text-xs text-destructive">
                                    <AlertCircleIcon className="mr-1 size-4" />
                                    Unable to load
                                </div>
                            ) : (
                                <>
                                    <div className="text-2xl font-bold">
                                        ${spendTotals?.total_spend?.toLocaleString() ?? '0'}
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        CPL: ${spendTotals?.cost_per_lead?.toFixed(2) ?? 'N/A'}
                                    </p>
                                    {spendTotals?.sync_status === 'never' && (
                                        <p className="text-xs text-amber-600 mt-1">
                                            No sync data yet
                                        </p>
                                    )}
                                </>
                            )}
                        </CardContent>
                    </Card>

                    {/* AI Usage Card - only show if AI is enabled */}
                    {aiEnabled && (
                        <Card className="animate-in fade-in-50 duration-500 delay-500">
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">AI Usage</CardTitle>
                                <SparklesIcon className="size-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <AIUsageStats />
                            </CardContent>
                        </Card>
                    )}
                </div>

                <Card className="animate-in fade-in-50 duration-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <SparklesIcon className="size-4 text-muted-foreground" />
                            AI Summary
                        </CardTitle>
                        <CardDescription>Lightweight insights from the current report data.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-3 md:grid-cols-3">
                            <div className="rounded-lg border border-border bg-background p-3">
                                <p className="text-xs font-semibold uppercase text-muted-foreground">Trend Shift</p>
                                <p className="mt-1 text-sm font-medium">{insightSummary.trend}</p>
                            </div>
                            <div className="rounded-lg border border-border bg-background p-3">
                                <p className="text-xs font-semibold uppercase text-muted-foreground">Anomalies</p>
                                <p className="mt-1 text-sm font-medium">{insightSummary.anomaly}</p>
                            </div>
                            <div className="rounded-lg border border-border bg-background p-3">
                                <p className="text-xs font-semibold uppercase text-muted-foreground">Bottlenecks</p>
                                <p className="mt-1 text-sm font-medium">{insightSummary.bottleneck}</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Charts Grid */}
                <div className="grid gap-6 md:grid-cols-2">
                    {/* Surrogates by Stage */}
                    <Card className="animate-in fade-in-50 duration-500 delay-400">
                        <CardHeader>
                            <CardTitle>Surrogates by Stage</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {byStatusLoading ? (
                                <div className="flex h-[300px] items-center justify-center">
                                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                                </div>
                            ) : byStatusError ? (
                                <div className="flex h-[300px] items-center justify-center text-destructive">
                                    <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                                </div>
                            ) : statusChartData.length > 0 ? (
                                <ChartContainer config={surrogatesOverviewConfig} className="h-[300px] w-full">
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
                                {byStatusError ? 'Unable to load status data' : topStatus ? `${topStatus.status}: ${topStatus.count} surrogates` : 'No data yet'}
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {byStatusError ? 'Please try again later' : 'Current distribution by stage'}
                            </div>
                        </CardFooter>
                    </Card>

                    {/* Surrogates Trend */}
                    <Card className="animate-in fade-in-50 duration-500 delay-500">
                        <CardHeader>
                            <CardTitle>Surrogates Trend</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {trendLoading ? (
                                <div className="flex h-[300px] items-center justify-center">
                                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                                </div>
                            ) : trendError ? (
                                <div className="flex h-[300px] items-center justify-center text-destructive">
                                    <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
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
                                            stroke="#3b82f6"
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
                                {trendError ? (
                                    'Unable to load trend data'
                                ) : computeTrendPercentage !== null ? (
                                    <>
                                        {computeTrendPercentage >= 0 ? 'Trending up' : 'Trending down'} by {Math.abs(computeTrendPercentage)}%
                                        {computeTrendPercentage >= 0 ? <TrendingUpIcon className="size-4" /> : <TrendingDownIcon className="size-4" />}
                                    </>
                                ) : (
                                    `${totalSurrogatesInPeriod} surrogates in period`
                                )}
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {trendError ? 'Please try again later' : `${trendChartData.length} data points`}
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
                            ) : byAssigneeError ? (
                                <div className="flex h-[300px] items-center justify-center text-destructive">
                                    <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                                </div>
                            ) : assigneeChartData.length > 0 ? (
                                <ChartContainer config={surrogatesByAssigneeConfig} className="h-[300px] w-full">
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
                                    <AlertCircleIcon className="mr-2 size-4" /> No assigned surrogates
                                </div>
                            )}
                        </CardContent>
                        <CardFooter className="flex-col items-start gap-2">
                            <div className="flex gap-2 leading-none font-medium">
                                {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                                {byAssigneeError ? 'Unable to load team data' : topPerformer ? `Top: ${topPerformer.member} (${topPerformer.count} surrogates)` : 'No assignments yet'}
                                {!byAssigneeError && topPerformer && <TrendingUpIcon className="size-4" />}
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {byAssigneeError ? 'Please try again later' : `${assigneeChartData.length} team members`}
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
                            ) : metaError ? (
                                <div className="flex h-[300px] items-center justify-center text-destructive">
                                    <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                                </div>
                            ) : (
                                <ChartContainer config={{
                                    notQualified: { label: "Not Qualified", color: "#94a3b8" },
                                    qualified: { label: "Qualified Only", color: "#3b82f6" },
                                    converted: { label: "Converted", color: "#22c55e" },
                                }} className="h-[300px] w-full">
                                    <PieChart>
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                        <Pie
                                            data={[
                                                {
                                                    name: "Not Qualified",
                                                    value: Math.max(0, (metaPerf?.leads_received ?? 0) - (metaPerf?.leads_qualified ?? 0)),
                                                    fill: "#94a3b8"
                                                },
                                                {
                                                    name: "Qualified Only",
                                                    value: Math.max(0, (metaPerf?.leads_qualified ?? 0) - (metaPerf?.leads_converted ?? 0)),
                                                    fill: "#3b82f6"
                                                },
                                                {
                                                    name: "Converted",
                                                    value: metaPerf?.leads_converted ?? 0,
                                                    fill: "#22c55e"
                                                },
                                            ]}
                                            dataKey="value"
                                            nameKey="name"
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={60}
                                            outerRadius={100}
                                            label={({ name, value }) => value > 0 ? `${name}: ${value}` : ''}
                                        />
                                        <ChartLegend content={<ChartLegendContent />} />
                                    </PieChart>
                                </ChartContainer>
                            )}
                        </CardContent>
                        <CardFooter className="flex-col items-start gap-2">
                            <div className="flex gap-2 leading-none font-medium">
                                {metaError ? 'Unable to load performance data' : metaPerf?.avg_time_to_convert_hours
                                    ? `Avg ${Math.round(metaPerf.avg_time_to_convert_hours / 24)} days to convert`
                                    : 'No conversion data yet'
                                }
                            </div>
                            <div className="text-muted-foreground leading-none">
                                {metaError ? 'Please try again later' : `${metaPerf?.leads_received ?? 0} leads received • ${metaPerf?.conversion_rate ?? 0}% conversion rate`}
                            </div>
                        </CardFooter>
                    </Card>
                </div>

                {/* Funnel & Map Charts */}
                <div className="mt-6 grid gap-6 lg:grid-cols-2">
                    <FunnelChart
                        data={funnel}
                        isLoading={funnelLoading}
                        isError={funnelError}
                        title="Conversion Funnel"
                    />
                    <USMapChart
                        data={byState}
                        isLoading={byStateLoading}
                        isError={byStateError}
                        title="Surrogates by State"
                    />
                </div>

                {/* Meta Spend Analytics Dashboard */}
                <div className="mt-8">
                    <MetaSpendDashboard dateParams={dateParams} />
                </div>

                {/* Individual Performance Section */}
                <div className="mt-6 space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold">Individual Performance</h2>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Mode:</span>
                            <Select
                                value={performanceMode}
                                onValueChange={(value) => {
                                    if (isPerformanceMode(value)) {
                                        setPerformanceMode(value)
                                    }
                                }}
                            >
                                <SelectTrigger className="w-40">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="cohort">Created Cohort</SelectItem>
                                    <SelectItem value="activity">Activity Window</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        {performanceMode === 'cohort'
                            ? 'Showing metrics for surrogates created within the selected date range, grouped by current owner.'
                            : 'Showing metrics for surrogates with status transitions within the selected date range.'}
                    </p>
                    <div className="grid gap-6 lg:grid-cols-2">
                        <TeamPerformanceChart
                            data={performanceData?.data}
                            isLoading={performanceLoading}
                            isError={performanceError}
                        />
                        <TeamPerformanceTable
                            data={performanceData?.data}
                            unassigned={performanceData?.unassigned}
                            isLoading={performanceLoading}
                            isError={performanceError}
                            {...(performanceData?.as_of ? { asOf: performanceData.as_of } : {})}
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}
