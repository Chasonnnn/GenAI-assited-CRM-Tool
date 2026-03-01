"use client"

import { useMemo, useCallback, useEffect } from "react"
import dynamic from "next/dynamic"
import { useAuth } from "@/lib/auth-context"
import { useDashboardSocket } from "@/lib/hooks/use-dashboard-socket"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useSurrogatesTrend, useSurrogatesByStatus } from "@/lib/hooks/use-analytics"
import { useAttention, useUpcoming } from "@/lib/hooks/use-dashboard"
import { useTasks, taskKeys } from "@/lib/hooks/use-tasks"
import { useQueryClient } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"

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

// =============================================================================
// Dashboard Content (requires filter context)
// =============================================================================

function DashboardContent() {
    const { user } = useAuth()
    const queryClient = useQueryClient()
    const { getDateParams, filters } = useDashboardFilters()
    const dateParams = getDateParams()
    const statsParams = {
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const trendParams = {
        period: "day" as const,
        ...dateParams,
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
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Welcome Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">
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

            <div className="grid gap-6 lg:grid-cols-12">
                <div className="space-y-6 lg:col-span-8">
                    {/* KPI Cards */}
                    <KPICardsSection
                        statsQuery={statsQuery}
                        tasksQuery={tasksQuery}
                        trendQuery={trendQuery}
                        statusQuery={statusQuery}
                    />

                    {/* Charts Row */}
                    <div className="grid gap-6 lg:grid-cols-2">
                        <TrendChart />
                        <StageChart />
                    </div>
                </div>

                <div className="space-y-6 lg:col-span-4">
                    {/* Action Panels */}
                    <AttentionNeededPanel />
                </div>
            </div>
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
