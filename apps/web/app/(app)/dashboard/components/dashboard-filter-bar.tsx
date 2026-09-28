"use client"

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { DateRangePicker } from "@/components/ui/date-range-picker"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { XIcon, RefreshCwIcon } from "lucide-react"
import { useDashboardFilters } from "../context/dashboard-filters"
import { useAssignees } from "@/lib/hooks/use-surrogates"
import { useAuth } from "@/lib/auth-context"
import { formatDistanceToNow } from "date-fns"
import { useMountEffect } from "@/lib/hooks/use-mount-effect"

interface DashboardFilterBarProps {
    lastUpdated?: number | null
    onRefresh?: () => void
    isRefreshing?: boolean
}

export function DashboardFilterBar({
    lastUpdated,
    onRefresh,
    isRefreshing,
}: DashboardFilterBarProps) {
    const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [refreshHold, setRefreshHold] = useState(false)
    const { user } = useAuth()
    const {
        filters,
        setDateRange,
        setCustomRange,
        setAssigneeId,
        resetFilters,
    } = useDashboardFilters()
    const { data: assignees } = useAssignees()
    const isAdmin = user?.role === "admin" || user?.role === "developer"
    const showReset = filters.dateRange !== "all" || (isAdmin && !!filters.assigneeId)
    // Non-admins are always scoped to their own records, so the select would only offer "Mine".
    const showAssigneeFilter = isAdmin
    // The current user is already listed as "Mine".
    const otherAssignees = (assignees ?? []).filter((assignee) => assignee.id !== user?.user_id)

    // The unmount cleanup intentionally clears the latest refresh hold timeout,
    // not the timeout value that existed when this effect was registered.
    // oxlint-disable-next-line react-doctor/exhaustive-deps
    useMountEffect(() => {
        return () => {
            if (refreshTimeoutRef.current) {
                clearTimeout(refreshTimeoutRef.current)
            }
        }
    })

    const showRefreshing = !!onRefresh && (isRefreshing || refreshHold)
    const lastUpdatedText = showRefreshing
        ? "Refreshing..."
        : lastUpdated
        ? `Updated ${formatDistanceToNow(lastUpdated, { addSuffix: true })}`
        : null

    const handleRefresh = () => {
        if (!onRefresh) return
        onRefresh()
        setRefreshHold(true)
        if (refreshTimeoutRef.current) {
            clearTimeout(refreshTimeoutRef.current)
        }
        refreshTimeoutRef.current = setTimeout(() => {
            setRefreshHold(false)
        }, 1000)
    }

    // Rendered inside the PageHeader actions row, which wraps below the title on narrow screens.
    // Both triggers share one height (h-9) and the outline surface so they read as one control group.
    return (
        <>
            <DateRangePicker
                preset={filters.dateRange}
                onPresetChange={setDateRange}
                customRange={filters.customRange}
                onCustomRangeChange={setCustomRange}
                ariaLabel="Filter by date range"
                className="h-9 flex-1 sm:flex-none"
            />

            {showAssigneeFilter && (
                <Select
                    name="dashboard_assignee_filter"
                    value={filters.assigneeId ?? "all"}
                    onValueChange={(value) => setAssigneeId(value && value !== "all" ? value : undefined)}
                >
                    <SelectTrigger
                        id="dashboard-assignee-filter"
                        aria-label="Filter by assignee"
                        className="min-w-36 flex-1 bg-background sm:w-[180px] sm:flex-none"
                    >
                        <SelectValue placeholder="All Assignees">
                            {(value: string | null) => {
                                if (!value || value === "all") return "All Assignees"
                                if (value === user?.user_id) return "Mine"
                                const assignee = assignees?.find((item) => item.id === value)
                                return assignee?.name ?? "Unknown assignee"
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Assignees</SelectItem>
                        {user?.user_id && <SelectItem value={user.user_id}>Mine</SelectItem>}
                        {otherAssignees.map((assignee) => (
                            <SelectItem key={assignee.id} value={assignee.id}>
                                {assignee.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            )}

            {showReset && (
                <Button
                    variant="ghost"
                    onClick={resetFilters}
                    className="text-muted-foreground hover:text-foreground"
                >
                    <XIcon aria-hidden="true" />
                    Reset
                </Button>
            )}

            {onRefresh && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleRefresh}
                    disabled={showRefreshing}
                    title={lastUpdatedText ?? undefined}
                    aria-label={showRefreshing ? "Refreshing dashboard" : "Refresh dashboard"}
                >
                    <RefreshCwIcon
                        className={showRefreshing ? "animate-spin motion-reduce:animate-none" : undefined}
                        aria-hidden="true"
                    />
                </Button>
            )}
        </>
    )
}
