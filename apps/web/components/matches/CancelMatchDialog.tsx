"use client"

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
import { Loader2Icon } from "lucide-react"

interface CancelMatchDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onConfirm: (reason?: string) => Promise<void>
    isPending?: boolean
}

export function CancelMatchDialog({
    open,
    onOpenChange,
    onConfirm,
    isPending = false,
}: CancelMatchDialogProps) {
    const [reason, setReason] = useState("")

    const handleConfirm = async () => {
        const trimmed = reason.trim()
        await onConfirm(trimmed ? trimmed : undefined)
        setReason("")
        onOpenChange(false)
    }

    const handleOpenChange = (isOpen: boolean) => {
        if (!isOpen) {
            setReason("")
        }
        onOpenChange(isOpen)
    }

    const handleCancel = () => {
        setReason("")
        onOpenChange(false)
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Cancel Match</DialogTitle>
                    <DialogDescription>
                        This will request admin approval to cancel the match and return both records
                        to Ready to Match.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="reason">Reason (optional)</Label>
                        <Textarea
                            id="reason"
                            placeholder="Why are you cancelling this match?"
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            rows={4}
                            className="resize-none"
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={handleCancel} disabled={isPending}>
                        Back
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={handleConfirm}
                        disabled={isPending}
                    >
                        {isPending ? (
                            <>
                                <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                                Requesting...
                            </>
                        ) : (
                            "Request Cancellation"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
