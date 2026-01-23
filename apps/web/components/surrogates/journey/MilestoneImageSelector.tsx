"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckIcon, ImageOffIcon, Loader2Icon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { useAttachmentDownloadUrl, useImageAttachments } from "@/lib/hooks/use-attachments"
import { useUpdateMilestoneFeaturedImage } from "@/lib/hooks/use-journey"
import type { Attachment } from "@/lib/api/attachments"

interface MilestoneImageSelectorProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateId: string
    milestoneSlug: string
    milestoneLabel: string
    currentAttachmentId: string | null
}

export function MilestoneImageSelector({
    open,
    onOpenChange,
    surrogateId,
    milestoneSlug,
    milestoneLabel,
    currentAttachmentId,
}: MilestoneImageSelectorProps) {
    const [selectedId, setSelectedId] = useState<string | null>(currentAttachmentId)
    const { data: attachments, isLoading } = useImageAttachments(surrogateId)
    const downloadMutation = useAttachmentDownloadUrl()
    const updateMutation = useUpdateMilestoneFeaturedImage(surrogateId)

    // Track which images have loaded their signed URLs
    const [imageUrls, setImageUrls] = useState<Record<string, string>>({})
    const [loadingUrls, setLoadingUrls] = useState<Set<string>>(new Set())

    const loadImageUrl = useCallback(async (attachment: Attachment) => {
        if (imageUrls[attachment.id] || loadingUrls.has(attachment.id)) return

        setLoadingUrls((prev) => new Set([...prev, attachment.id]))
        try {
            const result = await downloadMutation.mutateAsync(attachment.id)
            setImageUrls((prev) => ({ ...prev, [attachment.id]: result.download_url }))
        } catch {
            // Silently fail - will show placeholder
        } finally {
            setLoadingUrls((prev) => {
                const next = new Set(prev)
                next.delete(attachment.id)
                return next
            })
        }
    }, [downloadMutation, imageUrls, loadingUrls])

    useEffect(() => {
        if (!attachments || attachments.length === 0) return
        attachments.forEach((attachment) => {
            if (!imageUrls[attachment.id] && !loadingUrls.has(attachment.id)) {
                loadImageUrl(attachment)
            }
        })
    }, [attachments, imageUrls, loadingUrls, loadImageUrl])

    useEffect(() => {
        if (open) {
            setSelectedId(currentAttachmentId)
        }
    }, [open, currentAttachmentId])

    const handleSave = async () => {
        try {
            await updateMutation.mutateAsync({
                milestoneSlug,
                attachmentId: selectedId,
            })
            toast.success(
                selectedId ? "Image updated" : "Image cleared",
                { description: `${milestoneLabel} featured image has been ${selectedId ? "updated" : "reset to default"}.` }
            )
            onOpenChange(false)
        } catch (error: unknown) {
            const message =
                error instanceof Error
                    ? error.message
                    : typeof error === "string"
                        ? error
                        : "Please try again."
            toast.error("Failed to update image", {
                description: message,
            })
        }
    }

    const hasChanges = selectedId !== currentAttachmentId

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Select Featured Image</DialogTitle>
                    <DialogDescription>
                        Choose an image from {milestoneLabel} milestone, or use the default.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    {/* Default option */}
                    <button
                        type="button"
                        onClick={() => setSelectedId(null)}
                        className={cn(
                            "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                            selectedId === null
                                ? "border-primary bg-primary/5"
                                : "border-border hover:border-primary/50 hover:bg-muted/50"
                        )}
                    >
                        <div className="flex size-10 items-center justify-center rounded-md bg-stone-100 dark:bg-stone-800">
                            <ImageOffIcon className="size-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1">
                            <p className="text-sm font-medium">Use Default Image</p>
                            <p className="text-xs text-muted-foreground">
                                Display the standard milestone illustration
                            </p>
                        </div>
                        {selectedId === null && (
                            <CheckIcon className="size-5 text-primary" />
                        )}
                    </button>

                    {/* Image grid */}
                    {isLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : attachments && attachments.length > 0 ? (
                        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
                            {attachments.map((attachment) => {
                                const url = imageUrls[attachment.id]
                                const isSelected = selectedId === attachment.id
                                const isLoading = loadingUrls.has(attachment.id)

                                // Load URL when component mounts
                                if (!url && !isLoading) {
                                    loadImageUrl(attachment)
                                }

                                return (
                                    <button
                                        key={attachment.id}
                                        type="button"
                                        onClick={() => setSelectedId(attachment.id)}
                                        className={cn(
                                            "group relative aspect-square overflow-hidden rounded-lg border-2 transition-all",
                                            isSelected
                                                ? "border-primary ring-2 ring-primary/20"
                                                : "border-transparent hover:border-primary/50"
                                        )}
                                    >
                                        {isLoading || !url ? (
                                            <div className="flex size-full items-center justify-center bg-stone-100 dark:bg-stone-800">
                                                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                                            </div>
                                        ) : (
                                            <img
                                                src={url}
                                                alt={attachment.filename}
                                                className="size-full object-cover"
                                            />
                                        )}
                                        {isSelected && (
                                            <div className="absolute inset-0 flex items-center justify-center bg-primary/20">
                                                <div className="rounded-full bg-primary p-1">
                                                    <CheckIcon className="size-4 text-primary-foreground" />
                                                </div>
                                            </div>
                                        )}
                                        {/* Filename tooltip on hover */}
                                        <div className="absolute inset-x-0 bottom-0 truncate bg-black/60 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition-opacity group-hover:opacity-100">
                                            {attachment.filename}
                                        </div>
                                    </button>
                                )
                            })}
                        </div>
                    ) : (
                        <div className="rounded-lg border border-dashed py-8 text-center">
                            <ImageOffIcon className="mx-auto size-8 text-muted-foreground/50" />
                            <p className="mt-2 text-sm text-muted-foreground">
                                No images uploaded
                            </p>
                            <p className="text-xs text-muted-foreground/70">
                                Upload images to the surrogate&apos;s attachments to use them here.
                            </p>
                        </div>
                    )}
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-2">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSave}
                        disabled={!hasChanges || updateMutation.isPending}
                    >
                        {updateMutation.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                Saving...
                            </>
                        ) : (
                            "Save"
                        )}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}
