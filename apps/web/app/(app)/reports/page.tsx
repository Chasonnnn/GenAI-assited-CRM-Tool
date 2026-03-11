"use client"

import { useState, useMemo } from "react"
import dynamic from "next/dynamic"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Loader2Icon } from "lucide-react"
import { useAnalyticsSummary, useSurrogatesByStatus, useSurrogatesByAssignee, useSurrogatesTrend, useMetaPerformance, useFunnelCompare, useSurrogatesByStateCompare, useCampaigns, useSpendTotals, usePerformanceByUser } from "@/lib/hooks/use-analytics"
import { TeamPerformanceTable } from "@/components/reports/TeamPerformanceTable"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/lib/auth-context"
import { useSetAIContext } from "@/lib/context/ai-context"
import { toast } from "sonner"
import { formatLocalDate } from "@/lib/utils/date"
import { getCsrfHeaders } from "@/lib/csrf"
import { getReportSeriesColor } from "@/lib/report-theme"

const ReportsChartsGrid = dynamic(
    () => import("./components/ReportsChartsGrid").then((mod) => mod.ReportsChartsGrid),
    {
        ssr: false,
        loading: () => (
            <div className="grid gap-6 md:grid-cols-2">
                <Skeleton className="h-[380px] w-full rounded-lg" />
                <Skeleton className="h-[380px] w-full rounded-lg" />
                <Skeleton className="h-[380px] w-full rounded-lg" />
                <Skeleton className="h-[380px] w-full rounded-lg" />
            </div>
        ),
    }
)

const FunnelChart = dynamic(
    () => import("@/components/charts/funnel-chart").then((mod) => mod.FunnelChart),
    { ssr: false, loading: () => <Skeleton className="h-[320px] w-full rounded-lg" /> }
)

const USMapChart = dynamic(
    () => import("@/components/charts/us-map-chart").then((mod) => mod.USMapChart),
    { ssr: false, loading: () => <Skeleton className="h-[320px] w-full rounded-lg" /> }
)

const TeamPerformanceChart = dynamic(
    () => import("@/components/reports/TeamPerformanceChart").then((mod) => mod.TeamPerformanceChart),
    { ssr: false, loading: () => <Skeleton className="h-[320px] w-full rounded-lg" /> }
)

const MetaSpendDashboard = dynamic(
    () => import("@/components/reports/MetaSpendDashboard").then((mod) => mod.MetaSpendDashboard),
    { ssr: false, loading: () => <Skeleton className="h-[360px] w-full rounded-lg" /> }
)

export default function ReportsPage() {
    const { user } = useAuth()

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
    const { data: spendTotals } = useSpendTotals(dateParams)

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
        fill: getReportSeriesColor(i),
    }))

    const assigneeChartData = (byAssignee || [])
        .filter(item => item.user_email)
        .slice(0, 5)
        .map((item, i) => ({
            member: item.user_email?.split('@')[0] || 'Unassigned',
            count: item.count,
            fill: getReportSeriesColor(i),
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

    const headerDescription = useMemo(() => {
        if (dateRange === "all") {
            return "A calmer analyst view of portfolio health, conversion flow, and paid acquisition efficiency."
        }
        if (dateRange === "custom" && customRange.from && customRange.to) {
            return `A focused report for ${customRange.from.toLocaleDateString()} to ${customRange.to.toLocaleDateString()}.`
        }
        return "A focused report for the currently selected reporting window."
    }, [customRange.from, customRange.to, dateRange])

    const analystSummary = useMemo(() => {
        if (summaryLoading) {
            return "Loading the current reporting window."
        }
        if (summaryError) {
            return "Core portfolio metrics are temporarily unavailable."
        }

        const total = summary?.total_surrogates ?? 0
        const newThisPeriod = summary?.new_this_period ?? 0
        const qualifiedRate = summary?.pre_qualified_rate ?? 0

        return `${total.toLocaleString()} active surrogates are in the portfolio. ${newThisPeriod.toLocaleString()} entered during this reporting window, and ${qualifiedRate}% are already pre-qualified or approved.`
    }, [summary, summaryError, summaryLoading])

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
        <div className="flex min-h-screen flex-col bg-background">
            <div className="border-b border-border/80 bg-background/80">
                <div className="flex flex-col gap-5 px-6 py-5 xl:flex-row xl:items-end xl:justify-between">
                    <div className="space-y-2">
                        <h1 className="font-display text-4xl font-semibold tracking-tight text-foreground">
                            Reports
                        </h1>
                        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                            {headerDescription}
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        <DateRangePicker
                            preset={dateRange}
                            onPresetChange={setDateRange}
                            customRange={customRange}
                            onCustomRangeChange={setCustomRange}
                        />
                        <Select value={selectedCampaign} onValueChange={(v) => setSelectedCampaign(v || '')}>
                            <SelectTrigger className="w-full sm:w-56">
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
                        <Button onClick={handleExportPDF} disabled={isExporting}>
                            {isExporting ? (
                                <>
                                    <Loader2Icon className="size-4 animate-spin" />
                                    Exporting...
                                </>
                            ) : (
                                "Export PDF"
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            <div className="flex-1 space-y-8 p-5 sm:p-6 xl:p-8">
                <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
                    <div className="overflow-hidden rounded-[28px] border border-border/80 bg-card/95 shadow-sm">
                        <div className="flex h-full flex-col gap-6 p-6 sm:p-8">
                            <div className="space-y-4">
                                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                                    Analyst Summary
                                </p>
                                <div className="flex flex-wrap items-end gap-4">
                                    <div className="font-display text-6xl font-semibold leading-none tracking-tight text-foreground sm:text-7xl">
                                        {summary?.total_surrogates ?? 0}
                                    </div>
                                    <div className="max-w-xl space-y-2 pb-1">
                                        <p className="text-lg font-medium text-foreground">
                                            Active surrogates in the portfolio.
                                        </p>
                                        <p className="text-sm leading-6 text-muted-foreground">
                                            {analystSummary}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-y border-border/70 py-4 text-sm">
                                <div className="flex items-center gap-2">
                                    <span className="text-muted-foreground">New this period</span>
                                    <span className="font-semibold text-foreground">
                                        {summary?.new_this_period ?? 0}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-muted-foreground">Pre-qualified</span>
                                    <span className="font-semibold text-foreground">
                                        {summary?.pre_qualified_rate ?? 0}%
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-muted-foreground">Spend</span>
                                    <span className="font-semibold text-foreground">
                                        ${spendTotals?.total_spend?.toLocaleString() ?? "0"}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <Card className="gap-0 rounded-[28px] border border-border/80 bg-card/95 shadow-sm">
                        <CardHeader className="gap-2 px-6 pb-0 pt-6">
                            <CardTitle className="text-xl font-semibold tracking-tight">Report Brief</CardTitle>
                        </CardHeader>
                        <CardContent className="px-6 pb-6 pt-5">
                            <div className="space-y-4">
                                <div className="border-b border-border/70 pb-4">
                                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                                        Trend Shift
                                    </p>
                                    <p className="mt-2 text-sm font-medium leading-6 text-foreground">{insightSummary.trend}</p>
                                </div>
                                <div className="border-b border-border/70 pb-4">
                                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                                        Bottlenecks
                                    </p>
                                    <p className="mt-2 text-sm font-medium leading-6 text-foreground">{insightSummary.bottleneck}</p>
                                </div>
                                <div className="text-sm leading-6 text-muted-foreground">
                                    {insightSummary.anomaly}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </section>

                <section className="space-y-4">
                    <div>
                        <h2 className="text-xl font-semibold tracking-tight text-foreground">
                            Portfolio trend and comparison views
                        </h2>
                    </div>

                    <ReportsChartsGrid
                        aiEnabled={user?.ai_enabled ?? false}
                        statusChartData={statusChartData}
                        trendChartData={trendChartData}
                        assigneeChartData={assigneeChartData}
                        topStatus={topStatus}
                        topPerformer={topPerformer}
                        totalSurrogatesInPeriod={totalSurrogatesInPeriod}
                        computeTrendPercentage={computeTrendPercentage}
                        metaPerf={metaPerf ?? null}
                        byStatusLoading={byStatusLoading}
                        byStatusError={byStatusError}
                        trendLoading={trendLoading}
                        trendError={trendError}
                        byAssigneeLoading={byAssigneeLoading}
                        byAssigneeError={byAssigneeError}
                        metaLoading={metaLoading}
                        metaError={metaError}
                    />
                </section>

                <section className="grid gap-6 lg:grid-cols-2">
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
                </section>

                <section className="space-y-4">
                    <div>
                        <h2 className="text-xl font-semibold tracking-tight text-foreground">
                            Meta spend and form quality
                        </h2>
                    </div>
                    <MetaSpendDashboard dateParams={dateParams} />
                </section>

                <section className="space-y-4">
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
                </section>
            </div>
        </div>
    )
}
