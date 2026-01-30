"use client"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { useSurrogateDetailLayout } from "../context"

export function ReleaseQueueDialog() {
    const {
        activeDialog,
        closeDialog,
        queues,
        selectedQueueId,
        setSelectedQueueId,
        releaseSurrogate,
        isReleasePending,
    } = useSurrogateDetailLayout()

    const isOpen = activeDialog.type === "release_queue"

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Release to Queue</DialogTitle>
                </DialogHeader>
                <div className="py-4">
                    <Label htmlFor="queue-select">Select Queue</Label>
                    <select
                        id="queue-select"
                        value={selectedQueueId}
                        onChange={(event) => setSelectedQueueId(event.target.value)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mt-2"
                    >
                        <option value="">Select a queue...</option>
                        {queues.map((queue) => (
                            <option key={queue.id} value={queue.id}>
                                {queue.name}
                            </option>
                        ))}
                    </select>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={closeDialog}>Cancel</Button>
                    <Button
                        onClick={releaseSurrogate}
                        disabled={!selectedQueueId || isReleasePending}
                    >
                        {isReleasePending ? "Releasing..." : "Release"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
