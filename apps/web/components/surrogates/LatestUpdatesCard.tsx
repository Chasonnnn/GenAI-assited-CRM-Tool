"use client"

import { useState, useMemo } from "react"
import { FileTextIcon, PaperclipIcon, ArrowRightIcon, Loader2Icon } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useSurrogateHistory } from "@/lib/hooks/use-surrogates"
import { attachmentsApi, Attachment } from "@/lib/api/attachments"
import { NoteRead } from "@/lib/api/notes"
import { sanitizeHtml } from "@/lib/utils/sanitize"
import { openDownloadUrlWithSpreadsheetWarning } from "@/lib/utils/csv-download-warning"

interface LatestUpdatesCardProps {
    surrogateId: string
    notes: NoteRead[] | undefined
    attachments: Attachment[] | undefined
}

function formatRelativeTime(dateString: string): string {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
}

export function LatestUpdatesCard({
    surrogateId,
    notes,
    attachments,
}: LatestUpdatesCardProps) {
    // Get status history for latest stage change (returns array directly)
    const { data: statusHistory } = useSurrogateHistory(surrogateId)
    const [isDownloading, setIsDownloading] = useState(false)

    const latestNote = notes?.[0]  // Already sorted newest first
    const latestAttachment = attachments?.[0]  // Already sorted newest first
    const lastStageChange = statusHistory?.[0]  // Array access

    // Sanitize note HTML (memoized to avoid re-sanitizing on every render)
    const sanitizedNoteHtml = useMemo(() => {
        if (!latestNote?.body) return ''
        return sanitizeHtml(latestNote.body)
    }, [latestNote?.body])

    // Click-to-download: call API directly (no hook that auto-opens)
    const handleAttachmentClick = async (attachmentId: string) => {
        setIsDownloading(true)
        try {
            const { download_url, filename } = await attachmentsApi.getDownloadUrl(attachmentId)
            openDownloadUrlWithSpreadsheetWarning(download_url, filename)
        } finally {
            setIsDownloading(false)
        }
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Latest Updates</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {/* Most Recent Note - render SANITIZED HTML in capped container */}
                {latestNote ? (
                    <div className="flex items-start gap-2">
                        <FileTextIcon className="size-4 text-muted-foreground mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div
                                className="text-sm line-clamp-2 prose prose-sm max-w-none dark:prose-invert"
                                dangerouslySetInnerHTML={{ __html: sanitizedNoteHtml }}
                            />
                            <div className="text-xs text-muted-foreground mt-0.5">
                                {latestNote.author_name} · {formatRelativeTime(latestNote.created_at)}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <FileTextIcon className="size-4" />
                        <span>No notes yet</span>
                    </div>
                )}

                {/* Most Recent File - click to fetch signed URL and open */}
                {latestAttachment ? (
                    <button
                        onClick={() => handleAttachmentClick(latestAttachment.id)}
                        disabled={isDownloading}
                        className="flex items-start gap-2 w-full text-left hover:bg-muted/50 rounded p-1 -m-1 transition-colors"
                        aria-label={`Download ${latestAttachment.filename}`}
                    >
                        <PaperclipIcon className="size-4 text-muted-foreground mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm truncate">{latestAttachment.filename}</div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                                {formatRelativeTime(latestAttachment.created_at)}
                            </div>
                        </div>
                        {isDownloading && (
                            <Loader2Icon className="size-3 animate-spin" />
                        )}
                    </button>
                ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <PaperclipIcon className="size-4" />
                        <span>No files yet</span>
                    </div>
                )}

                {/* Last Stage Change - from SurrogateStatusHistory */}
                {lastStageChange ? (
                    <div className="flex items-start gap-2">
                        <ArrowRightIcon className="size-4 text-muted-foreground mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm">
                                <span className="text-muted-foreground">{lastStageChange.from_label_snapshot}</span>
                                <span className="mx-1">-&gt;</span>
                                <span className="font-medium">{lastStageChange.to_label_snapshot}</span>
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                                {formatRelativeTime(lastStageChange.changed_at)}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <ArrowRightIcon className="size-4" />
                        <span>No stage changes</span>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
