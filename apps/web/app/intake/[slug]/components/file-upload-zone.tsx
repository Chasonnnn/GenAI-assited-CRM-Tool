"use client"

import * as React from "react"
import { FileTextIcon, UploadIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { toast } from "@/components/ui/toast"
import { cn } from "@/lib/utils"

function getUploadFileKey(file: File): string {
    return `${file.name}:${file.size}:${file.lastModified}`
}

export function FileUploadZone({
    files,
    onFilesChange,
    maxFiles = 10,
    maxFileSizeBytes,
    allowedMimeTypes,
}: {
    files: File[]
    onFilesChange: (files: File[]) => void
    maxFiles?: number
    maxFileSizeBytes?: number | null
    allowedMimeTypes?: string[] | null
}) {
    const [isDragging, setIsDragging] = React.useState(false)
    const inputRef = React.useRef<HTMLInputElement>(null)
    const inputId = React.useId()

    const maxSizeBytes = maxFileSizeBytes || 10 * 1024 * 1024
    const acceptedTypes = allowedMimeTypes && allowedMimeTypes.length > 0 ? allowedMimeTypes : null

    const isAllowedType = (file: File) => {
        if (!acceptedTypes) return true
        return acceptedTypes.some((type) => {
            if (type.endsWith("/*")) return file.type.startsWith(type.replace("/*", "/"))
            return file.type === type
        })
    }

    const applyFileLimits = (incomingFiles: File[]) => {
        const filteredFiles = incomingFiles.filter((file) => {
            if (!isAllowedType(file)) {
                toast.error(`File type not allowed: ${file.name}`)
                return false
            }
            if (file.size > maxSizeBytes) {
                const maxMb = Math.floor(maxSizeBytes / (1024 * 1024))
                toast.error(`File too large (${file.name}). Max ${maxMb} MB.`)
                return false
            }
            return true
        })
        const combined = [...files, ...filteredFiles]
        if (combined.length > maxFiles) toast.error(`Maximum ${maxFiles} files allowed.`)
        onFilesChange(combined.slice(0, maxFiles))
    }

    return (
        <div className="space-y-3">
            <Button
                unstyled
                type="button"
                onClick={() => inputRef.current?.click()}
                aria-label="Upload files"
                onDrop={(event) => {
                    event.preventDefault()
                    setIsDragging(false)
                    applyFileLimits(Array.from(event.dataTransfer.files))
                }}
                onDragOver={(event) => {
                    event.preventDefault()
                    setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                className={cn(
                    "flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 transition-all",
                    "hover:border-blue-300 hover:bg-sky-50",
                    "focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2",
                    isDragging ? "border-blue-400 bg-sky-50" : "border-stone-300 bg-white",
                )}
            >
                <UploadIcon className="size-10 text-stone-400" />
                <div className="text-center">
                    <p className="text-sm font-medium text-stone-700">Drag and drop files here</p>
                    <p className="text-sm text-stone-500">
                        or <span className="text-primary underline underline-offset-2">click to browse</span>
                    </p>
                </div>
                <p className="text-xs text-stone-400">
                    Up to {maxFiles} files for this field, {(maxSizeBytes / (1024 * 1024)).toFixed(0)}MB each
                </p>
            </Button>
            <input
                id={inputId}
                name="public_form_file_upload"
                ref={inputRef}
                type="file"
                multiple
                aria-label="Select files to upload"
                accept={acceptedTypes ? acceptedTypes.join(",") : undefined}
                onChange={(event) => applyFileLimits(Array.from(event.target.files || []))}
                className="hidden"
            />
            {files.length > 0 && (
                <div className="space-y-2">
                    {files.map((file, index) => (
                        <div
                            key={getUploadFileKey(file)}
                            className="flex items-center justify-between rounded-lg border border-stone-200 bg-stone-50 p-3"
                        >
                            <div className="flex items-center gap-3">
                                <FileTextIcon className="size-5 text-stone-400" />
                                <div>
                                    <p className="text-sm font-medium text-stone-700">{file.name}</p>
                                    <p className="text-xs text-stone-500">{(file.size / 1024).toFixed(1)} KB</p>
                                </div>
                            </div>
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="size-8"
                                onClick={() => onFilesChange(files.filter((_, itemIndex) => itemIndex !== index))}
                                aria-label={`Remove ${file.name}`}
                            >
                                <XIcon className="size-4" />
                            </Button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
