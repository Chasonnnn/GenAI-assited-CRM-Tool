"use client"

import { useState } from "react"
import { CSVUpload } from "@/components/import/CSVUpload"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Loader2Icon,
    FileUpIcon,
    CheckCircleIcon,
    XCircleIcon,
    ClockIcon,
    MoreHorizontalIcon,
    Trash2Icon,
    RefreshCcwIcon,
    PlayIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
    useCancelImport,
    useImports,
    useRetryImport,
    useRunImportInline,
    type ImportActionResponse,
} from "@/lib/hooks/use-import"
import type { ImportHistoryItem } from "@/lib/api/import"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"

export default function CSVImportPage() {
    const { data: imports = [], isLoading, refetch } = useImports()
    const { user } = useAuth()
    const cancelMutation = useCancelImport()
    const retryMutation = useRetryImport()
    const runInlineMutation = useRunImportInline()
    const [deleteTarget, setDeleteTarget] = useState<ImportHistoryItem | null>(null)

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "completed":
                return { variant: "default" as const, icon: CheckCircleIcon, color: "bg-green-500/10 text-green-600 border-green-500/20" }
            case "failed":
            case "rejected":
            case "cancelled":
                return { variant: "destructive" as const, icon: XCircleIcon, color: "bg-destructive/10 text-destructive border-destructive/20" }
            case "pending":
            case "awaiting_approval":
            case "approved":
            case "running":
                return { variant: "secondary" as const, icon: ClockIcon, color: "bg-amber-500/10 text-amber-600 border-amber-500/20" }
            default:
                return { variant: "secondary" as const, icon: FileUpIcon, color: "" }
        }
    }

    const canRetry = (imp: ImportHistoryItem) =>
        (imp.status === "approved" || imp.status === "failed") &&
        (user?.role === "admin" || user?.role === "developer")

    const canRunInline = (imp: ImportHistoryItem) =>
        (imp.status === "approved" || imp.status === "failed") &&
        (user?.role === "admin" || user?.role === "developer")

    const canDelete = (imp: ImportHistoryItem) => imp.status !== "running"

    const handleRetry = async (imp: ImportHistoryItem) => {
        try {
            const response: ImportActionResponse = await retryMutation.mutateAsync(imp.id)
            toast.success(response.message || "Import queued for processing")
        } catch (err: unknown) {
            toast.error(err instanceof Error ? err.message : "Failed to retry import")
        }
    }

    const handleRunInline = async (imp: ImportHistoryItem) => {
        try {
            const response: ImportActionResponse = await runInlineMutation.mutateAsync(imp.id)
            toast.success(response.message || "Import processed inline")
        } catch (err: unknown) {
            toast.error(err instanceof Error ? err.message : "Failed to run import inline")
        }
    }

    const handleConfirmDelete = async () => {
        if (!deleteTarget) return
        try {
            const response = await cancelMutation.mutateAsync(deleteTarget.id)
            toast.success(response.message || "Import cancelled")
            setDeleteTarget(null)
        } catch (err: unknown) {
            toast.error(err instanceof Error ? err.message : "Failed to cancel import")
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">CSV Import</h1>
                        <p className="text-sm text-muted-foreground">Bulk import surrogates from CSV files</p>
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
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {imports.map((imp) => {
                                        const badge = getStatusBadge(imp.status)
                                        const Icon = badge.icon
                                        const showRetry = canRetry(imp)
                                        const showRunInline = canRunInline(imp)
                                        const showDelete = canDelete(imp)
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
                                                <TableCell className="text-right">
                                                    {showRetry || showRunInline || showDelete ? (
                                                        <DropdownMenu>
                                                            <DropdownMenuTrigger
                                                                render={(props) => (
                                                                    <Button
                                                                        {...props}
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        disabled={
                                                                            cancelMutation.isPending ||
                                                                            retryMutation.isPending ||
                                                                            runInlineMutation.isPending
                                                                        }
                                                                    >
                                                                        <MoreHorizontalIcon className="size-4" />
                                                                    </Button>
                                                                )}
                                                            />
                                                            <DropdownMenuContent align="end">
                                                                {showRunInline && (
                                                                    <DropdownMenuItem
                                                                        onClick={() => handleRunInline(imp)}
                                                                        disabled={runInlineMutation.isPending}
                                                                    >
                                                                        <PlayIcon className="mr-2 size-4" />
                                                                        Run now
                                                                    </DropdownMenuItem>
                                                                )}
                                                                {showRetry && (
                                                                    <DropdownMenuItem
                                                                        onClick={() => handleRetry(imp)}
                                                                        disabled={retryMutation.isPending}
                                                                    >
                                                                        <RefreshCcwIcon className="mr-2 size-4" />
                                                                        Retry
                                                                    </DropdownMenuItem>
                                                                )}
                                                                {showDelete && (
                                                                    <DropdownMenuItem
                                                                        onClick={() => setDeleteTarget(imp)}
                                                                        disabled={cancelMutation.isPending}
                                                                    >
                                                                        <Trash2Icon className="mr-2 size-4" />
                                                                        Delete
                                                                    </DropdownMenuItem>
                                                                )}
                                                            </DropdownMenuContent>
                                                        </DropdownMenu>
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

            <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete import?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will cancel the import and remove it from history. You can re-upload the CSV if needed.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep</AlertDialogCancel>
                        <AlertDialogAction onClick={handleConfirmDelete} disabled={cancelMutation.isPending}>
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
