"use client"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { useInterviewTab } from "./context"

export function DeleteDialog() {
    const { dialog, closeDialog, deleteInterview, isDeletePending } = useInterviewTab()

    const isOpen = dialog.type === "delete"

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete Interview</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-muted-foreground">
                    Are you sure you want to delete this interview? This action cannot be undone.
                </p>
                <DialogFooter>
                    <Button variant="outline" onClick={closeDialog}>
                        Cancel
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={deleteInterview}
                        disabled={isDeletePending}
                    >
                        {isDeletePending ? "Deleting..." : "Delete"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
