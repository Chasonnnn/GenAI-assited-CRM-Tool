"use client"

import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, Loader2Icon, UsersIcon } from "lucide-react"
import type {
    PerformanceStageColumn,
    UnassignedPerformanceData,
    UserPerformanceData,
} from "@/lib/api/analytics"
import { cn } from "@/lib/utils"

interface TeamPerformanceTableProps {
    columns: PerformanceStageColumn[]
    data: UserPerformanceData[] | undefined
    unassigned: UnassignedPerformanceData | undefined
    conversionStageKey?: string | null
    isLoading?: boolean
    isError?: boolean
    title?: string
    asOf?: string
}

type SortKey =
    | "user_name"
    | "total_surrogates"
    | "conversion_rate"
    | "avg_days_to_match"
    | "avg_days_to_conversion"
    | `stage:${string}`
type SortDirection = "asc" | "desc"

type PerformanceSummaryEntry = {
    id: string
    name: string
    archivedCount: number
    totalSurrogates: number
    stageCounts: Record<string, number>
    conversionRate: number | null
    avgDaysToMatch: number | null
    avgDaysToConversion: number | null
    muted?: boolean
}

function SortDirectionIcon({
    columnKey,
    sortKey,
    sortDirection,
}: {
    columnKey: SortKey
    sortKey: SortKey
    sortDirection: SortDirection
}) {
    if (sortKey !== columnKey) {
        return <ArrowUpDownIcon className="ml-1 size-3 text-muted-foreground/50" />
    }
    return sortDirection === "asc"
        ? <ArrowUpIcon className="ml-1 size-3" />
        : <ArrowDownIcon className="ml-1 size-3" />
}

function getSortableValue(user: UserPerformanceData, sortKey: SortKey): number | string {
    if (sortKey === "user_name") return user.user_name
    if (sortKey === "total_surrogates") return user.total_surrogates
    if (sortKey === "conversion_rate") return user.conversion_rate
    if (sortKey === "avg_days_to_match") return user.avg_days_to_match ?? -Infinity
    if (sortKey === "avg_days_to_conversion") return user.avg_days_to_conversion ?? -Infinity
    if (sortKey.startsWith("stage:")) {
        return user.stage_counts[sortKey.slice(6)] ?? 0
    }
    return 0
}

export function TeamPerformanceTable({
    columns,
    data,
    unassigned,
    isLoading = false,
    isError = false,
    title = "Individual Performance",
    asOf,
}: TeamPerformanceTableProps) {
    const [sortKey, setSortKey] = useState<SortKey>("total_surrogates")
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc")

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc")
            return
        }
        setSortKey(key)
        setSortDirection("desc")
    }

    const sortedData = useMemo(() => {
        if (!data) return []
        return [...data].sort((a, b) => {
            const aValue = getSortableValue(a, sortKey)
            const bValue = getSortableValue(b, sortKey)
            if (typeof aValue === "string" && typeof bValue === "string") {
                return sortDirection === "asc"
                    ? aValue.localeCompare(bValue)
                    : bValue.localeCompare(aValue)
            }
            return sortDirection === "asc"
                ? Number(aValue) - Number(bValue)
                : Number(bValue) - Number(aValue)
        })
    }, [data, sortDirection, sortKey])

    const mobileSummaryData = useMemo<PerformanceSummaryEntry[]>(() => {
        const entries: PerformanceSummaryEntry[] = sortedData.map((user) => ({
            id: user.user_id,
            name: user.user_name,
            archivedCount: user.archived_count,
            totalSurrogates: user.total_surrogates,
            stageCounts: user.stage_counts,
            conversionRate: user.conversion_rate,
            avgDaysToMatch: user.avg_days_to_match,
            avgDaysToConversion: user.avg_days_to_conversion,
        }))

        if (unassigned && unassigned.total_surrogates > 0) {
            entries.push({
                id: "unassigned",
                name: "Unassigned",
                archivedCount: unassigned.archived_count,
                totalSurrogates: unassigned.total_surrogates,
                stageCounts: unassigned.stage_counts,
                conversionRate: null,
                avgDaysToMatch: null,
                avgDaysToConversion: null,
                muted: true,
            })
        }

        return entries
    }, [sortedData, unassigned])

    const stageKeys = columns.map((column) => column.stage_key)

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" />
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (isError) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" />
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-destructive">
                        Unable to load performance data
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (!data || data.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" />
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                        No performance data available
                    </div>
                </CardContent>
            </Card>
        )
    }

    const formatDays = (value: number | null) => (value === null ? "-" : `${value.toFixed(1)}d`)
    const formatPercent = (value: number | null) => (value === null ? "-" : `${value}%`)
    const conversionBadgeClass = (value: number | null) =>
        cn(
            value === null && "border-border bg-muted text-muted-foreground hover:bg-muted",
            value !== null && value >= 30 && "border-primary/20 bg-primary/10 text-primary hover:bg-primary/15",
            value !== null && value >= 20 && value < 30 && "border-border bg-secondary text-secondary-foreground hover:bg-secondary/80",
            value !== null && value < 20 && "border-border bg-background text-muted-foreground hover:bg-muted",
        )

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <UsersIcon className="size-5" />
                            {title}
                        </CardTitle>
                        {asOf ? (
                            <CardDescription>
                                Data as of {new Date(asOf).toLocaleString()}
                            </CardDescription>
                        ) : null}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-0">
                <div
                    className="space-y-3 p-4 md:hidden"
                    role="list"
                    aria-label="Team performance mobile summary"
                >
                    {mobileSummaryData.map((entry) => (
                        <article
                            key={entry.id}
                            aria-label={`Performance summary for ${entry.name}`}
                            className={cn(
                                "rounded-2xl border border-border/70 bg-background p-4 shadow-sm",
                                entry.muted && "bg-muted/30",
                            )}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="truncate font-semibold">{entry.name}</h3>
                                        {entry.archivedCount > 0 ? (
                                            <Badge variant="outline" className="text-xs">
                                                {entry.archivedCount} archived
                                            </Badge>
                                        ) : null}
                                    </div>
                                    <p className="mt-1 text-sm text-muted-foreground">
                                        {entry.totalSurrogates} surrogates
                                    </p>
                                </div>
                                <Badge variant="outline" className={conversionBadgeClass(entry.conversionRate)}>
                                    {formatPercent(entry.conversionRate)}
                                </Badge>
                            </div>

                            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                                {columns.map((column) => (
                                    <div key={column.stage_key} className="rounded-xl bg-muted/40 p-3">
                                        <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                            {column.label}
                                        </dt>
                                        <dd className="mt-1 text-base font-semibold">
                                            {entry.stageCounts[column.stage_key] ?? 0}
                                        </dd>
                                    </div>
                                ))}
                                <div className="rounded-xl bg-muted/40 p-3">
                                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                        Match conversion
                                    </dt>
                                    <dd className="mt-1 text-base font-semibold">
                                        {formatPercent(entry.conversionRate)}
                                    </dd>
                                </div>
                                <div className="rounded-xl bg-muted/40 p-3">
                                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                        Avg to match
                                    </dt>
                                    <dd className="mt-1 text-base font-semibold">
                                        {formatDays(entry.avgDaysToMatch)}
                                    </dd>
                                </div>
                                <div className="rounded-xl bg-muted/40 p-3">
                                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                        Avg to conversion
                                    </dt>
                                    <dd className="mt-1 text-base font-semibold">
                                        {formatDays(entry.avgDaysToConversion)}
                                    </dd>
                                </div>
                            </dl>
                        </article>
                    ))}
                </div>

                <div className="hidden overflow-x-auto md:block">
                    <Table className="min-w-[980px]">
                        <TableHeader>
                            <TableRow>
                                <TableHead>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 -ml-3 px-2 hover:bg-transparent"
                                        onClick={() => handleSort("user_name")}
                                    >
                                        Team Member
                                        <SortDirectionIcon columnKey="user_name" sortKey={sortKey} sortDirection={sortDirection} />
                                    </Button>
                                </TableHead>
                                <TableHead className="text-center">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 px-2 hover:bg-transparent"
                                        onClick={() => handleSort("total_surrogates")}
                                    >
                                        Surrogates
                                        <SortDirectionIcon columnKey="total_surrogates" sortKey={sortKey} sortDirection={sortDirection} />
                                    </Button>
                                </TableHead>
                                {columns.map((column) => {
                                    const columnKey = `stage:${column.stage_key}` as const
                                    return (
                                        <TableHead key={column.stage_key} className="text-center">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-8 px-2 hover:bg-transparent"
                                                onClick={() => handleSort(columnKey)}
                                            >
                                                {column.label}
                                                <SortDirectionIcon columnKey={columnKey} sortKey={sortKey} sortDirection={sortDirection} />
                                            </Button>
                                        </TableHead>
                                    )
                                })}
                                <TableHead className="text-center">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 px-2 hover:bg-transparent"
                                        onClick={() => handleSort("conversion_rate")}
                                    >
                                        Conv. Rate
                                        <SortDirectionIcon columnKey="conversion_rate" sortKey={sortKey} sortDirection={sortDirection} />
                                    </Button>
                                </TableHead>
                                <TableHead className="text-center">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 px-2 hover:bg-transparent"
                                        onClick={() => handleSort("avg_days_to_match")}
                                    >
                                        Avg to Match
                                        <SortDirectionIcon columnKey="avg_days_to_match" sortKey={sortKey} sortDirection={sortDirection} />
                                    </Button>
                                </TableHead>
                                <TableHead className="text-center">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 px-2 hover:bg-transparent"
                                        onClick={() => handleSort("avg_days_to_conversion")}
                                    >
                                        Avg to Conversion
                                        <SortDirectionIcon columnKey="avg_days_to_conversion" sortKey={sortKey} sortDirection={sortDirection} />
                                    </Button>
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedData.map((user) => (
                                <TableRow key={user.user_id}>
                                    <TableCell className="font-medium">
                                        {user.user_name}
                                        {user.archived_count > 0 ? (
                                            <Badge variant="outline" className="ml-2 text-xs">
                                                {user.archived_count} archived
                                            </Badge>
                                        ) : null}
                                    </TableCell>
                                    <TableCell className="text-center font-medium">{user.total_surrogates}</TableCell>
                                    {stageKeys.map((stageKey) => (
                                        <TableCell key={stageKey} className="text-center">
                                            {user.stage_counts[stageKey] ?? 0}
                                        </TableCell>
                                    ))}
                                    <TableCell className="text-center">
                                        <Badge variant="outline" className={conversionBadgeClass(user.conversion_rate)}>
                                            {user.conversion_rate}%
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-center text-muted-foreground">
                                        {formatDays(user.avg_days_to_match)}
                                    </TableCell>
                                    <TableCell className="text-center text-muted-foreground">
                                        {formatDays(user.avg_days_to_conversion)}
                                    </TableCell>
                                </TableRow>
                            ))}
                            {unassigned && unassigned.total_surrogates > 0 ? (
                                <TableRow className="bg-muted/30">
                                    <TableCell className="font-medium text-muted-foreground">
                                        Unassigned
                                        {unassigned.archived_count > 0 ? (
                                            <Badge variant="outline" className="ml-2 text-xs">
                                                {unassigned.archived_count} archived
                                            </Badge>
                                        ) : null}
                                    </TableCell>
                                    <TableCell className="text-center font-medium text-muted-foreground">
                                        {unassigned.total_surrogates}
                                    </TableCell>
                                    {stageKeys.map((stageKey) => (
                                        <TableCell key={stageKey} className="text-center text-muted-foreground">
                                            {unassigned.stage_counts[stageKey] ?? 0}
                                        </TableCell>
                                    ))}
                                    <TableCell className="text-center">-</TableCell>
                                    <TableCell className="text-center">-</TableCell>
                                    <TableCell className="text-center">-</TableCell>
                                </TableRow>
                            ) : null}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    )
}
