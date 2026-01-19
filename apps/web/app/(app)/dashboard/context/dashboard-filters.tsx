"use client"

import { createContext, useContext, useCallback, useState, useEffect, type ReactNode } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import type { DateRangePreset } from "@/components/ui/date-range-picker"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

// =============================================================================
// Types
// =============================================================================

interface DateRange {
    from: Date | undefined
    to: Date | undefined
}

interface DashboardFilters {
    dateRange: DateRangePreset
    customRange: DateRange
    assigneeId?: string | undefined
}

interface DashboardFiltersContextValue {
    filters: DashboardFilters
    setDateRange: (preset: DateRangePreset) => void
    setCustomRange: (range: DateRange) => void
    setAssigneeId: (id: string | undefined) => void
    resetFilters: () => void
    hasActiveFilters: boolean
    // Computed date params for API calls
    getDateParams: () => { from_date?: string; to_date?: string }
}

// =============================================================================
// Constants
// =============================================================================

const VALID_DATE_RANGES: DateRangePreset[] = ["all", "today", "week", "month", "custom"]
const isDateRangePreset = (value: string | null): value is DateRangePreset =>
    value !== null && VALID_DATE_RANGES.includes(value as DateRangePreset)
const ALL_TIME_START = new Date(2000, 0, 1)

const parseDateParam = (value: string | null): Date | undefined => {
    if (!value) return undefined
    const parsed = parseDateInput(value)
    return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

const normalizeFilterValue = (value: string | null): string | undefined => {
    if (!value || value === "all") return undefined
    return value
}

const datesEqual = (left?: Date, right?: Date) => {
    return (left?.getTime() ?? null) === (right?.getTime() ?? null)
}

// =============================================================================
// Context
// =============================================================================

const DashboardFiltersContext = createContext<DashboardFiltersContextValue | null>(null)

export function useDashboardFilters() {
    const context = useContext(DashboardFiltersContext)
    if (!context) {
        throw new Error("useDashboardFilters must be used within a DashboardFiltersProvider")
    }
    return context
}

// =============================================================================
// Provider
// =============================================================================

interface DashboardFiltersProviderProps {
    children: ReactNode
}

export function DashboardFiltersProvider({ children }: DashboardFiltersProviderProps) {
    const searchParams = useSearchParams()
    const router = useRouter()
    const currentQuery = searchParams.toString()

    // Read initial values from URL params
    const urlRange = searchParams.get("range")
    const urlFrom = searchParams.get("from")
    const urlTo = searchParams.get("to")
    const urlAssignee = searchParams.get("assignee")

    const initialRange = isDateRangePreset(urlRange) ? urlRange : "all"
    const initialCustomRange = initialRange === "custom"
        ? { from: parseDateParam(urlFrom), to: parseDateParam(urlTo) }
        : { from: undefined, to: undefined }

    const [dateRange, setDateRangeState] = useState<DateRangePreset>(initialRange)
    const [customRange, setCustomRangeState] = useState<DateRange>(initialCustomRange)
    const [assigneeId, setAssigneeIdState] = useState<string | undefined>(normalizeFilterValue(urlAssignee))

    // Sync state changes back to URL
    const updateUrlParams = useCallback((
        range: DateRangePreset,
        rangeDates: DateRange,
        assignee?: string
    ) => {
        const newParams = new URLSearchParams()

        if (range !== "all") {
            newParams.set("range", range)
        }
        if (range === "custom" && rangeDates.from) {
            newParams.set("from", formatLocalDate(rangeDates.from))
            if (rangeDates.to) {
                newParams.set("to", formatLocalDate(rangeDates.to))
            }
        }
        if (assignee) {
            newParams.set("assignee", assignee)
        }

        const queryStr = newParams.toString()
        router.replace(queryStr ? `?${queryStr}` : "/dashboard", { scroll: false })
    }, [router])

    // Set date range
    const setDateRange = useCallback((preset: DateRangePreset) => {
        setDateRangeState(preset)
        if (preset !== "custom") {
            setCustomRangeState({ from: undefined, to: undefined })
        }
        updateUrlParams(
            preset,
            preset === "custom" ? customRange : { from: undefined, to: undefined },
            assigneeId
        )
    }, [customRange, assigneeId, updateUrlParams])

    // Set custom date range
    const setCustomRange = useCallback((range: DateRange) => {
        setCustomRangeState(range)
        if (dateRange !== "custom") {
            setDateRangeState("custom")
        }
        updateUrlParams("custom", range, assigneeId)
    }, [dateRange, assigneeId, updateUrlParams])

    // Set assignee filter
    const setAssigneeId = useCallback((id: string | undefined) => {
        setAssigneeIdState(id)
        updateUrlParams(dateRange, customRange, id)
    }, [dateRange, customRange, updateUrlParams])

    // Reset all filters
    const resetFilters = useCallback(() => {
        setDateRangeState("all")
        setCustomRangeState({ from: undefined, to: undefined })
        setAssigneeIdState(undefined)
        router.replace("/dashboard", { scroll: false })
    }, [router])

    // Sync URL changes back to state (e.g., browser back/forward)
    useEffect(() => {
        const nextRange = isDateRangePreset(searchParams.get("range"))
            ? searchParams.get("range") as DateRangePreset
            : "all"
        if (nextRange !== dateRange) {
            setDateRangeState(nextRange)
        }
        if (nextRange === "custom") {
            const nextFrom = parseDateParam(searchParams.get("from"))
            const nextTo = parseDateParam(searchParams.get("to"))
            if (!datesEqual(nextFrom, customRange.from) || !datesEqual(nextTo, customRange.to)) {
                setCustomRangeState({ from: nextFrom, to: nextTo })
            }
        } else if (customRange.from || customRange.to) {
            setCustomRangeState({ from: undefined, to: undefined })
        }

        const nextAssignee = normalizeFilterValue(searchParams.get("assignee"))
        if (nextAssignee !== assigneeId) {
            setAssigneeIdState(nextAssignee)
        }
    }, [currentQuery]) // eslint-disable-line react-hooks/exhaustive-deps

    // Compute date params for API calls
    const getDateParams = useCallback((): { from_date?: string; to_date?: string } => {
        if (dateRange === "all") {
            return { from_date: formatLocalDate(ALL_TIME_START) }
        }

        const now = new Date()
        let from: Date | undefined
        let to: Date | undefined

        switch (dateRange) {
            case "today":
                from = new Date(now.getFullYear(), now.getMonth(), now.getDate())
                to = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)
                break
            case "week": {
                const dayOfWeek = now.getDay()
                from = new Date(now.getFullYear(), now.getMonth(), now.getDate() - dayOfWeek)
                to = now
                break
            }
            case "month":
                from = new Date(now.getFullYear(), now.getMonth(), 1)
                to = now
                break
            case "custom":
                from = customRange.from
                to = customRange.to
                break
        }

        const params: { from_date?: string; to_date?: string } = {}
        if (from) params.from_date = formatLocalDate(from)
        if (to) params.to_date = formatLocalDate(to)
        return params
    }, [dateRange, customRange])

    // Check if any filters are active
    const hasActiveFilters = dateRange !== "all" || !!assigneeId

    const value: DashboardFiltersContextValue = {
        filters: {
            dateRange,
            customRange,
            assigneeId,
        },
        setDateRange,
        setCustomRange,
        setAssigneeId,
        resetFilters,
        hasActiveFilters,
        getDateParams,
    }

    return (
        <DashboardFiltersContext.Provider value={value}>
            {children}
        </DashboardFiltersContext.Provider>
    )
}
