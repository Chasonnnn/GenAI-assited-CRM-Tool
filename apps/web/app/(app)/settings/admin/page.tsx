"use client"

import { useState, useCallback } from "react"
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
import { toast } from "sonner"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export default function AdminDataPage() {
    const { user } = useAuth()
    const [isExporting, setIsExporting] = useState<string | null>(null)
    const [isImporting, setIsImporting] = useState(false)
    const [importResult, setImportResult] = useState<{ status: string; details: Record<string, unknown> } | null>(null)

    const isDeveloper = user?.role === "developer"

    const handleExport = useCallback(async (type: "surrogates" | "config" | "analytics") => {
        setIsExporting(type)
        const headers = { "X-Requested-With": "XMLHttpRequest" }

        const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

        try {
            const createResponse = await fetch(`${API_BASE}/admin/exports/${type}`, {
                method: "POST",
                credentials: "include",
                headers,
            })

            if (!createResponse.ok) {
                throw new Error(`Export failed: ${createResponse.status}`)
            }

            const createData = await createResponse.json()
            if (
                !createData
                || typeof createData.job_id !== "string"
                || typeof createData.status !== "string"
            ) {
                throw new Error("Invalid export response")
            }
            const jobId = createData.job_id

            let jobStatus = createData.status
            let jobError: string | null = null

            for (let attempt = 0; attempt < 60; attempt += 1) {
                if (jobStatus === "completed") break
                if (jobStatus === "failed") break

                await sleep(2000)
                const statusResponse = await fetch(`${API_BASE}/admin/exports/jobs/${jobId}`, {
                    credentials: "include",
                    headers,
                })
                if (!statusResponse.ok) {
                    throw new Error(`Export status failed: ${statusResponse.status}`)
                }
                const statusData = await statusResponse.json()
                jobStatus = statusData.status
                jobError = statusData.error || null
            }

            if (jobStatus !== "completed") {
                throw new Error(jobError || "Export failed or timed out")
            }

            const downloadResponse = await fetch(`${API_BASE}/admin/exports/jobs/${jobId}/download`, {
                credentials: "include",
                headers,
            })
            if (!downloadResponse.ok) {
                throw new Error(`Export download failed: ${downloadResponse.status}`)
            }

            const downloadData = await downloadResponse.json()
            if (
                !downloadData
                || typeof downloadData.download_url !== "string"
                || typeof downloadData.filename !== "string"
            ) {
                throw new Error("Invalid export download response")
            }
            const downloadUrl = downloadData.download_url
            const filename = downloadData.filename

            const link = document.createElement("a")
            link.href = downloadUrl
            link.target = "_blank"
            link.rel = "noopener"
            link.download = filename
            document.body.appendChild(link)
            link.click()
            link.remove()

            toast.success("Export complete", { description: `Downloaded ${filename}` })
        } catch (error) {
            console.error("Export failed:", error)
            toast.error("Export failed", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        } finally {
            setIsExporting(null)
        }
    }, [])

    const handleImport = useCallback(async (type: "config" | "surrogates" | "all", files: { config?: File; surrogates?: File }) => {
        setIsImporting(true)
        setImportResult(null)

        try {
            const formData = new FormData()
            if (type === "config" || type === "all") {
                if (!files.config) throw new Error("Config ZIP required")
                formData.append("config_zip", files.config)
            }
            if (type === "surrogates" || type === "all") {
                if (!files.surrogates) throw new Error("Surrogates CSV required")
                formData.append("surrogates_csv", files.surrogates)
            }

            const response = await fetch(`${API_BASE}/admin/imports/${type}`, {
                method: "POST",
                credentials: "include",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRF-Token": "1",
                },
                body: formData,
            })

            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || `Import failed: ${response.status}`)
            }

            setImportResult({ status: "success", details: data })
            toast.success("Import complete", {
                description: `Imported ${data.surrogates_imported || 0} surrogates`,
            })
        } catch (error) {
            console.error("Import failed:", error)
            setImportResult({
                status: "error",
                details: { message: error instanceof Error ? error.message : "Unknown error" }
            })
            toast.error("Import failed", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        } finally {
            setIsImporting(false)
        }
    }, [])

    if (!isDeveloper) {
        return (
            <div className="flex min-h-screen flex-col p-6">
                <Alert variant="destructive">
                    <ShieldAlertIcon className="size-4" />
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
                    <ShieldAlertIcon className="size-4" />
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
                                        <DatabaseIcon className="size-5" />
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
                                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                                        ) : (
                                            <DownloadIcon className="mr-2 size-4" />
                                        )}
                                        Export Surrogates CSV
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <FileIcon className="size-5" />
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
                                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                                        ) : (
                                            <DownloadIcon className="mr-2 size-4" />
                                        )}
                                        Export Config ZIP
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <BarChart3Icon className="size-5" />
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
                                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                                        ) : (
                                            <DownloadIcon className="mr-2 size-4" />
                                        )}
                                        Export Analytics ZIP
                                    </Button>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    <TabsContent value="import" className="space-y-6 mt-6">
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" />
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
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                                <UploadIcon className="mr-2 size-4" />
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
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                                <UploadIcon className="mr-2 size-4" />
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
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                                <UploadIcon className="mr-2 size-4" />
                            )}
                            Import All
                        </Button>
                    </div>

                    {result && (
                        <Alert variant={result.status === "success" ? "default" : "destructive"}>
                            {result.status === "success" ? (
                                <CheckCircleIcon className="size-4" />
                            ) : (
                                <AlertCircleIcon className="size-4" />
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
