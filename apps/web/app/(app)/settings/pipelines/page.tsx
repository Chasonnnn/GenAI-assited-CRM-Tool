"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
    GripVerticalIcon,
    SaveIcon,
    Loader2Icon,
    HistoryIcon,
    RotateCcwIcon,
    CheckIcon,
    InfoIcon
} from "lucide-react"
import { usePipelines, usePipeline, useUpdatePipeline, usePipelineVersions, useRollbackPipeline } from "@/lib/hooks/use-pipelines"
import type { PipelineStage } from "@/lib/api/pipelines"
import { formatDistanceToNow } from "date-fns"
import { useAuth } from "@/lib/auth-context"

function StageEditor({
    stages,
    onChange
}: {
    stages: PipelineStage[]
    onChange: (stages: PipelineStage[]) => void
}) {
    const [dragIndex, setDragIndex] = useState<number | null>(null)

    const handleDragStart = (index: number) => {
        setDragIndex(index)
    }

    const handleDragOver = (e: React.DragEvent, targetIndex: number) => {
        e.preventDefault()
        if (dragIndex === null || dragIndex === targetIndex) return

        const newStages = [...stages]
        const [removed] = newStages.splice(dragIndex, 1)
        newStages.splice(targetIndex, 0, removed)
        onChange(newStages)
        setDragIndex(targetIndex)
    }

    const handleDragEnd = () => {
        setDragIndex(null)
    }

    const updateStage = (index: number, field: keyof PipelineStage, value: string) => {
        const newStages = [...stages]
        newStages[index] = { ...newStages[index], [field]: value }
        onChange(newStages)
    }

    return (
        <div className="space-y-4">
            <div className="space-y-2">
                {stages.map((stage, index) => (
                    <div
                        key={stage.status}
                        draggable
                        onDragStart={() => handleDragStart(index)}
                        onDragOver={(e) => handleDragOver(e, index)}
                        onDragEnd={handleDragEnd}
                        className={`flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-accent/30 transition-colors ${dragIndex === index ? "opacity-50" : ""
                            }`}
                    >
                        <GripVerticalIcon className="size-4 text-muted-foreground cursor-grab" />

                        <div className="flex items-center gap-2">
                            <input
                                type="color"
                                value={stage.color}
                                onChange={(e) => updateStage(index, "color", e.target.value)}
                                className="w-8 h-8 rounded border cursor-pointer"
                            />
                        </div>

                        <div className="flex-1 grid grid-cols-2 gap-3">
                            <Input
                                value={stage.label}
                                onChange={(e) => updateStage(index, "label", e.target.value)}
                                placeholder="Label"
                                className="h-9"
                            />
                            <Input
                                value={stage.status}
                                readOnly
                                disabled
                                className="h-9 font-mono text-sm bg-muted"
                                title="Status key is read-only"
                            />
                        </div>

                        <Badge variant="outline" className="tabular-nums">
                            #{index + 1}
                        </Badge>
                    </div>
                ))}
            </div>

            <Alert>
                <InfoIcon className="size-4" />
                <AlertDescription>
                    Drag stages to reorder. Edit labels and colors. Status keys are read-only.
                </AlertDescription>
            </Alert>
        </div>
    )
}

function VersionHistory({
    pipelineId,
    onRollback,
    canRollback
}: {
    pipelineId: string
    onRollback: (version: number) => void
    canRollback: boolean
}) {
    const { data: versions, isLoading, isError } = usePipelineVersions(pipelineId)

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // Handle 403 gracefully for non-developers
    if (isError) {
        return (
            <div className="text-center py-8 text-sm text-muted-foreground">
                Version history requires Developer role
            </div>
        )
    }

    if (!versions?.length) {
        return (
            <div className="text-center py-8 text-sm text-muted-foreground">
                No version history
            </div>
        )
    }

    return (
        <div className="space-y-2">
            {versions.map((version, index) => (
                <div
                    key={version.id}
                    className={`p-3 rounded-lg border ${index === 0 ? 'bg-accent/30' : ''}`}
                >
                    <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                            <Badge variant={index === 0 ? "default" : "outline"} className="text-xs">
                                v{version.version}
                            </Badge>
                            {index === 0 && (
                                <span className="text-xs text-green-600 flex items-center gap-1">
                                    <CheckIcon className="size-3" />
                                    Current
                                </span>
                            )}
                        </div>
                        {index > 0 && canRollback && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => onRollback(version.version)}
                                className="h-7 text-xs"
                            >
                                <RotateCcwIcon className="size-3 mr-1" />
                                Restore
                            </Button>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        {formatDistanceToNow(new Date(version.created_at), { addSuffix: true })}
                    </p>
                    {version.comment && (
                        <p className="text-xs mt-1 italic">{version.comment}</p>
                    )}
                </div>
            ))}
        </div>
    )
}

export default function PipelinesSettingsPage() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const { data: pipelines, isLoading: pipelinesLoading } = usePipelines()
    const defaultPipeline = pipelines?.find(p => p.is_default)
    const { data: pipeline, isLoading: pipelineLoading } = usePipeline(defaultPipeline?.id || null)

    const updatePipeline = useUpdatePipeline()
    const rollbackPipeline = useRollbackPipeline()

    const [editedStages, setEditedStages] = useState<PipelineStage[] | null>(null)
    const [comment, setComment] = useState("")

    const isLoading = pipelinesLoading || pipelineLoading
    const currentStages = editedStages ?? pipeline?.stages ?? []
    const hasChanges = editedStages !== null

    const handleSave = async () => {
        if (!pipeline || !editedStages) return

        try {
            await updatePipeline.mutateAsync({
                id: pipeline.id,
                data: {
                    stages: editedStages,
                    expected_version: pipeline.current_version,
                    comment: comment || undefined,
                }
            })
            setEditedStages(null)
            setComment("")
        } catch (e) {
            // Error handled by mutation
        }
    }

    const handleRollback = async (version: number) => {
        if (!pipeline) return

        try {
            await rollbackPipeline.mutateAsync({ id: pipeline.id, version })
            setEditedStages(null)
        } catch (e) {
            // Error handled by mutation
        }
    }

    const handleReset = () => {
        setEditedStages(null)
        setComment("")
    }

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-5xl mx-auto">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold">Pipeline Settings</h1>
                <p className="text-sm text-muted-foreground">
                    Configure case status stages and their display order
                </p>
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                {/* Main Editor */}
                <div className="lg:col-span-2 space-y-6">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        {pipeline?.name || "Default Pipeline"}
                                        <Badge variant="outline">v{pipeline?.current_version || 1}</Badge>
                                    </CardTitle>
                                    <CardDescription>
                                        Drag to reorder stages • Click color to change
                                    </CardDescription>
                                </div>
                                {hasChanges && (
                                    <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                                        Unsaved changes
                                    </Badge>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent>
                            <StageEditor
                                stages={currentStages}
                                onChange={setEditedStages}
                            />
                        </CardContent>
                    </Card>

                    {/* Save Section */}
                    {hasChanges && (
                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="comment">Change Note (optional)</Label>
                                        <Input
                                            id="comment"
                                            placeholder="Describe what you changed..."
                                            value={comment}
                                            onChange={(e) => setComment(e.target.value)}
                                        />
                                    </div>

                                    <div className="flex gap-3">
                                        <Button
                                            onClick={handleSave}
                                            disabled={updatePipeline.isPending}
                                            className="flex-1"
                                        >
                                            {updatePipeline.isPending ? (
                                                <Loader2Icon className="size-4 mr-2 animate-spin" />
                                            ) : (
                                                <SaveIcon className="size-4 mr-2" />
                                            )}
                                            Save Changes
                                        </Button>
                                        <Button variant="outline" onClick={handleReset}>
                                            Discard
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Sidebar */}
                <div className="space-y-6">
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base flex items-center gap-2">
                                <HistoryIcon className="size-4" />
                                Version History
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {pipeline && (
                                <VersionHistory
                                    pipelineId={pipeline.id}
                                    onRollback={handleRollback}
                                    canRollback={isDeveloper}
                                />
                            )}
                        </CardContent>
                    </Card>

                    {/* Stage Preview */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Stage Preview</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-wrap gap-2">
                                {currentStages.map((stage) => (
                                    <Badge
                                        key={stage.status}
                                        style={{
                                            backgroundColor: stage.color,
                                            color: '#fff'
                                        }}
                                    >
                                        {stage.label}
                                    </Badge>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
