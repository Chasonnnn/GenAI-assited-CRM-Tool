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
    onSubmit: (target: "case" | "ip", content: string) => Promise<void>
    isPending?: boolean
    caseName?: string
    ipName?: string
}

export function AddNoteDialog({
    open,
    onOpenChange,
    onSubmit,
    isPending = false,
    caseName = "Surrogate Case",
    ipName = "Intended Parent",
}: AddNoteDialogProps) {
    const [target, setTarget] = useState<"case" | "ip">("case")
    const [content, setContent] = useState("")

    const handleSubmit = async () => {
        if (!content.trim()) return
        await onSubmit(target, content.trim())
        setContent("")
        setTarget("case")
        onOpenChange(false)
    }

    const handleCancel = () => {
        setContent("")
        setTarget("case")
        onOpenChange(false)
    }

    const handleOpenChange = (isOpen: boolean) => {
        if (!isOpen) {
            setContent("")
            setTarget("case")
        }
        onOpenChange(isOpen)
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Add Note</DialogTitle>
                    <DialogDescription>
                        Add a note to the case or intended parent record.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="target">Add note to</Label>
                        <Select value={target} onValueChange={(v) => setTarget(v as "case" | "ip")}>
                            <SelectTrigger id="target">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="case">{caseName}</SelectItem>
                                <SelectItem value="ip">{ipName}</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="content">Note Content</Label>
                        <Textarea
                            id="content"
                            placeholder="Enter your note..."
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
                                <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                                Saving...
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
