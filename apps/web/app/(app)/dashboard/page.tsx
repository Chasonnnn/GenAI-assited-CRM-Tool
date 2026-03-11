"use client"

import { useMemo, useCallback, useEffect } from "react"
import dynamic from "next/dynamic"
import Link from "@/components/app-link"
import { useAuth } from "@/lib/auth-context"
import { useDashboardSocket } from "@/lib/hooks/use-dashboard-socket"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useSurrogatesTrend, useSurrogatesByStatus } from "@/lib/hooks/use-analytics"
import { useAttention, useUpcoming } from "@/lib/hooks/use-dashboard"
import { useTasks, taskKeys } from "@/lib/hooks/use-tasks"
import { useQueryClient } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { ArrowRightIcon } from "lucide-react"

import { DashboardFiltersProvider, useDashboardFilters } from "./context/dashboard-filters"
import { DashboardFilterBar } from "./components/dashboard-filter-bar"
import { KPICardsSection } from "./components/kpi-cards-section"
import { AttentionNeededPanel } from "./components/attention-needed-panel"
import { trackDashboardViewed } from "@/lib/workflow-metrics"

const TrendChart = dynamic(
    () => import("./components/trend-chart").then((mod) => mod.TrendChart),
    { ssr: false, loading: () => <Skeleton className="h-80 w-full rounded-lg" /> }
)

const StageChart = dynamic(
    () => import("./components/stage-chart").then((mod) => mod.StageChart),
    { ssr: false, loading: () => <Skeleton className="h-80 w-full rounded-lg" /> }
)

// =============================================================================
// Helpers
// =============================================================================

function getFirstName(displayName: string | undefined): string {
    if (!displayName) return "there"
    const [firstName] = displayName.split(" ")
    return firstName || displayName
}

function pluralize(value: number, singular: string, plural = `${singular}s`): string {
    return `${value.toLocaleString()} ${value === 1 ? singular : plural}`
}

// =============================================================================
// Dashboard Content (requires filter context)
// =============================================================================

function DashboardContent() {
    const { user } = useAuth()
    const queryClient = useQueryClient()
    const { getDateParams, filters } = useDashboardFilters()
    const dateParams = getDateParams()
    const browserTimezone = useMemo(
        () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        [],
    )
    const statsParams = {
        ...dateParams,
        timezone: browserTimezone,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const trendParams = {
        period: "day" as const,
        ...dateParams,
        timezone: browserTimezone,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const statusParams = {
        ...dateParams,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const attentionParams = {
        ...(filters.assigneeId ? { assignee_id: filters.assigneeId } : {}),
        days_unreached: 7,
        days_stuck: 30,
    }
    const tasksParams = {
        is_completed: false,
        per_page: 5,
        exclude_approvals: true,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : user?.user_id ? { owner_id: user.user_id } : {}),
    }
    const upcomingParams = {
        days: 7,
        include_overdue: true,
        ...(filters.assigneeId ? { assignee_id: filters.assigneeId } : {}),
    }

    // WebSocket for real-time updates
    useDashboardSocket()

    useEffect(() => {
        trackDashboardViewed()
    }, [])

    // Fetch data for "last updated" calculation
    const statsQuery = useSurrogateStats(statsParams)
    const trendQuery = useSurrogatesTrend(trendParams)
    const statusQuery = useSurrogatesByStatus(statusParams)
    const attentionQuery = useAttention(attentionParams)
    const tasksQuery = useTasks(tasksParams)
    const upcomingQuery = useUpcoming(upcomingParams)

    const statusTotal = useMemo(() => {
        if (!statusQuery.data?.length) return 0
        return statusQuery.data.reduce((sum, item) => sum + item.count, 0)
    }, [statusQuery.data])

    const kpiTotalForCheck = useMemo(() => {
        if (filters.dateRange !== "all") {
            return statusQuery.data ? statusTotal : (statsQuery.data?.total ?? 0)
        }
        return statsQuery.data?.total ?? statusTotal
    }, [filters.dateRange, statusQuery.data, statusTotal, statsQuery.data?.total])

    const attentionSnapshot = useMemo(() => {
        const attention = attentionQuery.data
        const unreachedCount = attention?.unreached_count ?? 0
        const overdueCount = attention?.overdue_count ?? 0
        const stuckCount = attention?.stuck_count ?? 0
        const totalCount = attention?.total_count ?? (unreachedCount + overdueCount + stuckCount)
        return {
            unreachedCount,
            overdueCount,
            stuckCount,
            totalCount,
        }
    }, [attentionQuery.data])

    const upcomingTotal = useMemo(() => {
        if (!upcomingQuery.data) return 0
        return upcomingQuery.data.tasks.length + upcomingQuery.data.meetings.length
    }, [upcomingQuery.data])

    const leadSummary = useMemo(() => {
        if (attentionSnapshot.totalCount > 0) {
            return `${pluralize(attentionSnapshot.totalCount, "case")} need follow-up across overdue tasks, unreached leads, or stalled stages.`
        }
        if ((statsQuery.data?.this_week ?? 0) > 0) {
            return `${pluralize(statsQuery.data?.this_week ?? 0, "new intake")} arrived this week and the queue is clear of urgent follow-up.`
        }
        return "The active portfolio is stable, with no urgent follow-up items open right now."
    }, [attentionSnapshot.totalCount, statsQuery.data?.this_week])

    const attentionHref = useMemo(() => {
        const params = new URLSearchParams({
            filter: filters.assigneeId && filters.assigneeId !== user?.user_id ? "all" : "my_tasks",
        })
        if (filters.assigneeId) {
            params.set("owner_id", filters.assigneeId)
        } else if (user?.user_id) {
            params.set("owner_id", user.user_id)
        }
        if (attentionSnapshot.overdueCount > 0) {
            params.set("focus", "overdue")
        }
        return `/tasks?${params.toString()}`
    }, [attentionSnapshot.overdueCount, filters.assigneeId, user?.user_id])

    // Calculate last updated timestamp
    const lastUpdated = useMemo(() => {
        const timestamps = [
            statsQuery.dataUpdatedAt,
            trendQuery.dataUpdatedAt,
            statusQuery.dataUpdatedAt,
            attentionQuery.dataUpdatedAt,
            tasksQuery.dataUpdatedAt,
            upcomingQuery.dataUpdatedAt,
        ].filter(Boolean)
        return timestamps.length ? Math.max(...timestamps) : null
    }, [
        statsQuery.dataUpdatedAt,
        trendQuery.dataUpdatedAt,
        statusQuery.dataUpdatedAt,
        attentionQuery.dataUpdatedAt,
        tasksQuery.dataUpdatedAt,
        upcomingQuery.dataUpdatedAt,
    ])

    // Check if any query is currently fetching
    const isRefreshing =
        statsQuery.isFetching ||
        trendQuery.isFetching ||
        statusQuery.isFetching ||
        attentionQuery.isFetching ||
        tasksQuery.isFetching ||
        upcomingQuery.isFetching

    useEffect(() => {
        if (process.env.NODE_ENV !== "development") return
        if (!statusQuery.data || statsQuery.data?.total === undefined) return
        const delta = Math.abs(kpiTotalForCheck - statusTotal)
        const ratio = delta / Math.max(kpiTotalForCheck || 1, 1)
        if (delta >= 5 && ratio >= 0.2) {
            console.warn("[dashboard] KPI vs distribution mismatch", {
                kpiTotal: kpiTotalForCheck,
                distributionTotal: statusTotal,
                filters,
                dateParams,
            })
        }
    }, [
        dateParams,
        filters,
        kpiTotalForCheck,
        statsQuery.data?.total,
        statusQuery.data,
        statusTotal,
    ])

    // Refresh all dashboard data
    const handleRefresh = useCallback(() => {
        queryClient.invalidateQueries({ queryKey: ["surrogates", "stats"] })
        queryClient.invalidateQueries({ queryKey: ["analytics"] })
        queryClient.invalidateQueries({ queryKey: ["dashboard"] })
        queryClient.invalidateQueries({ queryKey: taskKeys.all })
    }, [queryClient])

    // Current date for header
    const currentDate = new Date().toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
    })

    return (
        <div className="flex flex-1 flex-col gap-8 p-5 sm:p-6 xl:p-8">
            {/* Welcome Header */}
            <div className="flex items-end justify-between gap-4">
                <div className="space-y-2">
                    <h1 className="font-display text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
                        Welcome back, {getFirstName(user?.display_name)}
                    </h1>
                    <p className="text-sm text-muted-foreground">{currentDate}</p>
                </div>
            </div>

            {/* Filter Bar */}
            <DashboardFilterBar
                lastUpdated={lastUpdated}
                onRefresh={handleRefresh}
                isRefreshing={isRefreshing}
            />

            <section className="overflow-hidden rounded-[28px] border border-border/80 bg-card/95 shadow-sm">
                <div className="flex flex-col gap-6 p-6 sm:p-8">
                    <div className="space-y-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                            Portfolio health
                        </p>
                        <div className="flex flex-wrap items-end gap-4">
                            <div className="font-display text-6xl font-semibold leading-none tracking-tight text-foreground sm:text-7xl">
                                {kpiTotalForCheck.toLocaleString()}
                            </div>
                            <div className="max-w-xl space-y-2 pb-1">
                                <p className="text-lg font-medium text-foreground">
                                    Active surrogates in motion.
                                </p>
                                <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                                    {leadSummary}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-y border-border/70 py-4 text-sm">
                        <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">New this week</span>
                            <span className="font-semibold text-foreground">
                                {(statsQuery.data?.this_week ?? 0).toLocaleString()}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">Needs review</span>
                            <span className="font-semibold text-foreground">
                                {attentionSnapshot.totalCount.toLocaleString()}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">Due this week</span>
                            <span className="font-semibold text-foreground">
                                {upcomingTotal.toLocaleString()}
                            </span>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <Button render={<Link href={attentionHref} />}>
                            Review attention queue
                            <ArrowRightIcon className="size-4" />
                        </Button>
                    </div>
                </div>
            </section>

            <section className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
                <div className="space-y-6">
                    <KPICardsSection
                        statsQuery={statsQuery}
                        tasksQuery={tasksQuery}
                        statusQuery={statusQuery}
                    />

                    <div className="space-y-4">
                        <div>
                            <h2 className="text-xl font-semibold tracking-tight text-foreground">
                                Trends and stage distribution
                            </h2>
                        </div>
                        <div className="grid gap-6 xl:grid-cols-2">
                            <TrendChart />
                            <StageChart />
                        </div>
                    </div>
                </div>

                <AttentionNeededPanel />
            </section>
        </div>
    )
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function DashboardPage() {
    return (
        <DashboardFiltersProvider>
            <DashboardContent />
        </DashboardFiltersProvider>
    )
}
