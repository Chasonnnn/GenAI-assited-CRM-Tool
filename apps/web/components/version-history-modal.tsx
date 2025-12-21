"use client"

/**
 * Reusable Version History Modal
 * 
 * Shows version history for pipelines, email templates, and other versioned entities.
 * Supports viewing version details and rollback (developer only).
 */

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { History, RotateCcw, Calendar, MessageSquare, ChevronDown, ChevronUp } from "lucide-react"
import { format } from "date-fns"
import { useState } from "react"

export interface VersionItem {
    id: string
    version: number
    payload: Record<string, unknown>
    comment: string | null
    created_by_user_id: string | null
    created_at: string
}

interface VersionHistoryModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    title: string
    entityType: "pipeline" | "email_template" | "ai_settings"
    versions: VersionItem[]
    currentVersion: number
    isLoading?: boolean
    onRollback?: (version: number) => void
    isRollingBack?: boolean
    canRollback?: boolean  // Developer-only feature
}

export function VersionHistoryModal({
    open,
    onOpenChange,
    title,
    entityType,
    versions,
    currentVersion,
    isLoading,
    onRollback,
    isRollingBack,
    canRollback = false,
}: VersionHistoryModalProps) {
    const [expandedVersion, setExpandedVersion] = useState<number | null>(null)

    const formatDate = (dateStr: string) => {
        try {
            return format(new Date(dateStr), "MMM d, yyyy 'at' h:mm a")
        } catch {
            return dateStr
        }
    }

    const toggleExpanded = (version: number) => {
        setExpandedVersion(expandedVersion === version ? null : version)
    }

    const renderPayloadPreview = (payload: Record<string, unknown>) => {
        // Show relevant fields based on entity type
        if (entityType === "pipeline") {
            const stages = (payload.stages as Array<{ label: string }>) || []
            return `${stages.length} stages: ${stages.map(s => s.label).join(", ")}`
        }
        if (entityType === "email_template") {
            return `Subject: ${payload.subject || "(empty)"}`
        }
        return JSON.stringify(payload).slice(0, 100) + "..."
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <History className="h-5 w-5" />
                        Version History
                    </DialogTitle>
                    <DialogDescription>
                        {title} — Current version: {currentVersion}
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                    </div>
                ) : versions.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        No version history available
                    </div>
                ) : (
                    <ScrollArea className="max-h-[400px] pr-4">
                        <div className="space-y-3">
                            {versions.map((v) => (
                                <div
                                    key={v.id}
                                    className={`border rounded-lg p-3 ${v.version === currentVersion
                                        ? "border-primary bg-primary/5"
                                        : "border-border"
                                        }`}
                                >
                                    {/* Version header */}
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Badge
                                                variant={v.version === currentVersion ? "default" : "secondary"}
                                            >
                                                v{v.version}
                                            </Badge>
                                            {v.version === currentVersion && (
                                                <span className="text-xs text-muted-foreground">current</span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => toggleExpanded(v.version)}
                                            >
                                                {expandedVersion === v.version ? (
                                                    <ChevronUp className="h-4 w-4" />
                                                ) : (
                                                    <ChevronDown className="h-4 w-4" />
                                                )}
                                            </Button>
                                            {canRollback && v.version !== currentVersion && onRollback && (
                                                <AlertDialog>
                                                    <AlertDialogTrigger>
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            disabled={isRollingBack}
                                                        >
                                                            <RotateCcw className="h-3 w-3 mr-1" />
                                                            Rollback
                                                        </Button>
                                                    </AlertDialogTrigger>
                                                    <AlertDialogContent>
                                                        <AlertDialogHeader>
                                                            <AlertDialogTitle>Rollback to v{v.version}?</AlertDialogTitle>
                                                            <AlertDialogDescription>
                                                                This will create a new version with the configuration from v{v.version}.
                                                                History is never rewritten — you can always roll forward again.
                                                            </AlertDialogDescription>
                                                        </AlertDialogHeader>
                                                        <AlertDialogFooter>
                                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                            <AlertDialogAction
                                                                onClick={() => onRollback(v.version)}
                                                                disabled={isRollingBack}
                                                            >
                                                                {isRollingBack ? "Rolling back..." : "Confirm Rollback"}
                                                            </AlertDialogAction>
                                                        </AlertDialogFooter>
                                                    </AlertDialogContent>
                                                </AlertDialog>
                                            )}
                                        </div>
                                    </div>

                                    {/* Version metadata */}
                                    <div className="mt-2 text-sm text-muted-foreground space-y-1">
                                        <div className="flex items-center gap-1">
                                            <Calendar className="h-3 w-3" />
                                            {formatDate(v.created_at)}
                                        </div>
                                        {v.comment && (
                                            <div className="flex items-center gap-1">
                                                <MessageSquare className="h-3 w-3" />
                                                {v.comment}
                                            </div>
                                        )}
                                    </div>

                                    {/* Expanded payload view */}
                                    {expandedVersion === v.version && (
                                        <div className="mt-3 pt-3 border-t">
                                            <div className="text-xs font-mono bg-muted p-2 rounded overflow-auto max-h-[200px]">
                                                <pre>{JSON.stringify(v.payload, null, 2)}</pre>
                                            </div>
                                        </div>
                                    )}

                                    {/* Collapsed preview */}
                                    {expandedVersion !== v.version && (
                                        <div className="mt-2 text-xs text-muted-foreground truncate">
                                            {renderPayloadPreview(v.payload)}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                )}
            </DialogContent>
        </Dialog>
    )
}
