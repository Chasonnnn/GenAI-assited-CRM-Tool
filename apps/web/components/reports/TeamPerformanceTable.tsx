"use client"

import { useState, type ReactNode } from "react"
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
import { formatDateTime } from "@/lib/formatters"
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
type SortHandler = (key: SortKey) => void

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

function formatDays(value: number | null) {
    return value === null ? "-" : `${value.toFixed(1)}d`
}

function formatPercent(value: number | null) {
    return value === null ? "-" : `${value}%`
}

function conversionBadgeClass(value: number | null) {
    return cn(
        value === null && "border-border bg-muted text-muted-foreground hover:bg-muted",
        value !== null && value >= 30 && "border-primary/20 bg-primary/10 text-primary hover:bg-primary/15",
        value !== null && value >= 20 && value < 30 && "border-border bg-secondary text-secondary-foreground hover:bg-secondary/80",
        value !== null && value < 20 && "border-border bg-background text-muted-foreground hover:bg-muted",
    )
}

function sortPerformanceData(
    data: UserPerformanceData[],
    sortKey: SortKey,
    sortDirection: SortDirection,
) {
    return data.toSorted((a, b) => {
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
}

function buildMobileSummaryData(
    sortedData: UserPerformanceData[],
    unassigned: UnassignedPerformanceData | undefined,
): PerformanceSummaryEntry[] {
    const mobileSummaryData: PerformanceSummaryEntry[] = sortedData.map((user) => ({
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
        mobileSummaryData.push({
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

    return mobileSummaryData
}

function TeamPerformanceCardHeader({
    title,
    asOfLabel,
}: {
    title: string
    asOfLabel?: string | null
}) {
    return (
        <CardHeader>
            <div className="flex items-center justify-between">
                <div>
                    <CardTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" />
                        {title}
                    </CardTitle>
                    {asOfLabel ? (
                        <CardDescription>
                            Data as of {asOfLabel}
                        </CardDescription>
                    ) : null}
                </div>
            </div>
        </CardHeader>
    )
}

function TeamPerformanceStatusCard({
    title,
    status,
}: {
    title: string
    status: "loading" | "error" | "empty"
}) {
    const message = status === "error"
        ? "Unable to load performance data"
        : "No performance data available"

    return (
        <Card>
            <TeamPerformanceCardHeader title={title} />
            <CardContent>
                <div
                    className={cn(
                        "flex h-[300px] items-center justify-center",
                        status === "error" && "text-destructive",
                        status === "empty" && "text-muted-foreground",
                    )}
                >
                    {status === "loading" ? (
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    ) : message}
                </div>
            </CardContent>
        </Card>
    )
}

function TeamPerformanceDataCard({
    title,
    asOfLabel,
    children,
}: {
    title: string
    asOfLabel: string | null
    children: ReactNode
}) {
    return (
        <Card>
            <TeamPerformanceCardHeader title={title} asOfLabel={asOfLabel} />
            <CardContent className="p-0">
                {children}
            </CardContent>
        </Card>
    )
}

function TeamPerformanceMetricTile({
    label,
    value,
}: {
    label: string
    value: ReactNode
}) {
    return (
        <div className="rounded-xl bg-muted/40 p-3">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {label}
            </dt>
            <dd className="mt-1 text-base font-semibold">
                {value}
            </dd>
        </div>
    )
}

function TeamPerformanceMobileSummaryCard({
    columns,
    entry,
}: {
    columns: PerformanceStageColumn[]
    entry: PerformanceSummaryEntry
}) {
    return (
        <li>
            <article
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
                        <TeamPerformanceMetricTile
                            key={column.stage_key}
                            label={column.label}
                            value={entry.stageCounts[column.stage_key] ?? 0}
                        />
                    ))}
                    <TeamPerformanceMetricTile
                        label="Match conversion"
                        value={formatPercent(entry.conversionRate)}
                    />
                    <TeamPerformanceMetricTile
                        label="Avg to match"
                        value={formatDays(entry.avgDaysToMatch)}
                    />
                    <TeamPerformanceMetricTile
                        label="Avg to conversion"
                        value={formatDays(entry.avgDaysToConversion)}
                    />
                </dl>
            </article>
        </li>
    )
}

function TeamPerformanceMobileSummary({
    columns,
    entries,
}: {
    columns: PerformanceStageColumn[]
    entries: PerformanceSummaryEntry[]
}) {
    return (
        <ul
            className="space-y-3 p-4 md:hidden"
            aria-label="Team performance mobile summary"
        >
            {entries.map((entry) => (
                <TeamPerformanceMobileSummaryCard
                    key={entry.id}
                    columns={columns}
                    entry={entry}
                />
            ))}
        </ul>
    )
}

function SortableTableHead({
    children,
    columnKey,
    sortKey,
    sortDirection,
    onSort,
    className,
    buttonClassName,
}: {
    children: ReactNode
    columnKey: SortKey
    sortKey: SortKey
    sortDirection: SortDirection
    onSort: SortHandler
    className?: string
    buttonClassName?: string
}) {
    const handleClick = () => onSort(columnKey)

    return (
        <TableHead className={className}>
            <Button
                variant="ghost"
                size="sm"
                className={cn("h-8 px-2 hover:bg-transparent", buttonClassName)}
                onClick={handleClick}
            >
                {children}
                <SortDirectionIcon
                    columnKey={columnKey}
                    sortKey={sortKey}
                    sortDirection={sortDirection}
                />
            </Button>
        </TableHead>
    )
}

function TeamPerformanceDesktopDataRow({
    stageKeys,
    user,
}: {
    stageKeys: string[]
    user: UserPerformanceData
}) {
    return (
        <TableRow>
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
    )
}

function TeamPerformanceDesktopUnassignedRow({
    stageKeys,
    unassigned,
}: {
    stageKeys: string[]
    unassigned: UnassignedPerformanceData
}) {
    return (
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
    )
}

function TeamPerformanceDesktopTable({
    columns,
    rows,
    unassigned,
    sortKey,
    sortDirection,
    onSort,
}: {
    columns: PerformanceStageColumn[]
    rows: UserPerformanceData[]
    unassigned: UnassignedPerformanceData | undefined
    sortKey: SortKey
    sortDirection: SortDirection
    onSort: SortHandler
}) {
    const stageKeys = columns.map((column) => column.stage_key)

    return (
        <div className="hidden overflow-x-auto md:block">
            <Table className="min-w-[980px]">
                <TableHeader>
                    <TableRow>
                        <SortableTableHead
                            columnKey="user_name"
                            sortKey={sortKey}
                            sortDirection={sortDirection}
                            onSort={onSort}
                            buttonClassName="-ml-3"
                        >
                            Team Member
                        </SortableTableHead>
                        <SortableTableHead
                            columnKey="total_surrogates"
                            sortKey={sortKey}
                            sortDirection={sortDirection}
                            onSort={onSort}
                            className="text-center"
                        >
                            Surrogates
                        </SortableTableHead>
                        {columns.map((column) => {
                            const columnKey: SortKey = `stage:${column.stage_key}`
                            return (
                                <SortableTableHead
                                    key={column.stage_key}
                                    columnKey={columnKey}
                                    sortKey={sortKey}
                                    sortDirection={sortDirection}
                                    onSort={onSort}
                                    className="text-center"
                                >
                                    {column.label}
                                </SortableTableHead>
                            )
                        })}
                        <SortableTableHead
                            columnKey="conversion_rate"
                            sortKey={sortKey}
                            sortDirection={sortDirection}
                            onSort={onSort}
                            className="text-center"
                        >
                            Conv. Rate
                        </SortableTableHead>
                        <SortableTableHead
                            columnKey="avg_days_to_match"
                            sortKey={sortKey}
                            sortDirection={sortDirection}
                            onSort={onSort}
                            className="text-center"
                        >
                            Avg to Match
                        </SortableTableHead>
                        <SortableTableHead
                            columnKey="avg_days_to_conversion"
                            sortKey={sortKey}
                            sortDirection={sortDirection}
                            onSort={onSort}
                            className="text-center"
                        >
                            Avg to Conversion
                        </SortableTableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {rows.map((user) => (
                        <TeamPerformanceDesktopDataRow
                            key={user.user_id}
                            stageKeys={stageKeys}
                            user={user}
                        />
                    ))}
                    {unassigned && unassigned.total_surrogates > 0 ? (
                        <TeamPerformanceDesktopUnassignedRow
                            stageKeys={stageKeys}
                            unassigned={unassigned}
                        />
                    ) : null}
                </TableBody>
            </Table>
        </div>
    )
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

    if (isLoading) {
        return <TeamPerformanceStatusCard title={title} status="loading" />
    }

    if (isError) {
        return <TeamPerformanceStatusCard title={title} status="error" />
    }

    if (!data || data.length === 0) {
        return <TeamPerformanceStatusCard title={title} status="empty" />
    }

    const sortedData = sortPerformanceData(data, sortKey, sortDirection)
    const mobileSummaryData = buildMobileSummaryData(sortedData, unassigned)
    const asOfLabel = formatDateTime(asOf)

    return (
        <TeamPerformanceDataCard title={title} asOfLabel={asOfLabel}>
            <TeamPerformanceMobileSummary columns={columns} entries={mobileSummaryData} />
            <TeamPerformanceDesktopTable
                columns={columns}
                rows={sortedData}
                unassigned={unassigned}
                sortKey={sortKey}
                sortDirection={sortDirection}
                onSort={handleSort}
            />
        </TeamPerformanceDataCard>
    )
}
