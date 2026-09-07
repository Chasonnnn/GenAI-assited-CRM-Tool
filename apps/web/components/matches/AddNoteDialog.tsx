"use client"

import type { MatchWorkSource } from "@/lib/api/matches"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Loader2Icon } from "lucide-react"

interface AddNoteDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSubmit: (target: MatchWorkSource, content: string) => Promise<void>
    isPending?: boolean
    surrogateName?: string
    participantKind?: "surrogate" | "donor"
    ipName?: string
}

export function AddNoteDialog({
    open,
    onOpenChange,
    onSubmit,
    isPending = false,
    surrogateName = "Surrogate",
    participantKind = "surrogate",
    ipName = "Intended Parent",
}: AddNoteDialogProps) {
    const [target, setTarget] = useState<MatchWorkSource>("match")
    const [content, setContent] = useState("")

    const handleSubmit = async () => {
        if (!content.trim()) return
        try { await onSubmit(target, content.trim()) } catch { return }
        setContent("")
        setTarget("match")
        onOpenChange(false)
    }

    const handleCancel = () => {
        setContent("")
        setTarget("match")
        onOpenChange(false)
    }

    const handleOpenChange = (isOpen: boolean) => {
        if (!isOpen) {
            setContent("")
            setTarget("match")
        }
        onOpenChange(isOpen)
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Add Note</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="target">Related to</Label>
                        <Select value={target} onValueChange={(v) => setTarget(v as MatchWorkSource)}>
                            <SelectTrigger id="target">
                                <SelectValue>{(value: string | null) => value === "match" ? "Match" : value === "ip" ? ipName : surrogateName}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="match">Match</SelectItem>
                                <SelectItem value={participantKind}>{surrogateName}</SelectItem>
                                <SelectItem value="ip">{ipName}</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="content">Note Content</Label>
                        <Textarea
                            id="content"
                            placeholder="Enter your note"
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            rows={5}
                            className="resize-none"
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={handleCancel} disabled={isPending}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!content.trim() || isPending}
                    >
                        {isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                Saving
                            </>
                        ) : (
                            "Add Note"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
