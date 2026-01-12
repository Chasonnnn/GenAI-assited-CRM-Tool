"use client"

/**
 * ApprovalTaskActions - Approve/Deny buttons for workflow approval tasks.
 *
 * Only shown to the task owner (case owner). Others see a disabled state.
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
import { useResolveWorkflowApproval } from "@/lib/hooks/use-tasks"

interface ApprovalTaskActionsProps {
    taskId: string
    isOwner: boolean
    disabled?: boolean
    onResolved?: () => void
}

export function ApprovalTaskActions({
    taskId,
    isOwner,
    disabled = false,
    onResolved,
}: ApprovalTaskActionsProps) {
    const [showDenyDialog, setShowDenyDialog] = useState(false)
    const [denyReason, setDenyReason] = useState("")

    const resolveApproval = useResolveWorkflowApproval()

    const handleApprove = async () => {
        await resolveApproval.mutateAsync({
            taskId,
            decision: "approve",
        })
        onResolved?.()
    }

    const handleDeny = async () => {
        await resolveApproval.mutateAsync({
            taskId,
            decision: "deny",
            ...(denyReason.trim() ? { reason: denyReason.trim() } : {}),
        })
        setShowDenyDialog(false)
        setDenyReason("")
        onResolved?.()
    }

    const isPending = resolveApproval.isPending

    if (!isOwner) {
        return (
            <div className="text-sm text-muted-foreground italic">
                Only the case owner can approve or deny
            </div>
        )
    }

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
                    {isPending ? (
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
                    onClick={() => setShowDenyDialog(true)}
                    disabled={disabled || isPending}
                >
                    <XIcon className="mr-1 size-4" />
                    Deny
                </Button>
            </div>

            <Dialog open={showDenyDialog} onOpenChange={setShowDenyDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Deny Workflow Action</DialogTitle>
                        <DialogDescription>
                            This will cancel the workflow. Optionally provide a reason.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <Label htmlFor="deny-reason">Reason (optional)</Label>
                        <Textarea
                            id="deny-reason"
                            placeholder="Why are you denying this action?"
                            value={denyReason}
                            onChange={(e) => setDenyReason(e.target.value)}
                            className="mt-1.5"
                            rows={3}
                        />
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setShowDenyDialog(false)}
                            disabled={isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleDeny}
                            disabled={isPending}
                        >
                            {isPending && <Loader2Icon className="mr-1 size-4 animate-spin" />}
                            Deny
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}
