"use client"

/**
 * StatusChangeRequestActions - Approve/Reject buttons for status change requests.
 *
 * Only shown to admins who can approve/reject regression requests.
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
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { CheckIcon, XIcon, Loader2Icon } from "lucide-react"
import {
    useApproveStatusChangeRequest,
    useRejectStatusChangeRequest,
} from "@/lib/hooks/use-status-change-requests"

interface StatusChangeRequestActionsProps {
    requestId: string
    disabled?: boolean
    onResolved?: () => void
}

export function StatusChangeRequestActions({
    requestId,
    disabled = false,
    onResolved,
}: StatusChangeRequestActionsProps) {
    const [showRejectDialog, setShowRejectDialog] = useState(false)
    const [rejectReason, setRejectReason] = useState("")

    const approveRequest = useApproveStatusChangeRequest()
    const rejectRequest = useRejectStatusChangeRequest()

    const handleApprove = async () => {
        await approveRequest.mutateAsync(requestId)
        onResolved?.()
    }

    const handleReject = async () => {
        const payload: { requestId: string; reason?: string } = { requestId }
        const trimmedReason = rejectReason.trim()
        if (trimmedReason) payload.reason = trimmedReason
        await rejectRequest.mutateAsync(payload)
        setShowRejectDialog(false)
        setRejectReason("")
        onResolved?.()
    }

    const isPending = approveRequest.isPending || rejectRequest.isPending

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
                    {approveRequest.isPending ? (
                        <Loader2Icon className="mr-1 size-4 animate-spin" />
                    ) : (
                        <CheckIcon className="mr-1 size-4" />
                    )}
                    Approve
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
                        <DialogTitle>Reject Status Change Request</DialogTitle>
                        <DialogDescription>
                            This will reject the request. The record will remain in its current status.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <Label htmlFor="reject-reason">Reason (optional)</Label>
                        <Textarea
                            id="reject-reason"
                            placeholder="Why are you rejecting this request?"
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            className="mt-1.5"
                            rows={3}
                        />
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
                            {rejectRequest.isPending && (
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
