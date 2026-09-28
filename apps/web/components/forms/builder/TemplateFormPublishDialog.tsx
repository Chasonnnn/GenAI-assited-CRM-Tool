"use client"

import { Loader2Icon } from "lucide-react"

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

type TemplateFormPublishDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    onPublish: () => void
    isLoading?: boolean
}

export function TemplateFormPublishDialog({
    open,
    onOpenChange,
    onPublish,
    isLoading = false,
}: TemplateFormPublishDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent size="md">
                <DialogHeader>
                    <DialogTitle>Publish Form Template</DialogTitle>
                    <DialogDescription>
                        Publish this form template to every organization library. Draft edits stay private until you re-publish.
                    </DialogDescription>
                </DialogHeader>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={onPublish} disabled={isLoading}>
                        {isLoading ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                        Publish
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
