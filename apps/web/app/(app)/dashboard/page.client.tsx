"use client"

import { useMountEffect } from "@/lib/hooks/use-mount-effect"
import { useDashboardKpiMismatchWarning } from "@/lib/hooks/use-dashboard-kpi-mismatch-warning"
import dynamic from "next/dynamic"
import { useAuth } from "@/lib/auth-context"
import { useDashboardSocket } from "@/lib/hooks/use-dashboard-socket"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useSurrogatesTrend, useSurrogatesByStatus } from "@/lib/hooks/use-analytics"
import { useAttention, useUpcoming } from "@/lib/hooks/use-dashboard"
import { ATTENTION_STUCK_DAYS } from "@/lib/api/dashboard"
import { useTasks, taskKeys } from "@/lib/hooks/use-tasks"
import { useQueryClient } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/page-header"

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
// Dashboard Content (requires filter context)
// =============================================================================

function DashboardContent() {
    const { user } = useAuth()
    const queryClient = useQueryClient()
    const { getDateParams, filters } = useDashboardFilters()
    const dateParams = getDateParams()
    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
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
        days_stuck: ATTENTION_STUCK_DAYS,
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

    useMountEffect(() => {
        trackDashboardViewed()
    })

    // Fetch data for "last updated" calculation
    const statsQuery = useSurrogateStats(statsParams)
    const trendQuery = useSurrogatesTrend(trendParams)
    const statusQuery = useSurrogatesByStatus(statusParams)
    const attentionQuery = useAttention(attentionParams)
    const tasksQuery = useTasks(tasksParams)
    const upcomingQuery = useUpcoming(upcomingParams)

    const statusTotal = statusQuery.data?.reduce((sum, item) => sum + item.count, 0) ?? 0

    const kpiTotalForCheck =
        filters.dateRange !== "all"
            ? statusQuery.data ? statusTotal : (statsQuery.data?.total ?? 0)
            : statsQuery.data?.total ?? statusTotal

    // Calculate last updated timestamp
    const lastUpdatedTimestamps = [
        statsQuery.dataUpdatedAt,
        trendQuery.dataUpdatedAt,
        statusQuery.dataUpdatedAt,
        attentionQuery.dataUpdatedAt,
        tasksQuery.dataUpdatedAt,
        upcomingQuery.dataUpdatedAt,
    ].filter(Boolean)
    const lastUpdated = lastUpdatedTimestamps.length ? Math.max(...lastUpdatedTimestamps) : null

    // Check if any query is currently fetching
    const isRefreshing =
        statsQuery.isFetching ||
        trendQuery.isFetching ||
        statusQuery.isFetching ||
        attentionQuery.isFetching ||
        tasksQuery.isFetching ||
        upcomingQuery.isFetching

    useDashboardKpiMismatchWarning({
        dateParams,
        distributionTotal: statusTotal,
        enabled:
            process.env.NODE_ENV === "development" &&
            Boolean(statusQuery.data) &&
            statsQuery.data?.total !== undefined,
        filters,
        kpiTotal: kpiTotalForCheck,
    })

    // Refresh all dashboard data
    const handleRefresh = () => {
        void queryClient.invalidateQueries({ queryKey: ["surrogates", "stats"] })
        void queryClient.invalidateQueries({ queryKey: ["analytics"] })
        void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
        void queryClient.invalidateQueries({ queryKey: taskKeys.all })
    }

    return (
        <div className="flex flex-1 flex-col">
            <PageHeader
                title="Dashboard"
                actions={
                    <DashboardFilterBar
                        lastUpdated={lastUpdated}
                        onRefresh={handleRefresh}
                        isRefreshing={isRefreshing}
                    />
                }
            />

            {/* Grid items get min-w-0 so wide chart content cannot stretch the single column below lg. */}
            <div className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-12">
                <div className="min-w-0 space-y-6 lg:col-span-8">
                    <KPICardsSection
                        statsQuery={statsQuery}
                        tasksQuery={tasksQuery}
                        trendQuery={trendQuery}
                        statusQuery={statusQuery}
                    />

                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 [&>*]:min-w-0">
                        <TrendChart />
                        <StageChart />
                    </div>
                </div>

                <div className="min-w-0 space-y-6 lg:col-span-4">
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
