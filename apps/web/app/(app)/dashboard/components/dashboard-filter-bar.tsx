"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { DateRangePicker } from "@/components/ui/date-range-picker"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { XIcon, RefreshCwIcon } from "lucide-react"
import { useDashboardFilters } from "../context/dashboard-filters"
import { useAssignees } from "@/lib/hooks/use-surrogates"
import { useAuth } from "@/lib/auth-context"
import { formatDistanceToNow } from "date-fns"

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

    useEffect(() => {
        if (!isAdmin && user?.user_id && !filters.assigneeId) {
            setAssigneeId(user.user_id)
        }
    }, [filters.assigneeId, isAdmin, setAssigneeId, user?.user_id])

    useEffect(() => {
        return () => {
            if (refreshTimeoutRef.current) {
                clearTimeout(refreshTimeoutRef.current)
            }
        }
    }, [])

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

    return (
        <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
                <DateRangePicker
                    preset={filters.dateRange}
                    onPresetChange={setDateRange}
                    customRange={filters.customRange}
                    onCustomRangeChange={setCustomRange}
                />

                <Select
                    value={filters.assigneeId ?? (isAdmin ? "all" : user?.user_id ?? "all")}
                    onValueChange={(value) => setAssigneeId(value && value !== "all" ? value : undefined)}
                    disabled={!isAdmin && !user?.user_id}
                >
                    <SelectTrigger className="w-full sm:w-[180px]" size="sm">
                    <SelectValue placeholder="All assignees">
                        {(value: string | null) => {
                                if (!value || value === "all") return isAdmin ? "All Assignees" : "Mine"
                            if (value === user?.user_id) return "Mine"
                            const assignee = assignees?.find((item) => item.id === value)
                            return assignee?.name ?? value
                        }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {isAdmin && <SelectItem value="all">All Assignees</SelectItem>}
                        {user?.user_id && <SelectItem value={user.user_id}>Mine</SelectItem>}
                        {isAdmin && assignees?.map((assignee) => (
                            <SelectItem key={assignee.id} value={assignee.id}>
                                {assignee.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                {showReset && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={resetFilters}
                        className="h-8 px-2 text-muted-foreground hover:text-foreground"
                    >
                        <XIcon className="mr-1 size-3.5" />
                        Reset
                    </Button>
                )}
            </div>

            <div className="flex items-center gap-3">
                {lastUpdatedText && (
                    <span className="text-xs text-muted-foreground">
                        {lastUpdatedText}
                    </span>
                )}
                {onRefresh && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleRefresh}
                        disabled={showRefreshing}
                        className="size-8"
                    >
                        <RefreshCwIcon className={`size-4 ${showRefreshing ? 'animate-spin' : ''}`} />
                    </Button>
                )}
            </div>
        </div>
    )
}
