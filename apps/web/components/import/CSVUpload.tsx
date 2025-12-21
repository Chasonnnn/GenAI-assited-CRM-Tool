"use client"

import { useState, useCallback, type DragEvent } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { UploadIcon, XIcon, CheckIcon, XCircleIcon, FileIcon, Loader2Icon } from "lucide-react"
import { cn } from "@/lib/utils"
import { usePreviewImport, useExecuteImport, type ImportPreview } from "@/lib/hooks/use-import"

// Column mapping for detected fields (matches backend)
const COLUMN_MAPPING: Record<string, string[]> = {
    "full_name": ["full_name", "name", "full name", "fullname"],
    "email": ["email", "email_address", "e-mail", "emailaddress"],
    "phone": ["phone", "phone_number", "phonenumber", "mobile", "cell"],
    "state": ["state", "st"],
    "date_of_birth": ["dob", "date_of_birth", "birth_date", "birthdate"],
    "source": ["source"],
}

interface CSVUploadProps {
    onImportComplete?: () => void
}

export function CSVUpload({ onImportComplete }: CSVUploadProps) {
    const [file, setFile] = useState<File | null>(null)
    const [isDragging, setIsDragging] = useState(false)
    const [preview, setPreview] = useState<ImportPreview | null>(null)
    const [error, setError] = useState<string>("")

    const previewMutation = usePreviewImport()
    const executeMutation = useExecuteImport()

    const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(true)
    }, [])

    const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(false)
    }, [])

    const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(false)

        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile) {
            handleFileSelect(droppedFile)
        }
    }, [])

    const handleFileSelect = async (selectedFile: File) => {
        // Validate file type
        if (!selectedFile.name.endsWith(".csv")) {
            setError("Please upload a CSV file")
            return
        }

        setError("")
        setFile(selectedFile)

        // Preview import
        try {
            const previewData = await previewMutation.mutateAsync(selectedFile)
            setPreview(previewData)
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to preview CSV")
            setFile(null)
        }
    }

    const detectColumnMapping = (header: string): boolean => {
        const normalizedHeader = header.toLowerCase().trim().replace(/\s+/g, "_").replace(/-/g, "_")
        return Object.keys(COLUMN_MAPPING).includes(normalizedHeader) ||
            Object.values(COLUMN_MAPPING).some((mappings) =>
                mappings.some((mapping) => normalizedHeader === mapping.toLowerCase())
            )
    }

    const handleRemoveFile = () => {
        setFile(null)
        setPreview(null)
        setError("")
    }

    const handleImport = async () => {
        if (!file) return

        try {
            await executeMutation.mutateAsync(file)
            setFile(null)
            setPreview(null)
            onImportComplete?.()
        } catch (err: any) {
            setError(err.response?.data?.detail || "Import failed")
        }
    }

    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return bytes + " B"
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
        return (bytes / (1024 * 1024)).toFixed(1) + " MB"
    }

    return (
        <div className="space-y-6">
            {/* Upload Zone */}
            {!preview && (
                <Card>
                    <div
                        className={cn(
                            "relative flex min-h-[300px] cursor-pointer flex-col items-center justify-center border-2 border-dashed p-12 transition-colors",
                            isDragging && "border-primary bg-primary/5",
                            !isDragging && "border-border hover:border-primary/50 hover:bg-muted/50",
                            error && "border-destructive",
                        )}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => document.getElementById("file-upload")?.click()}
                    >
                        <input
                            id="file-upload"
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={(e) => {
                                const selectedFile = e.target.files?.[0]
                                if (selectedFile) handleFileSelect(selectedFile)
                            }}
                        />

                        {previewMutation.isPending ? (
                            <>
                                <Loader2Icon className="mb-4 size-12 animate-spin text-muted-foreground" />
                                <h3 className="mb-2 text-lg font-semibold">Processing CSV...</h3>
                                <p className="text-sm text-muted-foreground">Analyzing rows and detecting duplicates</p>
                            </>
                        ) : (
                            <>
                                <UploadIcon className="mb-4 size-12 text-muted-foreground" />
                                <h3 className="mb-2 text-lg font-semibold">
                                    {isDragging ? "Drop CSV file here" : "Drag CSV here or click to browse"}
                                </h3>
                                <p className="text-sm text-muted-foreground">Upload a CSV file to import cases</p>
                            </>
                        )}

                        {error && (
                            <div className="mt-4 flex items-center gap-2 text-sm text-destructive">
                                <XCircleIcon className="size-4" />
                                {error}
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Preview Table */}
            {preview && (
                <>
                    {/* Stats Banner */}
                    <Card className="p-4">
                        <div className="flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground">Total Rows:</span>
                                <Badge variant="secondary">{preview.total_rows}</Badge>
                            </div>

                            {preview.duplicate_emails_db > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Duplicates in DB:</span>
                                    <Badge className="bg-destructive/10 text-destructive border-destructive/20">
                                        {preview.duplicate_emails_db}
                                    </Badge>
                                </div>
                            )}

                            {preview.duplicate_emails_csv > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Duplicates in CSV:</span>
                                    <Badge className="bg-amber-500/10 text-amber-500 border-amber-500/20">
                                        {preview.duplicate_emails_csv}
                                    </Badge>
                                </div>
                            )}

                            {preview.validation_errors > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Validation Errors:</span>
                                    <Badge className="bg-destructive/10 text-destructive border-destructive/20">
                                        {preview.validation_errors}
                                    </Badge>
                                </div>
                            )}

                            <div className="ml-auto flex items-center gap-2">
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <FileIcon className="size-4" />
                                    {file?.name}
                                </div>
                                <Button variant="ghost" size="sm" onClick={handleRemoveFile}>
                                    <XIcon className="size-4" />
                                </Button>
                            </div>
                        </div>
                    </Card>

                    {/* Data Table */}
                    <Card className="overflow-hidden">
                        <CardHeader>
                            <CardTitle>Preview ({preview.sample_rows.length} of {preview.total_rows} rows)</CardTitle>
                            <CardDescription>Review the data before importing. Duplicates will be skipped.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-[500px] overflow-auto">
                                <Table>
                                    <TableHeader className="sticky top-0 z-10 bg-background">
                                        <TableRow>
                                            {preview.detected_columns.map((header, idx) => (
                                                <TableHead key={idx}>
                                                    <div className="flex items-center gap-2">
                                                        <span>{header}</span>
                                                        {detectColumnMapping(header) ? (
                                                            <Badge className="bg-green-500/10 text-green-500 border-green-500/20 text-xs">
                                                                Mapped
                                                            </Badge>
                                                        ) : (
                                                            <Badge variant="secondary" className="bg-gray-500/10 text-gray-400 border-gray-500/20 text-xs">
                                                                Unmapped
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </TableHead>
                                            ))}
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {preview.sample_rows.map((row, rowIdx) => (
                                            <TableRow key={rowIdx}>
                                                {preview.detected_columns.map((header, cellIdx) => (
                                                    <TableCell key={cellIdx}>{row[header] || <span className="text-muted-foreground">—</span>}</TableCell>
                                                ))}
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>

                            {preview.unmapped_columns.length > 0 && (
                                <div className="mt-4 p-3 rounded-lg bg-muted/50 text-sm">
                                    <p className="font-medium mb-1">Unmapped Columns (will be ignored):</p>
                                    <div className="flex flex-wrap gap-2">
                                        {preview.unmapped_columns.map((col, idx) => (
                                            <Badge key={idx} variant="secondary" className="text-xs">
                                                {col}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Action Buttons */}
                    <div className="flex items-center justify-end gap-3">
                        <Button variant="outline" onClick={handleRemoveFile} disabled={executeMutation.isPending}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleImport}
                            disabled={preview.validation_errors > 0 || executeMutation.isPending}
                            className="min-w-[140px]"
                        >
                            {executeMutation.isPending ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    Importing...
                                </>
                            ) : (
                                `Import ${preview.total_rows} Cases`
                            )}
                        </Button>
                    </div>

                    {executeMutation.isSuccess && (
                        <Card className="bg-green-500/10 border-green-500/20">
                            <CardContent className="py-3">
                                <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                                    <CheckIcon className="size-5" />
                                    <p className="font-medium">Import completed successfully! Check history below for details.</p>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {error && executeMutation.isError && (
                        <Card className="bg-destructive/10 border-destructive/20">
                            <CardContent className="py-3">
                                <div className="flex items-center gap-2 text-destructive">
                                    <XCircleIcon className="size-5" />
                                    <p className="font-medium">{error}</p>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </>
            )}
        </div>
    )
}
