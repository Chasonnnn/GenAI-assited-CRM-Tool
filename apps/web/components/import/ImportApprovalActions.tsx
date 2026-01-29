"use client"

/**
 * ImportApprovalActions - Approve/Reject buttons for CSV import approvals.
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { CheckIcon, XIcon, Loader2Icon, PlayIcon } from "lucide-react"
import { useApproveImport, useRejectImport, useRunImportInline } from "@/lib/hooks/use-import"

interface ImportApprovalActionsProps {
    importId: string
    disabled?: boolean
    onResolved?: () => void
}

export function ImportApprovalActions({
    importId,
    disabled = false,
    onResolved,
}: ImportApprovalActionsProps) {
    const [showRejectDialog, setShowRejectDialog] = useState(false)
    const [rejectReason, setRejectReason] = useState("")
    const [rejectError, setRejectError] = useState<string | null>(null)

    const approveImport = useApproveImport()
    const rejectImport = useRejectImport()
    const runInlineImport = useRunImportInline()

    const handleApprove = async () => {
        await approveImport.mutateAsync(importId)
        onResolved?.()
    }

    const handleApproveAndRun = async () => {
        await approveImport.mutateAsync(importId)
        await runInlineImport.mutateAsync(importId)
        onResolved?.()
    }

    const handleReject = async () => {
        const trimmedReason = rejectReason.trim()
        if (!trimmedReason) {
            setRejectError("Rejection reason is required.")
            return
        }
        await rejectImport.mutateAsync({ importId, reason: trimmedReason })
        setShowRejectDialog(false)
        setRejectReason("")
        setRejectError(null)
        onResolved?.()
    }

    const isPending = approveImport.isPending || rejectImport.isPending || runInlineImport.isPending

    return (
        <>
            <div className="flex w-full gap-2 sm:w-auto">
                <Button
                    size="sm"
                    variant="default"
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 sm:flex-none"
                    onClick={handleApprove}
                    disabled={disabled || isPending}
                >
                    {approveImport.isPending ? (
                        <Loader2Icon className="mr-1 size-4 animate-spin" />
                    ) : (
                        <CheckIcon className="mr-1 size-4" />
                    )}
                    Approve
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 sm:flex-none"
                    onClick={handleApproveAndRun}
                    disabled={disabled || isPending}
                >
                    {runInlineImport.isPending ? (
                        <Loader2Icon className="mr-1 size-4 animate-spin" />
                    ) : (
                        <PlayIcon className="mr-1 size-4" />
                    )}
                    Run now
                </Button>
                <Button
                    size="sm"
                    variant="destructive"
                    className="flex-1 sm:flex-none"
                    onClick={() => setShowRejectDialog(true)}
                    disabled={disabled || isPending}
                >
                    <XIcon className="mr-1 size-4" />
                    Reject
                </Button>
            </div>

            <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Reject Import</DialogTitle>
                        <DialogDescription>
                            Rejected imports are not processed. Provide a reason for audit visibility.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-2">
                        <Label htmlFor="import-reject-reason">Reason *</Label>
                        <Textarea
                            id="import-reject-reason"
                            placeholder="Why are you rejecting this import?"
                            value={rejectReason}
                            onChange={(e) => {
                                setRejectReason(e.target.value)
                                setRejectError(null)
                            }}
                            className="mt-1.5"
                            rows={3}
                        />
                        {rejectError && (
                            <p className="text-sm text-destructive">{rejectError}</p>
                        )}
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setShowRejectDialog(false)}
                            disabled={isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleReject}
                            disabled={isPending}
                        >
                            {rejectImport.isPending && (
                                <Loader2Icon className="mr-1 size-4 animate-spin" />
                            )}
                            Reject
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}
