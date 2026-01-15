"use client"

/**
 * UploadFileDialog - Dialog for uploading files to Surrogate or IP from Match detail page
 */

import { useState, useRef } from "react"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { UploadIcon, FileIcon, XIcon } from "lucide-react"

interface UploadFileDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onUpload: (target: "surrogate" | "ip", file: File) => Promise<void>
    isPending: boolean
    surrogateName: string
    ipName: string
}

export function UploadFileDialog({
    open,
    onOpenChange,
    onUpload,
    isPending,
    surrogateName,
    ipName,
}: UploadFileDialogProps) {
    const [target, setTarget] = useState<"surrogate" | "ip">("surrogate")
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const handleSubmit = async () => {
        if (!selectedFile) return

        await onUpload(target, selectedFile)
        setSelectedFile(null)
        setTarget("surrogate")
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
            setTarget("surrogate")
        }
        onOpenChange(isOpen)
    }

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Upload File</DialogTitle>
                    <DialogDescription>
                        Upload a file to the Surrogate or Intended Parent record.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Target selection */}
                    <div className="space-y-2">
                        <Label>Upload to</Label>
                        <RadioGroup
                            value={target}
                            onValueChange={(v) => setTarget(v as "surrogate" | "ip")}
                            className="flex gap-4"
                        >
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="surrogate" id="target-surrogate" />
                                <Label htmlFor="target-surrogate" className="font-normal cursor-pointer">
                                    {surrogateName} (Surrogate)
                                </Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="ip" id="target-ip" />
                                <Label htmlFor="target-ip" className="font-normal cursor-pointer">
                                    {ipName} (IP)
                                </Label>
                            </div>
                        </RadioGroup>
                    </div>

                    {/* File selection */}
                    <div className="space-y-2">
                        <Label>File</Label>
                        <input
                            type="file"
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
                        {isPending ? "Uploading..." : "Upload"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
