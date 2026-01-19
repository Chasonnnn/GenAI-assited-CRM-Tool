"use client"

import { useMemo } from "react"
import { UsersIcon, UserPlusIcon, CheckSquareIcon } from "lucide-react"
import { KPICard } from "./kpi-card"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useTasks } from "@/lib/hooks/use-tasks"
import { useSurrogatesTrend, useSurrogatesByStatus } from "@/lib/hooks/use-analytics"
import { useDashboardFilters } from "../context/dashboard-filters"
import { useAuth } from "@/lib/auth-context"
import { formatLocalDate } from "@/lib/utils/date"

export function KPICardsSection() {
    const { filters, getDateParams } = useDashboardFilters()
    const { user } = useAuth()
    const dateParams = getDateParams()
    const ownerId = filters.assigneeId
    const taskOwnerId = filters.assigneeId ?? user?.user_id
    const statsParams = {
        ...(ownerId ? { owner_id: ownerId } : {}),
    }
    const tasksParams = {
        is_completed: false,
        per_page: 5,
        exclude_approvals: true,
        ...(taskOwnerId ? { owner_id: taskOwnerId } : {}),
    }
    const trendParams = {
        period: "day" as const,
        ...dateParams,
        ...(ownerId ? { owner_id: ownerId } : {}),
    }
    const statusParams = {
        ...dateParams,
        ...(ownerId ? { owner_id: ownerId } : {}),
    }

    // Fetch data
    const statsQuery = useSurrogateStats(statsParams)
    const tasksQuery = useTasks(tasksParams)
    const trendQuery = useSurrogatesTrend(trendParams)
    const statusQuery = useSurrogatesByStatus(statusParams)

    // Compute sparkline data from trend
    const sparklineData = useMemo(() => {
        if (!trendQuery.data?.length) return undefined
        // Take last 7 data points for mini sparkline
        return trendQuery.data.slice(-7).map((d) => d.count)
    }, [trendQuery.data])

    const statusTotal = useMemo(() => {
        if (!statusQuery.data?.length) return 0
        return statusQuery.data.reduce((sum, item) => sum + item.count, 0)
    }, [statusQuery.data])

    const activeTotal = useMemo(() => {
        if (filters.dateRange !== "all") {
            return statusQuery.data ? statusTotal : (statsQuery.data?.total ?? 0)
        }
        return statsQuery.data?.total ?? statusTotal
    }, [filters.dateRange, statusQuery.data, statusTotal, statsQuery.data?.total])

    // Build drilldown URL with current filter params
    const buildSurrogatesUrl = (additionalParams?: Record<string, string>) => {
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
        if (filters.assigneeId) {
            params.set("owner_id", filters.assigneeId)
        }
        if (additionalParams) {
            Object.entries(additionalParams).forEach(([key, value]) => {
                params.set(key, value)
            })
        }
        const query = params.toString()
        return `/surrogates${query ? `?${query}` : ""}`
    }

    const stats = statsQuery.data
    const tasks = tasksQuery.data

    // Count pending tasks
    const pendingTasksCount = tasks?.total ?? 0
    const tasksFilter = filters.assigneeId && filters.assigneeId !== user?.user_id ? "all" : "my_tasks"
    const showWeeklyChange = !!stats && !(stats.this_week === 0 && stats.last_week === 0)
    return (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 items-stretch">
            {/* Active Surrogates */}
            <KPICard
                title="Active Surrogates"
                icon={<UsersIcon className="size-3.5" />}
                value={activeTotal || 0}
                subtitle={`${stats?.this_week || 0} new this week`}
                change={
                    showWeeklyChange && stats?.week_change_pct !== null && stats?.week_change_pct !== undefined
                        ? {
                            currentValue: stats.this_week,
                            previousValue: stats.last_week,
                            percentChange: stats.week_change_pct,
                            period: "last week",
                        }
                        : undefined
                }
                sparklineData={sparklineData}
                href="/surrogates"
                isLoading={statsQuery.isLoading}
                isError={statsQuery.isError}
                onRetry={() => statsQuery.refetch()}
            />

            {/* New Leads */}
            <KPICard
                title="New Leads"
                icon={<UserPlusIcon className="size-3.5" />}
                value={stats?.this_month || 0}
                subtitle="This month"
                change={
                    stats?.month_change_pct !== null && stats?.month_change_pct !== undefined
                        ? {
                            currentValue: stats.this_month,
                            previousValue: stats.last_month,
                            percentChange: stats.month_change_pct,
                            period: "last month",
                        }
                        : undefined
                }
                sparklineData={sparklineData}
                href={buildSurrogatesUrl()}
                isLoading={statsQuery.isLoading}
                isError={statsQuery.isError}
                onRetry={() => statsQuery.refetch()}
            />

            {/* My Tasks */}
            <KPICard
                title={filters.assigneeId && filters.assigneeId !== user?.user_id ? "Tasks" : "My Tasks"}
                icon={<CheckSquareIcon className="size-3.5" />}
                value={pendingTasksCount}
                subtitle={
                    pendingTasksCount === 0
                        ? "All caught up!"
                        : "Tasks assigned to you"
                }
                href={filters.assigneeId
                    ? `/tasks?${new URLSearchParams({
                        filter: tasksFilter,
                        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
                    }).toString()}`
                    : "/tasks?filter=my_tasks"}
                isLoading={tasksQuery.isLoading}
                isError={tasksQuery.isError}
                onRetry={() => tasksQuery.refetch()}
            />
        </div>
    )
}
