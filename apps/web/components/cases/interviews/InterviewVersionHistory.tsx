"use client"

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Label } from "@/components/ui/label"
import {
    HistoryIcon,
    MoreVerticalIcon,
    RotateCcwIcon,
    GitCompareIcon,
    Loader2Icon,
    ClockIcon,
    UserIcon,
    FileTextIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatDistanceToNow } from "date-fns"
import {
    useInterviewVersions,
    useInterviewVersionDiff,
    useRestoreInterviewVersion,
} from "@/lib/hooks/use-interviews"
import type { InterviewVersionListItem } from "@/lib/api/interviews"
import { toast } from "sonner"

interface InterviewVersionHistoryProps {
    interviewId: string
    currentVersion: number
    open: boolean
    onOpenChange: (open: boolean) => void
    canRestore: boolean
}

// Format file size
function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Format source label
function formatSource(source: string): string {
    const labels: Record<string, string> = {
        manual: "Manual Edit",
        ai_transcription: "AI Transcription",
        restore: "Restored",
    }
    return labels[source] || source
}

export function InterviewVersionHistory({
    interviewId,
    currentVersion,
    open,
    onOpenChange,
    canRestore,
}: InterviewVersionHistoryProps) {
    const [diffDialogOpen, setDiffDialogOpen] = React.useState(false)
    const [diffVersions, setDiffVersions] = React.useState<{ v1: number; v2: number } | null>(null)
    const [restoreConfirmOpen, setRestoreConfirmOpen] = React.useState(false)
    const [versionToRestore, setVersionToRestore] = React.useState<number | null>(null)

    const { data: versions, isLoading } = useInterviewVersions(interviewId)
    const restoreMutation = useRestoreInterviewVersion()

    const handleCompare = (v1: number, v2: number) => {
        setDiffVersions({ v1, v2 })
        setDiffDialogOpen(true)
    }

    const handleRestore = async () => {
        if (!versionToRestore) return
        try {
            await restoreMutation.mutateAsync({
                interviewId,
                version: versionToRestore,
            })
            toast.success(`Restored to version ${versionToRestore}`)
            setRestoreConfirmOpen(false)
            setVersionToRestore(null)
            onOpenChange(false)
        } catch {
            toast.error("Failed to restore version")
        }
    }

    return (
        <>
            {/* Main Version History Dialog */}
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <HistoryIcon className="h-5 w-5" />
                            Version History
                        </DialogTitle>
                    </DialogHeader>

                    <div className="flex-1 overflow-auto -mx-6 px-6">
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !versions || versions.length === 0 ? (
                            <div className="text-center py-12">
                                <FileTextIcon className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
                                <p className="text-muted-foreground">No version history available</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {versions.map((version, idx) => (
                                    <VersionItem
                                        key={version.version}
                                        version={version}
                                        isCurrent={version.version === currentVersion}
                                        isLatest={idx === 0}
                                        previousVersion={idx < versions.length - 1 ? versions[idx + 1].version : null}
                                        canRestore={canRestore && version.version !== currentVersion}
                                        onCompare={(v1, v2) => handleCompare(v1, v2)}
                                        onRestore={(v) => {
                                            setVersionToRestore(v)
                                            setRestoreConfirmOpen(true)
                                        }}
                                    />
                                ))}
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Diff View Dialog */}
            {diffVersions && (
                <VersionDiffDialog
                    interviewId={interviewId}
                    v1={diffVersions.v1}
                    v2={diffVersions.v2}
                    open={diffDialogOpen}
                    onOpenChange={setDiffDialogOpen}
                    versions={versions || []}
                    onVersionChange={setDiffVersions}
                />
            )}

            {/* Restore Confirmation Dialog */}
            <Dialog open={restoreConfirmOpen} onOpenChange={setRestoreConfirmOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Restore Version {versionToRestore}?</DialogTitle>
                    </DialogHeader>
                    <p className="text-sm text-muted-foreground">
                        This will create a new version with the content from version {versionToRestore}.
                        The current version will be preserved in the history.
                    </p>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRestoreConfirmOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleRestore}
                            disabled={restoreMutation.isPending}
                        >
                            {restoreMutation.isPending ? (
                                <>
                                    <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                                    Restoring...
                                </>
                            ) : (
                                <>
                                    <RotateCcwIcon className="h-4 w-4 mr-2" />
                                    Restore
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}

// ============================================================================
// Sub-components
// ============================================================================

interface VersionItemProps {
    version: InterviewVersionListItem
    isCurrent: boolean
    isLatest: boolean
    previousVersion: number | null
    canRestore: boolean
    onCompare: (v1: number, v2: number) => void
    onRestore: (version: number) => void
}

function VersionItem({
    version,
    isCurrent,
    isLatest,
    previousVersion,
    canRestore,
    onCompare,
    onRestore,
}: VersionItemProps) {
    return (
        <div
            className={cn(
                "p-4 rounded-lg border transition-colors",
                isCurrent ? "bg-primary/5 border-primary/20" : "bg-card hover:bg-muted/50"
            )}
        >
            <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">Version {version.version}</span>
                        {isCurrent && (
                            <Badge variant="default" className="text-xs">
                                Current
                            </Badge>
                        )}
                        {isLatest && !isCurrent && (
                            <Badge variant="secondary" className="text-xs">
                                Latest
                            </Badge>
                        )}
                        <Badge variant="outline" className="text-xs">
                            {formatSource(version.source)}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <UserIcon className="h-3 w-3" />
                            {version.author_name}
                        </span>
                        <span className="flex items-center gap-1">
                            <ClockIcon className="h-3 w-3" />
                            {formatDistanceToNow(new Date(version.created_at), { addSuffix: true })}
                        </span>
                        <span>{formatBytes(version.content_size_bytes)}</span>
                    </div>
                </div>

                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVerticalIcon className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        {previousVersion && (
                            <DropdownMenuItem onClick={() => onCompare(previousVersion, version.version)}>
                                <GitCompareIcon className="h-4 w-4 mr-2" />
                                Compare with v{previousVersion}
                            </DropdownMenuItem>
                        )}
                        {canRestore && (
                            <DropdownMenuItem onClick={() => onRestore(version.version)}>
                                <RotateCcwIcon className="h-4 w-4 mr-2" />
                                Restore this version
                            </DropdownMenuItem>
                        )}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    )
}

interface VersionDiffDialogProps {
    interviewId: string
    v1: number
    v2: number
    open: boolean
    onOpenChange: (open: boolean) => void
    versions: InterviewVersionListItem[]
    onVersionChange: (versions: { v1: number; v2: number }) => void
}

function VersionDiffDialog({
    interviewId,
    v1,
    v2,
    open,
    onOpenChange,
    versions,
    onVersionChange,
}: VersionDiffDialogProps) {
    const { data: diff, isLoading } = useInterviewVersionDiff(interviewId, v1, v2)

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <GitCompareIcon className="h-5 w-5" />
                        Compare Versions
                    </DialogTitle>
                </DialogHeader>

                {/* Version Selectors */}
                <div className="flex items-center gap-4 py-2">
                    <div className="flex items-center gap-2">
                        <Label htmlFor="v1-select" className="text-sm">From:</Label>
                        <NativeSelect
                            id="v1-select"
                            value={v1.toString()}
                            onChange={(e) => onVersionChange({ v1: parseInt(e.target.value), v2 })}
                            className="w-32"
                        >
                            {versions.map((v) => (
                                <NativeSelectOption key={v.version} value={v.version.toString()}>
                                    Version {v.version}
                                </NativeSelectOption>
                            ))}
                        </NativeSelect>
                    </div>
                    <div className="flex items-center gap-2">
                        <Label htmlFor="v2-select" className="text-sm">To:</Label>
                        <NativeSelect
                            id="v2-select"
                            value={v2.toString()}
                            onChange={(e) => onVersionChange({ v1, v2: parseInt(e.target.value) })}
                            className="w-32"
                        >
                            {versions.map((v) => (
                                <NativeSelectOption key={v.version} value={v.version.toString()}>
                                    Version {v.version}
                                </NativeSelectOption>
                            ))}
                        </NativeSelect>
                    </div>
                    {diff && (
                        <div className="flex items-center gap-3 ml-auto text-sm">
                            <span className="text-green-600">+{diff.additions} additions</span>
                            <span className="text-red-600">-{diff.deletions} deletions</span>
                        </div>
                    )}
                </div>

                {/* Diff Content */}
                <div className="flex-1 overflow-auto border rounded-lg bg-muted/30 p-4">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : diff ? (
                        <div
                            className="prose prose-sm max-w-none dark:prose-invert font-mono text-sm whitespace-pre-wrap"
                            dangerouslySetInnerHTML={{ __html: diff.diff_html }}
                        />
                    ) : (
                        <p className="text-muted-foreground text-center py-8">
                            Unable to generate diff
                        </p>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// CSS for diff highlighting (add to globals.css or inline styles)
// .diff-add { background-color: rgb(187 247 208 / 0.5); } /* green-200/50 */
// .diff-del { background-color: rgb(254 202 202 / 0.5); } /* red-200/50 */
