"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    TrendingUpIcon,
    TrendingDownIcon,
    DollarSignIcon,
    MousePointerClickIcon,
    EyeIcon,
    UsersIcon,
    Loader2Icon,
    AlertCircleIcon,
    RefreshCwIcon,
    LayoutGridIcon,
    BarChart3Icon,
    FileTextIcon,
    ClockIcon,
} from "lucide-react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Area, AreaChart, Cell } from "recharts"
import {
    ChartContainer,
    ChartTooltip,
} from "@/components/ui/chart"
import {
    useMetaAdAccounts,
    useSpendTotals,
    useSpendByCampaign,
    useSpendByBreakdown,
    useSpendTrend,
    useFormPerformance,
    useMetaPlatformBreakdown,
    useMetaAdPerformance,
} from "@/lib/hooks/use-analytics"
import type { DateRangeParams, BreakdownParams } from "@/lib/api/analytics"
import { cn } from "@/lib/utils"

interface MetaSpendDashboardProps {
    dateParams: DateRangeParams
}

// Refined color palette with depth
const CHART_COLORS = {
    primary: "#0d9488",      // Teal-600
    secondary: "#14b8a6",    // Teal-500
    tertiary: "#5eead4",     // Teal-300
    accent: "#f59e0b",       // Amber-500
    muted: "#94a3b8",        // Slate-400
    success: "#22c55e",      // Green-500
    gradient: {
        from: "#0d9488",
        to: "#06b6d4",
    }
}

const BREAKDOWN_COLORS = [
    "#0d9488", "#0891b2", "#6366f1", "#8b5cf6", "#d946ef",
    "#ec4899", "#f43f5e", "#f97316", "#eab308", "#84cc16"
]

// Format helpers
const formatCurrency = (value: number | null) => {
    if (value === null || value === undefined) return "—"
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value)
}

const formatNumber = (value: number | null) => {
    if (value === null || value === undefined) return "—"
    return new Intl.NumberFormat("en-US").format(value)
}

const formatCompact = (value: number | null) => {
    if (value === null || value === undefined) return "—"
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
    return value.toString()
}

const formatPercent = (value: number | null) => {
    if (value === null || value === undefined) return "—"
    return `${value.toFixed(1)}%`
}

// Sync status indicator
function SyncStatusBadge({ status, lastSynced }: { status: string; lastSynced: string | null }) {
    const statusConfig = {
        synced: { label: "Synced", variant: "default" as const, icon: RefreshCwIcon },
        pending: { label: "Pending", variant: "secondary" as const, icon: ClockIcon },
        never: { label: "Not synced", variant: "outline" as const, icon: AlertCircleIcon },
    }

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.never
    const Icon = config.icon

    const timeAgo = lastSynced ? formatTimeAgo(new Date(lastSynced)) : null

    return (
        <div className="flex items-center gap-2">
            <Badge variant={config.variant} className="gap-1 text-xs font-normal">
                <Icon className="size-3" />
                {config.label}
            </Badge>
            {timeAgo && (
                <span className="text-xs text-muted-foreground">{timeAgo}</span>
            )}
        </div>
    )
}

function formatTimeAgo(date: Date): string {
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffHours / 24)

    if (diffHours < 1) return "just now"
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
}

// Metric card component
function MetricCard({
    title,
    value,
    subValue,
    icon: Icon,
    trend,
    className,
    loading,
    error,
}: {
    title: string
    value: string
    subValue?: string
    icon: React.ElementType
    trend?: number | null
    className?: string
    loading?: boolean
    error?: boolean
}) {
    return (
        <div className={cn(
            "relative overflow-hidden rounded-xl border border-border/50 bg-gradient-to-br from-background to-muted/30 p-4 transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 hover:border-primary/20",
            className
        )}>
            {/* Subtle gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent pointer-events-none" />

            <div className="relative">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        {title}
                    </span>
                    <div className="p-1.5 rounded-lg bg-primary/10">
                        <Icon className="size-3.5 text-primary" />
                    </div>
                </div>

                {loading ? (
                    <Loader2Icon className="size-5 animate-spin text-muted-foreground mt-2" />
                ) : error ? (
                    <div className="flex items-center gap-1 text-xs text-destructive mt-2">
                        <AlertCircleIcon className="size-3.5" />
                        Unable to load
                    </div>
                ) : (
                    <>
                        <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold tracking-tight">{value}</span>
                            {trend !== null && trend !== undefined && (
                                <span className={cn(
                                    "flex items-center text-xs font-medium",
                                    trend >= 0 ? "text-emerald-600" : "text-rose-600"
                                )}>
                                    {trend >= 0 ? <TrendingUpIcon className="size-3 mr-0.5" /> : <TrendingDownIcon className="size-3 mr-0.5" />}
                                    {Math.abs(trend)}%
                                </span>
                            )}
                        </div>
                        {subValue && (
                            <p className="text-xs text-muted-foreground mt-0.5">{subValue}</p>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

// Campaign table component
function CampaignSpendTable({
    data,
    loading,
    error
}: {
    data: Array<{
        campaign_external_id: string
        campaign_name: string
        spend: number
        impressions: number
        clicks: number
        leads: number
        cost_per_lead: number | null
    }> | undefined
    loading: boolean
    error: boolean
}) {
    if (loading) {
        return (
            <div className="flex items-center justify-center h-48">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-48 text-destructive">
                <AlertCircleIcon className="size-4 mr-2" />
                Unable to load campaign data
            </div>
        )
    }

    if (!data || data.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <LayoutGridIcon className="size-8 mb-2 opacity-50" />
                <p className="text-sm">No campaign data available</p>
                <p className="text-xs mt-1">Configure ad account sync in Settings</p>
            </div>
        )
    }

    const totalSpend = data.reduce((sum, c) => sum + c.spend, 0)

    return (
        <div className="overflow-hidden rounded-lg border border-border/50">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-border/50 bg-muted/30">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Campaign</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Spend</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden sm:table-cell">Impr.</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden md:table-cell">Clicks</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Leads</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">CPL</th>
                    </tr>
                </thead>
                <tbody>
                    {data.map((campaign, idx) => {
                        const spendPct = totalSpend > 0 ? (campaign.spend / totalSpend) * 100 : 0
                        return (
                            <tr
                                key={campaign.campaign_external_id}
                                className={cn(
                                    "border-b border-border/30 transition-colors hover:bg-muted/20",
                                    idx === data.length - 1 && "border-b-0"
                                )}
                            >
                                <td className="px-4 py-3">
                                    <div className="flex items-center gap-3">
                                        <div
                                            className="w-1 h-8 rounded-full"
                                            style={{ backgroundColor: BREAKDOWN_COLORS[idx % BREAKDOWN_COLORS.length] }}
                                        />
                                        <div className="min-w-0">
                                            <p className="font-medium truncate max-w-[200px]">{campaign.campaign_name}</p>
                                            <p className="text-xs text-muted-foreground">{spendPct.toFixed(1)}% of total</p>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-4 py-3 text-right font-mono font-medium">
                                    {formatCurrency(campaign.spend)}
                                </td>
                                <td className="px-4 py-3 text-right text-muted-foreground hidden sm:table-cell">
                                    {formatCompact(campaign.impressions)}
                                </td>
                                <td className="px-4 py-3 text-right text-muted-foreground hidden md:table-cell">
                                    {formatCompact(campaign.clicks)}
                                </td>
                                <td className="px-4 py-3 text-right font-medium">
                                    {formatNumber(campaign.leads)}
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <span className={cn(
                                        "font-mono text-sm",
                                        campaign.cost_per_lead && campaign.cost_per_lead < 50
                                            ? "text-emerald-600"
                                            : campaign.cost_per_lead && campaign.cost_per_lead > 100
                                                ? "text-amber-600"
                                                : ""
                                    )}>
                                        {campaign.cost_per_lead ? formatCurrency(campaign.cost_per_lead) : "—"}
                                    </span>
                                </td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

// Breakdown chart component
function BreakdownChart({
    data,
    loading,
    error,
}: {
    data: Array<{ breakdown_value: string; spend: number; leads: number; cost_per_lead: number | null }> | undefined
    loading: boolean
    error: boolean
}) {
    if (loading) {
        return (
            <div className="flex items-center justify-center h-[200px]">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-[200px] text-destructive text-sm">
                <AlertCircleIcon className="size-4 mr-2" />
                Unable to load
            </div>
        )
    }

    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-[200px] text-muted-foreground text-sm">
                No data available
            </div>
        )
    }

    const chartData = data.slice(0, 6).map((item, idx) => ({
        name: item.breakdown_value.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
        spend: item.spend,
        leads: item.leads,
        fill: BREAKDOWN_COLORS[idx % BREAKDOWN_COLORS.length],
    }))

    return (
        <ChartContainer config={{ spend: { label: "Spend" } }} className="h-[200px] w-full">
            <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" opacity={0.5} />
                <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `$${formatCompact(v)}`} />
                <YAxis dataKey="name" type="category" tickLine={false} axisLine={false} width={80} fontSize={11} />
                <ChartTooltip
                    content={({ payload }) => {
                        if (!payload?.length) return null
                        const d = payload[0].payload
                        return (
                            <div className="rounded-lg border bg-background/95 backdrop-blur p-2 shadow-lg text-xs">
                                <p className="font-medium">{d.name}</p>
                                <p className="text-muted-foreground">Spend: {formatCurrency(d.spend)}</p>
                                <p className="text-muted-foreground">Leads: {d.leads}</p>
                            </div>
                        )
                    }}
                />
                <Bar dataKey="spend" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, index) => (
                        <Cell key={index} fill={entry.fill ?? "hsl(var(--primary))"} />
                    ))}
                </Bar>
            </BarChart>
        </ChartContainer>
    )
}

// Form performance table component
function FormPerformanceTable({
    data,
    loading,
    error,
}: {
    data: Array<{
        form_external_id: string
        form_name: string
        mapping_status: string
        lead_count: number
        surrogate_count: number
        qualified_count: number
        conversion_rate: number
        qualified_rate: number
    }> | undefined
    loading: boolean
    error: boolean
}) {
    if (loading) {
        return (
            <div className="flex items-center justify-center h-48">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-48 text-destructive">
                <AlertCircleIcon className="size-4 mr-2" />
                Unable to load form data
            </div>
        )
    }

    if (!data || data.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <FileTextIcon className="size-8 mb-2 opacity-50" />
                <p className="text-sm">No form data available</p>
                <p className="text-xs mt-1">Forms sync when leads are received</p>
            </div>
        )
    }

    return (
        <div className="overflow-hidden rounded-lg border border-border/50">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-border/50 bg-muted/30">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Form</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Mapping</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Leads</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Surrogates</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden sm:table-cell">Qualified</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Conv. %</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden md:table-cell">Qual. %</th>
                    </tr>
                </thead>
                <tbody>
                    {data.map((form, idx) => (
                        <tr
                            key={form.form_external_id}
                            className={cn(
                                "border-b border-border/30 transition-colors hover:bg-muted/20",
                                idx === data.length - 1 && "border-b-0"
                            )}
                        >
                            <td className="px-4 py-3">
                                <p className="font-medium truncate max-w-[200px]">{form.form_name}</p>
                            </td>
                            <td className="px-4 py-3">
                                <Badge
                                    variant={
                                        form.mapping_status === "mapped"
                                            ? "default"
                                            : form.mapping_status === "outdated"
                                              ? "destructive"
                                              : "secondary"
                                    }
                                    className="text-xs"
                                >
                                    {form.mapping_status.replace(/_/g, " ")}
                                </Badge>
                            </td>
                            <td className="px-4 py-3 text-right font-medium">
                                {formatNumber(form.lead_count)}
                            </td>
                            <td className="px-4 py-3 text-right">
                                {formatNumber(form.surrogate_count)}
                            </td>
                            <td className="px-4 py-3 text-right text-emerald-600 hidden sm:table-cell">
                                {formatNumber(form.qualified_count)}
                            </td>
                            <td className="px-4 py-3 text-right">
                                <span className={cn(
                                    "font-medium",
                                    form.conversion_rate >= 80 ? "text-emerald-600" : form.conversion_rate < 50 ? "text-amber-600" : ""
                                )}>
                                    {formatPercent(form.conversion_rate)}
                                </span>
                            </td>
                            <td className="px-4 py-3 text-right hidden md:table-cell">
                                <span className={cn(
                                    "font-medium",
                                    form.qualified_rate >= 30 ? "text-emerald-600" : form.qualified_rate < 10 ? "text-amber-600" : ""
                                )}>
                                    {formatPercent(form.qualified_rate)}
                                </span>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

export function MetaSpendDashboard({ dateParams }: MetaSpendDashboardProps) {
    const [selectedAdAccount, setSelectedAdAccount] = useState<string>("")
    const [breakdownTab, setBreakdownTab] = useState<BreakdownParams["breakdown_type"]>("publisher_platform")

    // Build params with ad account filter
    const spendParams = useMemo(() => ({
        ...dateParams,
        ...(selectedAdAccount ? { ad_account_id: selectedAdAccount } : {}),
    }), [dateParams, selectedAdAccount])

    // Fetch data
    const { data: adAccounts, isLoading: adAccountsLoading } = useMetaAdAccounts()
    const { data: totals, isLoading: totalsLoading, isError: totalsError } = useSpendTotals(spendParams)
    const { data: campaigns, isLoading: campaignsLoading, isError: campaignsError } = useSpendByCampaign(spendParams)
    const { data: breakdown, isLoading: breakdownLoading, isError: breakdownError } = useSpendByBreakdown({
        ...spendParams,
        breakdown_type: breakdownTab,
    })
    const { data: trend, isLoading: trendLoading, isError: trendError } = useSpendTrend(spendParams)
    const { data: forms, isLoading: formsLoading, isError: formsError } = useFormPerformance(dateParams)
    const { data: platforms, isLoading: platformsLoading, isError: platformsError } = useMetaPlatformBreakdown(dateParams)
    const { data: ads, isLoading: adsLoading, isError: adsError } = useMetaAdPerformance(dateParams)

    // Transform trend data for chart
    const trendChartData = useMemo(() => {
        if (!trend) return []
        return trend.map(point => ({
            date: new Date(point.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
            spend: point.spend,
            leads: point.leads,
        }))
    }, [trend])

    const platformChartData = useMemo(() => {
        if (!platforms) return []
        return platforms.map((item, idx) => ({
            platform: item.platform.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
            leads: item.lead_count,
            fill: BREAKDOWN_COLORS[idx % BREAKDOWN_COLORS.length],
        }))
    }, [platforms])

    const adChartData = useMemo(() => {
        if (!ads) return []
        return ads.slice(0, 8).map((item, idx) => ({
            ad: item.ad_name,
            leads: item.lead_count,
            surrogates: item.surrogate_count,
            fill: BREAKDOWN_COLORS[idx % BREAKDOWN_COLORS.length],
        }))
    }, [ads])

    return (
        <div className="space-y-6">
            {/* Header with filters */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5">
                        <DollarSignIcon className="size-5 text-primary" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold">Meta Ads Spend</h2>
                        <p className="text-xs text-muted-foreground">Campaign performance from stored sync data</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {totals && <SyncStatusBadge status={totals.sync_status} lastSynced={totals.last_synced_at} />}
                    <Select value={selectedAdAccount} onValueChange={(v) => setSelectedAdAccount(v ?? "")}>
                        <SelectTrigger className="w-48">
                            <SelectValue placeholder="All Ad Accounts" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="">All Ad Accounts</SelectItem>
                            {adAccountsLoading && (
                                <SelectItem value="__loading__" disabled>Loading...</SelectItem>
                            )}
                            {adAccounts?.map(acc => (
                                <SelectItem key={acc.id} value={acc.id}>
                                    {acc.ad_account_name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* No data state */}
            {totals?.sync_status === "never" && (
                <Card className="border-dashed">
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <div className="p-3 rounded-full bg-muted mb-4">
                            <RefreshCwIcon className="size-6 text-muted-foreground" />
                        </div>
                        <h3 className="font-semibold mb-1">No Spend Data Yet</h3>
                        <p className="text-sm text-muted-foreground text-center max-w-sm">
                            Configure your Meta ad account in Settings and trigger a sync to see spend analytics.
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Main metrics */}
            {totals?.sync_status !== "never" && (
                <>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <MetricCard
                            title="Total Spend"
                            value={formatCurrency(totals?.total_spend ?? 0)}
                            subValue={`${totals?.ad_accounts_configured ?? 0} ad account${(totals?.ad_accounts_configured ?? 0) !== 1 ? "s" : ""}`}
                            icon={DollarSignIcon}
                            loading={totalsLoading}
                            error={totalsError}
                        />
                        <MetricCard
                            title="Impressions"
                            value={formatCompact(totals?.total_impressions ?? 0)}
                            icon={EyeIcon}
                            loading={totalsLoading}
                            error={totalsError}
                        />
                        <MetricCard
                            title="Clicks"
                            value={formatCompact(totals?.total_clicks ?? 0)}
                            icon={MousePointerClickIcon}
                            loading={totalsLoading}
                            error={totalsError}
                        />
                        <MetricCard
                            title="Cost per Lead"
                            value={totals?.cost_per_lead ? formatCurrency(totals.cost_per_lead) : "—"}
                            subValue={`${formatNumber(totals?.total_leads ?? 0)} leads`}
                            icon={UsersIcon}
                            loading={totalsLoading}
                            error={totalsError}
                        />
                    </div>

                    {/* Spend trend chart */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                                <BarChart3Icon className="size-4 text-muted-foreground" />
                                Spend Trend
                            </CardTitle>
                            <CardDescription>Daily spend over time</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {trendLoading ? (
                                <div className="flex items-center justify-center h-[250px]">
                                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : trendError ? (
                                <div className="flex items-center justify-center h-[250px] text-destructive">
                                    <AlertCircleIcon className="size-4 mr-2" />
                                    Unable to load trend data
                                </div>
                            ) : trendChartData.length === 0 ? (
                                <div className="flex items-center justify-center h-[250px] text-muted-foreground">
                                    No trend data available
                                </div>
                            ) : (
                                <ChartContainer config={{ spend: { label: "Spend", color: CHART_COLORS.primary } }} className="h-[250px] w-full">
                                    <AreaChart data={trendChartData} margin={{ left: 0, right: 0 }}>
                                        <defs>
                                            <linearGradient id="spendGradient" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.3} />
                                                <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" opacity={0.5} />
                                        <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={11} />
                                        <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `$${formatCompact(v)}`} />
                                        <ChartTooltip
                                            content={({ payload }) => {
                                                if (!payload?.length) return null
                                                const d = payload[0].payload
                                                return (
                                                    <div className="rounded-lg border bg-background/95 backdrop-blur p-2 shadow-lg text-xs">
                                                        <p className="font-medium">{d.date}</p>
                                                        <p className="text-muted-foreground">Spend: {formatCurrency(d.spend)}</p>
                                                        <p className="text-muted-foreground">Leads: {d.leads}</p>
                                                    </div>
                                                )
                                            }}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="spend"
                                            stroke={CHART_COLORS.primary}
                                            strokeWidth={2}
                                            fill="url(#spendGradient)"
                                        />
                                    </AreaChart>
                                </ChartContainer>
                            )}
                        </CardContent>
                    </Card>

                    {/* Campaign spend table */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                                <LayoutGridIcon className="size-4 text-muted-foreground" />
                                Campaign Performance
                            </CardTitle>
                            <CardDescription>Spend breakdown by campaign</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <CampaignSpendTable data={campaigns} loading={campaignsLoading} error={campaignsError} />
                        </CardContent>
                    </Card>

                    {/* Breakdown tabs */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Spend Breakdown</CardTitle>
                            <CardDescription>Analyze spend by different dimensions</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Tabs value={breakdownTab} onValueChange={(v) => setBreakdownTab(v as BreakdownParams["breakdown_type"])}>
                                <TabsList className="mb-4">
                                    <TabsTrigger value="publisher_platform">Platform</TabsTrigger>
                                    <TabsTrigger value="platform_position">Position</TabsTrigger>
                                    <TabsTrigger value="age">Age</TabsTrigger>
                                    <TabsTrigger value="region">Region</TabsTrigger>
                                </TabsList>
                                <TabsContent value={breakdownTab} className="mt-0">
                                    <BreakdownChart
                                        data={breakdown}
                                        loading={breakdownLoading}
                                        error={breakdownError}
                                    />
                                </TabsContent>
                            </Tabs>
                        </CardContent>
                    </Card>

                    {/* Form performance */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                                <FileTextIcon className="size-4 text-muted-foreground" />
                                Form Performance
                            </CardTitle>
                            <CardDescription>Lead conversion by form</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <FormPerformanceTable data={forms} loading={formsLoading} error={formsError} />
                        </CardContent>
                    </Card>

                    {/* Platform + Ad Performance */}
                    <div className="grid gap-4 md:grid-cols-2">
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <LayoutGridIcon className="size-4 text-muted-foreground" />
                                    Meta Platforms
                                </CardTitle>
                                <CardDescription>Lead distribution by platform</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {platformsLoading ? (
                                    <div className="flex items-center justify-center h-[220px]">
                                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                    </div>
                                ) : platformsError ? (
                                    <div className="flex items-center justify-center h-[220px] text-destructive">
                                        <AlertCircleIcon className="size-4 mr-2" />
                                        Unable to load platform data
                                    </div>
                                ) : platformChartData.length > 0 ? (
                                    <ChartContainer config={{ leads: { label: "Leads" } }} className="h-[220px] w-full">
                                        <BarChart data={platformChartData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" opacity={0.5} />
                                            <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} />
                                            <YAxis dataKey="platform" type="category" tickLine={false} axisLine={false} width={110} fontSize={11} />
                                            <ChartTooltip
                                                content={({ payload }) => {
                                                    if (!payload?.length) return null
                                                    const d = payload[0].payload
                                                    return (
                                                        <div className="rounded-lg border bg-background/95 backdrop-blur p-2 shadow-lg text-xs">
                                                            <p className="font-medium">{d.platform}</p>
                                                            <p className="text-muted-foreground">Leads: {formatNumber(d.leads)}</p>
                                                        </div>
                                                    )
                                                }}
                                            />
                                            <Bar dataKey="leads" radius={[0, 4, 4, 0]}>
                                                {platformChartData.map((entry, index) => (
                                                    <Cell key={index} fill={entry.fill ?? "hsl(var(--primary))"} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ChartContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-[220px] text-muted-foreground text-sm">
                                        No platform data yet
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <BarChart3Icon className="size-4 text-muted-foreground" />
                                    Ads Performance
                                </CardTitle>
                                <CardDescription>Top ads by lead volume</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {adsLoading ? (
                                    <div className="flex items-center justify-center h-[220px]">
                                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                    </div>
                                ) : adsError ? (
                                    <div className="flex items-center justify-center h-[220px] text-destructive">
                                        <AlertCircleIcon className="size-4 mr-2" />
                                        Unable to load ad performance
                                    </div>
                                ) : adChartData.length > 0 ? (
                                    <ChartContainer
                                        config={{
                                            leads: { label: "Leads", color: CHART_COLORS.primary },
                                            surrogates: { label: "Surrogates", color: CHART_COLORS.accent },
                                        }}
                                        className="h-[220px] w-full"
                                    >
                                        <BarChart data={adChartData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" opacity={0.5} />
                                            <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} />
                                            <YAxis dataKey="ad" type="category" tickLine={false} axisLine={false} width={140} fontSize={11} />
                                            <ChartTooltip
                                                content={({ payload }) => {
                                                    if (!payload?.length) return null
                                                    const d = payload[0].payload
                                                    return (
                                                        <div className="rounded-lg border bg-background/95 backdrop-blur p-2 shadow-lg text-xs">
                                                            <p className="font-medium truncate max-w-[220px]">{d.ad}</p>
                                                            <p className="text-muted-foreground">Leads: {formatNumber(d.leads)}</p>
                                                            <p className="text-muted-foreground">Surrogates: {formatNumber(d.surrogates)}</p>
                                                        </div>
                                                    )
                                                }}
                                            />
                                            <Bar dataKey="leads" fill={CHART_COLORS.primary} radius={[0, 4, 4, 0]} />
                                            <Bar dataKey="surrogates" fill={CHART_COLORS.accent} radius={[0, 4, 4, 0]} />
                                        </BarChart>
                                    </ChartContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-[220px] text-muted-foreground text-sm">
                                        No ad performance data yet
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </>
            )}
        </div>
    )
}
