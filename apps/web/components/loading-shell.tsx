import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"

type LoadingShellVariant = "table" | "cards" | "profile" | "calendar"

interface LoadingShellProps {
    variant: LoadingShellVariant
}

/**
 * Reusable loading skeleton layouts.
 * Server component - renders appropriate skeleton based on page type.
 */
export function LoadingShell({ variant }: LoadingShellProps) {
    switch (variant) {
        case "table":
            return <TableSkeleton />
        case "cards":
            return <CardsSkeleton />
        case "profile":
            return <ProfileSkeleton />
        case "calendar":
            return <CalendarSkeleton />
        default:
            return <CardsSkeleton />
    }
}

function TableSkeleton() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-14 items-center justify-between px-6">
                    <Skeleton className="h-7 w-32" />
                    <Skeleton className="h-9 w-24" />
                </div>
            </div>

            {/* Filters */}
            <div className="border-b border-border px-6 py-3">
                <div className="flex items-center gap-4">
                    <Skeleton className="h-9 w-64" />
                    <Skeleton className="h-9 w-32" />
                    <Skeleton className="h-9 w-32" />
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 p-6">
                <div className="rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                {Array.from({ length: 5 }).map((_, i) => (
                                    <TableHead key={i}>
                                        <Skeleton className="h-4 w-20" />
                                    </TableHead>
                                ))}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {Array.from({ length: 8 }).map((_, rowIdx) => (
                                <TableRow key={rowIdx}>
                                    {Array.from({ length: 5 }).map((_, colIdx) => (
                                        <TableCell key={colIdx}>
                                            <Skeleton className="h-4 w-full max-w-[120px]" />
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </div>
        </div>
    )
}

function CardsSkeleton() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-14 items-center justify-between px-6">
                    <Skeleton className="h-7 w-32" />
                    <Skeleton className="h-9 w-24" />
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6">
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Card key={i}>
                            <CardHeader>
                                <Skeleton className="h-5 w-3/4" />
                                <Skeleton className="h-4 w-1/2" />
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    <Skeleton className="h-4 w-full" />
                                    <Skeleton className="h-4 w-5/6" />
                                    <Skeleton className="h-4 w-4/6" />
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    )
}

function ProfileSkeleton() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Header with back button */}
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-14 items-center gap-4 px-6">
                    <Skeleton className="size-9" />
                    <Skeleton className="h-7 w-48" />
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6">
                <div className="grid gap-6 lg:grid-cols-3">
                    {/* Profile Card */}
                    <Card className="lg:col-span-1">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center gap-4">
                                <Skeleton className="size-24 rounded-full" />
                                <div className="text-center">
                                    <Skeleton className="mx-auto h-6 w-32" />
                                    <Skeleton className="mx-auto mt-2 h-4 w-24" />
                                </div>
                                <div className="mt-4 w-full space-y-2">
                                    {Array.from({ length: 4 }).map((_, i) => (
                                        <div key={i} className="flex justify-between">
                                            <Skeleton className="h-4 w-20" />
                                            <Skeleton className="h-4 w-24" />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Details */}
                    <div className="space-y-6 lg:col-span-2">
                        <Card>
                            <CardHeader>
                                <Skeleton className="h-5 w-24" />
                            </CardHeader>
                            <CardContent>
                                <div className="grid gap-4 sm:grid-cols-2">
                                    {Array.from({ length: 6 }).map((_, i) => (
                                        <div key={i}>
                                            <Skeleton className="mb-1 h-3 w-16" />
                                            <Skeleton className="h-5 w-full" />
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    )
}

function CalendarSkeleton() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-14 items-center justify-between px-6">
                    <Skeleton className="h-7 w-32" />
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-9 w-24" />
                        <Skeleton className="h-9 w-24" />
                    </div>
                </div>
            </div>

            {/* Calendar toolbar */}
            <div className="border-b border-border px-6 py-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Skeleton className="size-9" />
                        <Skeleton className="size-9" />
                        <Skeleton className="h-6 w-32" />
                    </div>
                    <div className="flex gap-1">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} className="h-8 w-16" />
                        ))}
                    </div>
                </div>
            </div>

            {/* Calendar grid */}
            <div className="flex-1 p-6">
                <div className="h-full rounded-lg border">
                    {/* Week header */}
                    <div className="grid grid-cols-7 border-b">
                        {Array.from({ length: 7 }).map((_, i) => (
                            <div key={i} className="border-r p-2 last:border-r-0">
                                <Skeleton className="mx-auto h-4 w-8" />
                            </div>
                        ))}
                    </div>
                    {/* Calendar body */}
                    <div className="grid flex-1 grid-cols-7">
                        {Array.from({ length: 35 }).map((_, i) => (
                            <div
                                key={i}
                                className="h-24 border-b border-r p-2 last:border-r-0"
                            >
                                <Skeleton className="mb-2 h-4 w-6" />
                                {i % 3 === 0 && <Skeleton className="h-5 w-full" />}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
