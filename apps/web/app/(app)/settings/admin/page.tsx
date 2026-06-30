"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    DownloadIcon,
    UploadIcon,
    FileIcon,
    DatabaseIcon,
    BarChart3Icon,
    Loader2Icon,
    CheckCircleIcon,
    AlertCircleIcon,
    ShieldAlertIcon
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getCsrfHeaders } from "@/lib/csrf"
import { toast } from "sonner"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
const EXPORT_POLL_INTERVAL_MS = 2000
const EXPORT_MAX_ATTEMPTS = 60

type ExportType = "surrogates" | "config" | "analytics"
type ImportType = "config" | "surrogates" | "all"
type ImportFiles = { config?: File; surrogates?: File }

type ExportJob = {
    jobId: string
    status: string
    error: string | null
}

type ExportDownload = {
    downloadUrl: string
    filename: string
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

function getErrorMessage(error: unknown) {
    return error instanceof Error ? error.message : "Unknown error"
}

async function readExportJob(type: ExportType, headers: Record<string, string>): Promise<ExportJob> {
    const response = await fetch(`${API_BASE}/admin/exports/${type}`, {
        method: "POST",
        credentials: "include",
        headers,
    })

    if (!response.ok) {
        throw new Error(`Export failed: ${response.status}`)
    }

    const data = await response.json()
    if (
        !data
        || typeof data.job_id !== "string"
        || typeof data.status !== "string"
    ) {
        throw new Error("Invalid export response")
    }

    return {
        jobId: data.job_id,
        status: data.status,
        error: typeof data.error === "string" ? data.error : null,
    }
}

async function readExportJobStatus(jobId: string, headers: Record<string, string>): Promise<ExportJob> {
    const response = await fetch(`${API_BASE}/admin/exports/jobs/${jobId}`, {
        credentials: "include",
        headers,
    })

    if (!response.ok) {
        throw new Error(`Export status failed: ${response.status}`)
    }

    const data = await response.json()
    return {
        jobId,
        status: typeof data.status === "string" ? data.status : "failed",
        error: typeof data.error === "string" ? data.error : null,
    }
}

async function waitForExportCompletion(
    job: ExportJob,
    headers: Record<string, string>,
    attempt = 0
): Promise<void> {
    if (job.status === "completed") return
    if (job.status === "failed") {
        throw new Error(job.error || "Export failed")
    }
    if (attempt >= EXPORT_MAX_ATTEMPTS) {
        throw new Error(job.error || "Export failed or timed out")
    }

    await sleep(EXPORT_POLL_INTERVAL_MS)
    const nextJob = await readExportJobStatus(job.jobId, headers)
    await waitForExportCompletion(nextJob, headers, attempt + 1)
}

async function readExportDownload(jobId: string, headers: Record<string, string>): Promise<ExportDownload> {
    const response = await fetch(`${API_BASE}/admin/exports/jobs/${jobId}/download`, {
        credentials: "include",
        headers,
    })

    if (!response.ok) {
        throw new Error(`Export download failed: ${response.status}`)
    }

    const data = await response.json()
    if (
        !data
        || typeof data.download_url !== "string"
        || typeof data.filename !== "string"
    ) {
        throw new Error("Invalid export download response")
    }

    return {
        downloadUrl: data.download_url,
        filename: data.filename,
    }
}

function buildImportFormData(type: ImportType, files: ImportFiles) {
    const formData = new FormData()
    if (type === "config" || type === "all") {
        if (!files.config) throw new Error("Config ZIP required")
        formData.append("config_zip", files.config)
    }
    if (type === "surrogates" || type === "all") {
        if (!files.surrogates) throw new Error("Surrogates CSV required")
        formData.append("surrogates_csv", files.surrogates)
    }
    return formData
}

async function importAdminData(type: ImportType, files: ImportFiles) {
    const response = await fetch(`${API_BASE}/admin/imports/${type}`, {
        method: "POST",
        credentials: "include",
        headers: {
            ...getCsrfHeaders(),
        },
        body: buildImportFormData(type, files),
    })

    const data = await response.json()

    if (!response.ok) {
        throw new Error(data.detail || `Import failed: ${response.status}`)
    }

    return data
}

export default function AdminDataPage() {
    const { user } = useAuth()
    const [isExporting, setIsExporting] = useState<string | null>(null)
    const [isImporting, setIsImporting] = useState(false)
    const [importResult, setImportResult] = useState<{ status: string; details: Record<string, unknown> } | null>(null)

    const isDeveloper = user?.role === "developer"

    const handleExport = async (type: ExportType) => {
        setIsExporting(type)
        const headers = { ...getCsrfHeaders() }
        const finishExport = () => setIsExporting(null)

        try {
            const exportJob = await readExportJob(type, headers)
            await waitForExportCompletion(exportJob, headers)
            const { downloadUrl, filename } = await readExportDownload(exportJob.jobId, headers)

            const link = document.createElement("a")
            link.href = downloadUrl
            link.target = "_blank"
            link.rel = "noopener"
            link.download = filename
            document.body.appendChild(link)
            link.click()
            link.remove()

            toast.success("Export complete", { description: `Downloaded ${filename}` })
            finishExport()
        } catch (error) {
            console.error("Export failed:", error)
            toast.error("Export failed", {
                description: getErrorMessage(error),
            })
            finishExport()
        }
    }

    const handleImport = async (type: ImportType, files: ImportFiles) => {
        setIsImporting(true)
        setImportResult(null)
        const finishImport = () => setIsImporting(false)

        try {
            const data = await importAdminData(type, files)
            setImportResult({ status: "success", details: data })
            toast.success("Import complete", {
                description: `Imported ${data.surrogates_imported || 0} surrogates`,
            })
            finishImport()
        } catch (error) {
            console.error("Import failed:", error)
            setImportResult({
                status: "error",
                details: { message: getErrorMessage(error) }
            })
            toast.error("Import failed", {
                description: getErrorMessage(error),
            })
            finishImport()
        }
    }

    if (!isDeveloper) {
        return (
            <div className="flex min-h-screen flex-col p-6">
                <Alert variant="destructive">
                    <ShieldAlertIcon className="size-4" aria-hidden="true" />
                    <AlertDescription>
                        This page is only accessible to developers.
                    </AlertDescription>
                </Alert>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-16 items-center px-6">
                    <h1 className="text-2xl font-semibold">Data Management</h1>
                </div>
            </div>

            <div className="flex-1 space-y-6 p-6">
                <Alert>
                    <ShieldAlertIcon className="size-4" aria-hidden="true" />
                    <AlertDescription>
                        <strong>Developer Only.</strong> These tools export and import organization data for
                        backup, restore, and development purposes. Imports are only available in dev/test environments.
                    </AlertDescription>
                </Alert>

                <Tabs defaultValue="export" className="w-full">
                    <TabsList>
                        <TabsTrigger value="export">Export Data</TabsTrigger>
                        <TabsTrigger value="import">Import Data</TabsTrigger>
                    </TabsList>

                    <TabsContent value="export" className="space-y-6 mt-6">
                        <div className="grid gap-6 md:grid-cols-3">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <DatabaseIcon className="size-5" aria-hidden="true" />
                                        Surrogates
                                    </CardTitle>
                                    <CardDescription>
                                        Export all surrogates as CSV with full profile data
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <Button
                                        className="w-full"
                                        onClick={() => handleExport("surrogates")}
                                        disabled={isExporting !== null}
                                    >
                                        {isExporting === "surrogates" ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <DownloadIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Export Surrogates CSV
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <FileIcon className="size-5" aria-hidden="true" />
                                        Configuration
                                    </CardTitle>
                                    <CardDescription>
                                        Export org config: pipelines, templates, workflows, settings
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <Button
                                        className="w-full"
                                        onClick={() => handleExport("config")}
                                        disabled={isExporting !== null}
                                    >
                                        {isExporting === "config" ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <DownloadIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Export Config ZIP
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <BarChart3Icon className="size-5" aria-hidden="true" />
                                        Analytics
                                    </CardTitle>
                                    <CardDescription>
                                        Export analytics datasets used by Reports page
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <Button
                                        className="w-full"
                                        onClick={() => handleExport("analytics")}
                                        disabled={isExporting !== null}
                                    >
                                        {isExporting === "analytics" ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <DownloadIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Export Analytics ZIP
                                    </Button>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    <TabsContent value="import" className="space-y-6 mt-6">
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" aria-hidden="true" />
                            <AlertDescription>
                                <strong>Warning:</strong> Imports only work on empty organizations in dev/test mode.
                                This is designed for restore and development scenarios.
                            </AlertDescription>
                        </Alert>

                        <ImportForm
                            onImport={handleImport}
                            isLoading={isImporting}
                            result={importResult}
                        />
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}

function ImportForm({
    onImport,
    isLoading,
    result
}: {
    onImport: (type: "config" | "surrogates" | "all", files: { config?: File; surrogates?: File }) => Promise<void>
    isLoading: boolean
    result: { status: string; details: Record<string, unknown> } | null
}) {
    const [configFile, setConfigFile] = useState<File | null>(null)
    const [surrogatesFile, setSurrogatesFile] = useState<File | null>(null)

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Import Files</CardTitle>
                    <CardDescription>
                        Upload exported files to restore data. Config must be imported before surrogates.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="config-file">Organization Config (ZIP)</Label>
                        <Input
                            id="config-file"
                            type="file"
                            accept=".zip"
                            onChange={(e) => setConfigFile(e.target.files?.[0] || null)}
                        />
                        {configFile && (
                            <p className="text-sm text-muted-foreground">
                                Selected: {configFile.name}
                            </p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="surrogates-file">Surrogates (CSV)</Label>
                        <Input
                            id="surrogates-file"
                            type="file"
                            accept=".csv"
                            onChange={(e) => setSurrogatesFile(e.target.files?.[0] || null)}
                        />
                        {surrogatesFile && (
                            <p className="text-sm text-muted-foreground">
                                Selected: {surrogatesFile.name}
                            </p>
                        )}
                    </div>

                    <Separator />

                    <div className="flex flex-wrap gap-3">
                        <Button
                            onClick={() => onImport("config", configFile ? { config: configFile } : {})}
                            disabled={isLoading || !configFile}
                        >
                            {isLoading ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            ) : (
                                <UploadIcon className="mr-2 size-4" aria-hidden="true" />
                            )}
                            Import Config Only
                        </Button>

                        <Button
                            variant="outline"
                            onClick={() =>
                                onImport(
                                    "surrogates",
                                    surrogatesFile ? { surrogates: surrogatesFile } : {}
                                )
                            }
                            disabled={isLoading || !surrogatesFile}
                        >
                            {isLoading ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            ) : (
                                <UploadIcon className="mr-2 size-4" aria-hidden="true" />
                            )}
                            Import Surrogates Only
                        </Button>

                        <Button
                            variant="secondary"
                            onClick={() => onImport("all", {
                                ...(configFile ? { config: configFile } : {}),
                                ...(surrogatesFile ? { surrogates: surrogatesFile } : {}),
                            })}
                            disabled={isLoading || !configFile || !surrogatesFile}
                        >
                            {isLoading ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            ) : (
                                <UploadIcon className="mr-2 size-4" aria-hidden="true" />
                            )}
                            Import All
                        </Button>
                    </div>

                    {result && (
                        <Alert variant={result.status === "success" ? "default" : "destructive"}>
                            {result.status === "success" ? (
                                <CheckCircleIcon className="size-4" aria-hidden="true" />
                            ) : (
                                <AlertCircleIcon className="size-4" aria-hidden="true" />
                            )}
                            <AlertDescription>
                                {result.status === "success" ? (
                                    <pre className="text-xs overflow-auto">
                                        {JSON.stringify(result.details, null, 2)}
                                    </pre>
                                ) : (
                                    String(result.details.message || "Import failed")
                                )}
                            </AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
