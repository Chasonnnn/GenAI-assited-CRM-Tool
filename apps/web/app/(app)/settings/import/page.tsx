"use client"

import { CSVUpload } from "@/components/import/CSVUpload"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Loader2Icon, FileUpIcon, CheckCircleIcon, XCircleIcon, ClockIcon } from "lucide-react"
import { useImports } from "@/lib/hooks/use-import"
import { formatDistanceToNow } from "date-fns"

export default function CSVImportPage() {
    const { data: imports = [], isLoading, refetch } = useImports()

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "completed":
                return { variant: "default" as const, icon: CheckCircleIcon, color: "bg-green-500/10 text-green-600 border-green-500/20" }
            case "failed":
                return { variant: "destructive" as const, icon: XCircleIcon, color: "bg-destructive/10 text-destructive border-destructive/20" }
            case "pending":
            case "in_progress":
                return { variant: "secondary" as const, icon: ClockIcon, color: "bg-amber-500/10 text-amber-600 border-amber-500/20" }
            default:
                return { variant: "secondary" as const, icon: FileUpIcon, color: "" }
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">CSV Import</h1>
                        <p className="text-sm text-muted-foreground">Bulk import cases from CSV files</p>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {/* Upload Section */}
                <CSVUpload onImportComplete={() => refetch()} />

                {/* Import History */}
                <Card>
                    <CardHeader>
                        <CardTitle>Import History</CardTitle>
                        <CardDescription>View past imports and their results</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : imports.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                                <FileUpIcon className="mb-4 size-12" />
                                <p className="text-lg font-medium">No imports yet</p>
                                <p className="text-sm">Upload a CSV file above to get started</p>
                            </div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Filename</TableHead>
                                        <TableHead>Import Date</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="text-right">Total</TableHead>
                                        <TableHead className="text-right">Imported</TableHead>
                                        <TableHead className="text-right">Skipped</TableHead>
                                        <TableHead className="text-right">Errors</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {imports.map((imp) => {
                                        const badge = getStatusBadge(imp.status)
                                        const Icon = badge.icon
                                        return (
                                            <TableRow key={imp.id}>
                                                <TableCell className="font-medium">{imp.filename}</TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {formatDistanceToNow(new Date(imp.created_at), { addSuffix: true })}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={badge.variant} className={`gap-1 ${badge.color}`}>
                                                        <Icon className="size-3" />
                                                        {imp.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right">{imp.total_rows}</TableCell>
                                                <TableCell className="text-right">
                                                    {imp.imported_count !== null ? (
                                                        <span className="text-green-600 dark:text-green-400 font-medium">
                                                            {imp.imported_count}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {imp.skipped_count !== null ? (
                                                        <span className="text-amber-600 dark:text-amber-400">
                                                            {imp.skipped_count}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {imp.error_count !== null && imp.error_count > 0 ? (
                                                        <span className="text-destructive font-medium">{imp.error_count}</span>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        )
                                    })}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
