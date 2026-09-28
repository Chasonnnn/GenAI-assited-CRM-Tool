"use client"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    useSurrogateDetailActions,
    useSurrogateDetailData,
    useSurrogateDetailDialogs,
    useSurrogateDetailQueue,
} from "../context"

const QUEUE_PLACEHOLDER = "Select a queue\u2026"

function formatQueueLabel(value: string | null, queues: { id: string; name: string }[]) {
    if (!value) return QUEUE_PLACEHOLDER
    return queues.find((queue) => queue.id === value)?.name ?? "Unknown queue"
}

export function ReleaseQueueDialog() {
    const { queues } = useSurrogateDetailData()
    const {
        activeDialog,
        closeDialog,
    } = useSurrogateDetailDialogs()
    const {
        selectedQueueId,
        setSelectedQueueId,
    } = useSurrogateDetailQueue()
    const {
        releaseSurrogate,
        isReleasePending,
    } = useSurrogateDetailActions()

    const isOpen = activeDialog.type === "release_queue"

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Release to Queue</DialogTitle>
                </DialogHeader>
                <div className="py-4">
                    <Label htmlFor="queue-select">Select Queue</Label>
                    <Select
                        value={selectedQueueId || null}
                        onValueChange={(value) => setSelectedQueueId(value ?? "")}
                    >
                        <SelectTrigger id="queue-select" className="mt-2">
                            <SelectValue placeholder={QUEUE_PLACEHOLDER}>
                                {(value: string | null) => formatQueueLabel(value, queues)}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectGroup>
                                {queues.map((queue) => (
                                    <SelectItem key={queue.id} value={queue.id}>
                                        {queue.name}
                                    </SelectItem>
                                ))}
                            </SelectGroup>
                        </SelectContent>
                    </Select>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={closeDialog}>Cancel</Button>
                    <Button
                        onClick={releaseSurrogate}
                        disabled={!selectedQueueId || isReleasePending}
                    >
                        {isReleasePending ? "Releasing\u2026" : "Release"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
