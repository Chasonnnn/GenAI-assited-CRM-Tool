"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Loader2Icon, ArrowUpDownIcon, ArrowUpIcon, ArrowDownIcon, UsersIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { UserPerformanceData, UnassignedPerformanceData } from "@/lib/api/analytics"
import { cn } from "@/lib/utils"

interface TeamPerformanceTableProps {
    data: UserPerformanceData[] | undefined
    unassigned: UnassignedPerformanceData | undefined
    isLoading?: boolean
    isError?: boolean
    title?: string
    asOf?: string
}

type SortKey = "user_name" | "total_cases" | "contacted" | "qualified" | "pending_match" | "matched" | "applied" | "lost" | "conversion_rate" | "avg_days_to_match" | "avg_days_to_apply"
type SortDirection = "asc" | "desc"

export function TeamPerformanceTable({
    data,
    unassigned,
    isLoading = false,
    isError = false,
    title = "Individual Performance",
    asOf,
}: TeamPerformanceTableProps) {
    const [sortKey, setSortKey] = useState<SortKey>("total_cases")
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc")

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc")
        } else {
            setSortKey(key)
            setSortDirection("desc")
        }
    }

    const sortedData = useMemo(() => {
        if (!data) return []
        return [...data].sort((a, b) => {
            let aVal = a[sortKey]
            let bVal = b[sortKey]

            // Handle null values
            if (aVal === null) aVal = -Infinity
            if (bVal === null) bVal = -Infinity

            if (typeof aVal === "string" && typeof bVal === "string") {
                return sortDirection === "asc"
                    ? aVal.localeCompare(bVal)
                    : bVal.localeCompare(aVal)
            }

            const numA = Number(aVal)
            const numB = Number(bVal)
            return sortDirection === "asc" ? numA - numB : numB - numA
        })
    }, [data, sortKey, sortDirection])

    const SortIcon = ({ columnKey }: { columnKey: SortKey }) => {
        if (sortKey !== columnKey) {
            return <ArrowUpDownIcon className="ml-1 size-3 text-muted-foreground/50" />
        }
        return sortDirection === "asc"
            ? <ArrowUpIcon className="ml-1 size-3" />
            : <ArrowDownIcon className="ml-1 size-3" />
    }

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

    const formatDays = (value: number | null) => {
        if (value === null) return "-"
        return `${value.toFixed(1)}d`
    }

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <UsersIcon className="size-5" />
                            {title}
                        </CardTitle>
                        {asOf && (
                            <CardDescription>
                                Data as of {new Date(asOf).toLocaleString()}
                            </CardDescription>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-0 overflow-x-auto">
                <Table className="min-w-[900px]">
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
                                    <SortIcon columnKey="user_name" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("total_cases")}
                                >
                                    Cases
                                    <SortIcon columnKey="total_cases" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("contacted")}
                                >
                                    Contacted
                                    <SortIcon columnKey="contacted" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("qualified")}
                                >
                                    Qualified
                                    <SortIcon columnKey="qualified" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("pending_match")}
                                >
                                    Ready to Match
                                    <SortIcon columnKey="pending_match" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("matched")}
                                >
                                    Matched
                                    <SortIcon columnKey="matched" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("applied")}
                                >
                                    Applied
                                    <SortIcon columnKey="applied" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("lost")}
                                >
                                    Lost
                                    <SortIcon columnKey="lost" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("conversion_rate")}
                                >
                                    Conv. Rate
                                    <SortIcon columnKey="conversion_rate" />
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
                                    <SortIcon columnKey="avg_days_to_match" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-center">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 hover:bg-transparent"
                                    onClick={() => handleSort("avg_days_to_apply")}
                                >
                                    Avg to Apply
                                    <SortIcon columnKey="avg_days_to_apply" />
                                </Button>
                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {sortedData.map((user) => (
                            <TableRow key={user.user_id}>
                                <TableCell className="font-medium">
                                    {user.user_name}
                                    {user.archived_count > 0 && (
                                        <Badge variant="outline" className="ml-2 text-xs">
                                            {user.archived_count} archived
                                        </Badge>
                                    )}
                                </TableCell>
                                <TableCell className="text-center font-medium">
                                    {user.total_cases}
                                </TableCell>
                                <TableCell className="text-center">
                                    {user.contacted}
                                </TableCell>
                                <TableCell className="text-center">
                                    {user.qualified}
                                </TableCell>
                                <TableCell className="text-center">
                                    {user.pending_match}
                                </TableCell>
                                <TableCell className="text-center">
                                    {user.matched}
                                </TableCell>
                                <TableCell className="text-center">
                                    <span className="text-green-600 font-medium">
                                        {user.applied}
                                    </span>
                                </TableCell>
                                <TableCell className="text-center">
                                    <span className={cn(
                                        user.lost > 0 && "text-red-600"
                                    )}>
                                        {user.lost}
                                    </span>
                                </TableCell>
                                <TableCell className="text-center">
                                    <Badge
                                        variant={user.conversion_rate >= 20 ? "default" : "secondary"}
                                        className={cn(
                                            user.conversion_rate >= 30 && "bg-green-500 hover:bg-green-600",
                                            user.conversion_rate >= 20 && user.conversion_rate < 30 && "bg-blue-500 hover:bg-blue-600"
                                        )}
                                    >
                                        {user.conversion_rate}%
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {formatDays(user.avg_days_to_match)}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {formatDays(user.avg_days_to_apply)}
                                </TableCell>
                            </TableRow>
                        ))}

                        {/* Unassigned row */}
                        {unassigned && unassigned.total_cases > 0 && (
                            <TableRow className="bg-muted/30">
                                <TableCell className="font-medium text-muted-foreground">
                                    Unassigned
                                    {unassigned.archived_count > 0 && (
                                        <Badge variant="outline" className="ml-2 text-xs">
                                            {unassigned.archived_count} archived
                                        </Badge>
                                    )}
                                </TableCell>
                                <TableCell className="text-center font-medium text-muted-foreground">
                                    {unassigned.total_cases}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {unassigned.contacted}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {unassigned.qualified}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {unassigned.pending_match}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {unassigned.matched}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {unassigned.applied}
                                </TableCell>
                                <TableCell className="text-center text-muted-foreground">
                                    {unassigned.lost}
                                </TableCell>
                                <TableCell className="text-center">-</TableCell>
                                <TableCell className="text-center">-</TableCell>
                                <TableCell className="text-center">-</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    )
}
