"use client"

import { useState } from "react"
import {
    AlertCircleIcon,
    Clock3Icon,
    FileClockIcon,
    HistoryIcon,
    Loader2Icon,
    RotateCcwIcon,
} from "lucide-react"

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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/formatters"
import type { EmailTemplateVersion } from "@/lib/api/email-templates"

interface EmailTemplateHistorySheetProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    templateName: string
    currentVersion: number | null
    versions: EmailTemplateVersion[]
    isLoading: boolean
    isError: boolean
    onRetry: () => void
    onRestore: (version: number) => Promise<void> | void
    isRestoring: boolean
}

function getVersionActionLabel(comment: string | null): string {
    const normalized = comment?.trim()
    if (!normalized) return "Template saved"

    if (normalized.toLowerCase() === "created") return "Template created"
    if (normalized.toLowerCase() === "updated") return "Template updated"

    const rollbackMatch = normalized.match(/^rollback from v(\d+)$/i)
    if (rollbackMatch?.[1]) {
        return `Restored from version ${rollbackMatch[1]}`
    }

    return normalized
}

function HistorySkeleton() {
    return (
        <div className="space-y-3 px-6 py-5" aria-label="Loading template history">
            <span className="sr-only">Loading version history…</span>
            {[0, 1, 2].map((item) => (
                <div key={item} className="space-y-3 rounded-xl border p-4">
                    <div className="flex items-center justify-between gap-4">
                        <Skeleton className="h-5 w-24" />
                        <Skeleton className="h-8 w-20" />
                    </div>
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-4 w-52" />
                </div>
            ))}
        </div>
    )
}

export function EmailTemplateHistorySheet({
    open,
    onOpenChange,
    templateName,
    currentVersion,
    versions,
    isLoading,
    isError,
    onRetry,
    onRestore,
    isRestoring,
}: EmailTemplateHistorySheetProps) {
    const [restoreTarget, setRestoreTarget] = useState<number | null>(null)

    const handleRestore = async () => {
        if (restoreTarget === null) return
        try {
            await onRestore(restoreTarget)
            setRestoreTarget(null)
        } catch {
            // The caller owns user-facing error reporting. Keep confirmation open for retry.
        }
    }

    return (
        <>
            <Sheet open={open} onOpenChange={onOpenChange}>
                <SheetContent className="w-full sm:max-w-lg">
                    <SheetHeader className="border-b pr-16">
                        <div className="flex items-center gap-2">
                            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                <HistoryIcon className="size-4" aria-hidden="true" />
                            </div>
                            <div className="min-w-0">
                                <SheetTitle>Template history</SheetTitle>
                                <p className="truncate text-sm font-medium">{templateName}</p>
                            </div>
                        </div>
                        <SheetDescription>
                            Review saved changes or restore an earlier version. Restoring always
                            adds a new version, so the audit trail stays intact.
                        </SheetDescription>
                        {currentVersion !== null && (
                            <Badge variant="secondary" className="mt-2">
                                Current version {currentVersion}
                            </Badge>
                        )}
                    </SheetHeader>

                    {isLoading ? (
                        <HistorySkeleton />
                    ) : isError ? (
                        <div className="p-6">
                            <Alert variant="destructive">
                                <AlertCircleIcon aria-hidden="true" />
                                <AlertTitle>Couldn’t load history</AlertTitle>
                                <AlertDescription>
                                    <p>Check your connection, then try loading the saved versions again.</p>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="mt-3"
                                        onClick={onRetry}
                                    >
                                        Try again
                                    </Button>
                                </AlertDescription>
                            </Alert>
                        </div>
                    ) : versions.length === 0 ? (
                        <div className="flex flex-1 flex-col items-center justify-center px-6 py-16 text-center">
                            <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-muted">
                                <FileClockIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                            </div>
                            <h3 className="font-medium">No saved versions yet</h3>
                            <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                                Version history will appear after this organization template is saved.
                            </p>
                        </div>
                    ) : (
                        <ScrollArea className="min-h-0 flex-1">
                            <div className="space-y-3 px-6 py-5">
                                {versions.map((version) => {
                                    const isCurrent = version.version === currentVersion
                                    return (
                                        <article
                                            key={version.id}
                                            className={
                                                isCurrent
                                                    ? "rounded-xl border border-primary/40 bg-primary/5 p-4"
                                                    : "rounded-xl border bg-card p-4"
                                            }
                                            aria-label={`Version ${version.version}`}
                                        >
                                            <div className="flex items-start justify-between gap-4">
                                                <div className="min-w-0 space-y-2">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <Badge variant={isCurrent ? "default" : "outline"}>
                                                            Version {version.version}
                                                        </Badge>
                                                        {isCurrent && (
                                                            <Badge variant="secondary">Current</Badge>
                                                        )}
                                                    </div>
                                                    <p className="font-medium">
                                                        {getVersionActionLabel(version.comment)}
                                                    </p>
                                                </div>
                                                {!isCurrent && (
                                                    <Button
                                                        type="button"
                                                        variant="outline"
                                                        size="sm"
                                                        aria-label={`Restore version ${version.version}`}
                                                        disabled={isRestoring}
                                                        onClick={() => setRestoreTarget(version.version)}
                                                    >
                                                        <RotateCcwIcon className="size-3.5" aria-hidden="true" />
                                                        Restore
                                                    </Button>
                                                )}
                                            </div>
                                            <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                                                <p className="flex items-center gap-1.5">
                                                    <Clock3Icon className="size-3.5" aria-hidden="true" />
                                                    {formatDateTime(version.created_at, "Date unavailable")}
                                                </p>
                                                <p>
                                                    {version.created_by_user_id
                                                        ? "Saved by a team member"
                                                        : "Saved automatically"}
                                                </p>
                                            </div>
                                        </article>
                                    )
                                })}
                            </div>
                        </ScrollArea>
                    )}
                </SheetContent>
            </Sheet>

            <AlertDialog
                open={restoreTarget !== null}
                onOpenChange={(nextOpen) => {
                    if (!nextOpen && !isRestoring) setRestoreTarget(null)
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Restore version {restoreTarget}?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            This replaces the editor draft with version {restoreTarget} and creates
                            a new version. Existing history is never overwritten.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isRestoring}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleRestore}
                            disabled={isRestoring}
                        >
                            {isRestoring && (
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                            )}
                            Restore version
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}
