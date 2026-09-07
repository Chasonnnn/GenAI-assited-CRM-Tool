"use client"

/**
 * UploadFileDialog - Dialog for uploading files to Surrogate or IP from Match detail page
 */

import type { MatchWorkSource } from "@/lib/api/matches"
import { useState, useRef, useId } from "react"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { UploadIcon, FileIcon, XIcon, Loader2Icon } from "lucide-react"

interface UploadFileDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onUpload: (target: MatchWorkSource, file: File) => Promise<void>
    isPending: boolean
    surrogateName: string
    participantKind?: "surrogate" | "donor"
    ipName: string
}

function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadFileDialog({
    open,
    onOpenChange,
    onUpload,
    isPending,
    surrogateName,
    participantKind = "surrogate",
    ipName,
}: UploadFileDialogProps) {
    const [target, setTarget] = useState<MatchWorkSource>("match")
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const fileInputId = useId()

    const handleSubmit = async () => {
        if (!selectedFile) return

        try { await onUpload(target, selectedFile) } catch { return }
        setSelectedFile(null)
        setTarget("match")
        onOpenChange(false)
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            setSelectedFile(file)
        }
    }

    const handleClearFile = () => {
        setSelectedFile(null)
        if (fileInputRef.current) {
            fileInputRef.current.value = ""
        }
    }

    const handleClose = (isOpen: boolean) => {
        if (!isOpen) {
            setSelectedFile(null)
            setTarget("match")
        }
        onOpenChange(isOpen)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Upload File</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Target selection */}
                    <div className="space-y-2">
                        <Label>Related to</Label>
                        <RadioGroup
                            value={target}
                            onValueChange={(v) => setTarget(v as MatchWorkSource)}
                            className="flex flex-col gap-3"
                        >
                            <div className="flex items-center gap-2">
                                <RadioGroupItem value="match" id="target-match" />
                                <Label htmlFor="target-match" className="font-normal cursor-pointer">Match</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <RadioGroupItem value={participantKind} id="target-surrogate" />
                                <Label htmlFor="target-surrogate" className="font-normal cursor-pointer">
                                    {surrogateName} ({participantKind === "donor" ? "Donor" : "Surrogate"})
                                </Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <RadioGroupItem value="ip" id="target-ip" />
                                <Label htmlFor="target-ip" className="font-normal cursor-pointer">
                                    {ipName} (IP)
                                </Label>
                            </div>
                        </RadioGroup>
                    </div>

                    {/* File selection */}
                    <div className="space-y-2">
                        <Label htmlFor={fileInputId}>File</Label>
                        <input
                            id={fileInputId}
                            name="match_upload_file"
                            type="file"
                            aria-label="Upload match file"
                            ref={fileInputRef}
                            onChange={handleFileSelect}
                            className="hidden"
                            accept="*/*"
                        />

                        {selectedFile ? (
                            <div className="flex items-center gap-2 p-3 border rounded-md bg-muted/50">
                                <FileIcon className="size-5 text-muted-foreground flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {formatFileSize(selectedFile.size)}
                                    </p>
                                </div>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleClearFile}
                                    aria-label={`Remove selected file ${selectedFile.name}`}
                                    className="flex-shrink-0"
                                >
                                    <XIcon className="size-4" />
                                </Button>
                            </div>
                        ) : (
                            <Button
                                type="button"
                                variant="outline"
                                className="w-full"
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <UploadIcon className="size-4 mr-2" />
                                Choose File
                            </Button>
                        )}
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => handleClose(false)}
                        disabled={isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={isPending || !selectedFile}
                    >
                        {isPending ? (
                            <>
                                <Loader2Icon
                                    className="mr-2 size-4 animate-spin"
                                    aria-hidden="true"
                                />
                                Uploading...
                            </>
                        ) : (
                            "Upload"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
