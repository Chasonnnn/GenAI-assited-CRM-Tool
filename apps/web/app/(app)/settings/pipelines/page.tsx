"use client"

import { useRef, useState } from "react"
import { flushSync } from "react-dom"
import { HistoryIcon, Loader2Icon, WorkflowIcon } from "lucide-react"

import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import {
    DeleteStageDialog,
    ImpactPreviewCard,
    PipelineEntitySelect,
    PipelineEntityToggle,
    SurrogatePipelineSections,
    VersionHistorySheet,
} from "@/components/pipelines/pipeline-panels"
import { StageDrawer } from "@/components/pipelines/stage-drawer"
import {
    getMobileStageRowId,
    MobileReorderList,
    MobileStageList,
    MobileStagePage,
    MobileStagesBar,
} from "@/components/pipelines/stage-mobile"
import { StagesToolbar, StageTable } from "@/components/pipelines/stage-table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SaveBar } from "@/components/ui/save-bar"
import { useIsMobile } from "@/hooks/use-mobile"
import type {
    PipelineChangePreview,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineStage,
} from "@/lib/api/pipelines"
import { useAuth } from "@/lib/auth-context"
import { focusFirstInvalid } from "@/lib/forms/use-form-validation"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import {
    useApplyPipelineDraft,
    usePipeline,
    usePipelineChangePreview,
    usePipelineDependencyGraph,
    usePipelines,
    useRecommendedPipelineDraft,
    useRollbackPipeline,
} from "@/lib/hooks/use-pipelines"
import { buildRecommendedDraftRemaps } from "@/lib/pipeline-reset-remaps"
import {
    applyLocalFeatureConfigRemap,
    buildApiDraft,
    buildDraft,
    buildDuplicateStage,
    buildNewStage,
    countDraftChanges,
    countStageErrors,
    createFallbackFeatureConfig,
    deepClone,
    getDefaultRemapTargetStageKey,
    getDefaultStageInsertIndex,
    getDeleteRequirements,
    getDependencyByStageKey,
    getDraftStageErrors,
    IMPACT_LABELS,
    IMPACT_PREVIEW_ID,
    moveStageInList,
    stringifyDraft,
    withCurrentLockMetadata,
    withStageFunnel,
    withStageMilestones,
    type DeleteStageState,
    type EditableStage,
    type ImpactArea,
    type PipelineDraftState,
    type ScopedEditorState,
} from "@/lib/pipelines/stage-editor"
import { SettingsPageGate } from "../settings-page-gate"

function usePipelineSettingsEditor() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const [entityType, setEntityType] = useState<PipelineEntityType>("surrogate")

    const pipelinesQuery = usePipelines(entityType)
    const { data: pipelines, isLoading: pipelinesLoading } = pipelinesQuery
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default)
    const pipelineQuery = usePipeline(
        defaultPipeline?.id || null,
        entityType,
    )
    const { data: pipeline, isLoading: pipelineLoading } = pipelineQuery
    const loadErrorQuery = pipelinesQuery.isError
        ? pipelinesQuery
        : pipelineQuery.isError
            ? pipelineQuery
            : null
    const [focusStageId, setFocusStageId] = useState<string | null>(null)
    const dependencyGraphQuery = usePipelineDependencyGraph(defaultPipeline?.id || null, entityType)
    const applyDraft = useApplyPipelineDraft()
    const rollbackPipeline = useRollbackPipeline()
    const recommendedDraft = useRecommendedPipelineDraft(defaultPipeline?.id || null, entityType)
    const editorContextKey = `${entityType}:${defaultPipeline?.id ?? "none"}:${pipeline?.current_version ?? 0}`

    const [draftOverride, setDraftOverride] = useState<ScopedEditorState<PipelineDraftState> | null>(null)
    const [deleteStageOverride, setDeleteStageOverride] = useState<ScopedEditorState<DeleteStageState> | null>(null)

    const isLoading = pipelinesLoading || pipelineLoading
    const baselineDraft = buildDraft(pipeline, entityType)
    const scopedDraft = draftOverride?.contextKey === editorContextKey ? draftOverride : null
    const debouncedScopedDraft = useDebouncedValue(scopedDraft, 1200)
    const draft = scopedDraft?.value ?? null
    const debouncedDraft = debouncedScopedDraft?.contextKey === editorContextKey ? debouncedScopedDraft.value : null
    const deleteStageState =
        deleteStageOverride?.contextKey === editorContextKey ? deleteStageOverride.value : null
    const currentDraft = draft ?? baselineDraft
    const baselineDraftFingerprint = baselineDraft ? stringifyDraft(baselineDraft) : null
    const debouncedDraftFingerprint = debouncedDraft ? stringifyDraft(debouncedDraft) : null
    const draftIsDebounced = scopedDraft === debouncedScopedDraft
    const hasChanges = scopedDraft
        ? !draftIsDebounced || debouncedDraftFingerprint !== baselineDraftFingerprint
        : false
    const changeCount = countDraftChanges(baselineDraft, draft)
    const stageErrors = draft ? getDraftStageErrors(draft.stages) : {}
    const stageErrorCount = countStageErrors(stageErrors)
    // Drafts that fail the API's field rules would only return a 422; show inline errors instead.
    const debouncedDraftHasErrors = debouncedDraft
        ? countStageErrors(getDraftStageErrors(debouncedDraft.stages)) > 0
        : false
    const previewDraftPayload = !debouncedDraft
        || debouncedDraftFingerprint === baselineDraftFingerprint
        || debouncedDraftHasErrors
        ? null
        : {
            ...buildApiDraft(debouncedDraft),
            ...(pipeline?.current_version
                ? { expected_version: pipeline.current_version }
                : {}),
        }
    const previewDraftFingerprint = previewDraftPayload ? JSON.stringify(previewDraftPayload) : ""
    const previewQuery = usePipelineChangePreview(
        defaultPipeline?.id || null,
        previewDraftPayload,
        entityType,
        previewDraftFingerprint,
    )
    const preview: PipelineChangePreview | null = previewDraftPayload ? previewQuery.data ?? null : null
    const dependencyGraph = preview?.dependency_graph ?? dependencyGraphQuery.data ?? null

    const currentStages = currentDraft?.stages ?? []
    const currentFeatureConfig = currentDraft?.featureConfig
    const setScopedDraft = (value: PipelineDraftState | null) => {
        setDraftOverride(value ? { contextKey: editorContextKey, value } : null)
    }
    const setScopedDeleteStageState = (value: DeleteStageState | null) => {
        setDeleteStageOverride(value ? { contextKey: editorContextKey, value } : null)
    }

    const updateDraft = (updater: (current: PipelineDraftState) => PipelineDraftState) => {
        setDraftOverride((previous) => {
            const scopedPrevious =
                previous?.contextKey === editorContextKey ? previous.value : null
            const base = scopedPrevious
                ?? baselineDraft
                ?? {
                    name: pipeline?.name ?? "Default Pipeline",
                    stages: [],
                    featureConfig: createFallbackFeatureConfig([]),
                    remaps: [],
                }
            return {
                contextKey: editorContextKey,
                value: updater(deepClone(base)),
            }
        })
    }

    const updateDraftFeatureConfig = (featureConfig: PipelineFeatureConfig) => {
        updateDraft((current) => ({
            ...current,
            featureConfig,
        }))
    }

    const updateStage = (stageId: string, updater: (stage: EditableStage) => EditableStage) => {
        updateDraft((current) => ({
            ...current,
            stages: current.stages.map((stage) => (stage.id === stageId ? updater(stage) : stage)),
        }))
    }

    const reorderStages = (fromIndex: number, toIndex: number) => {
        updateDraft((current) => ({
            ...current,
            stages: moveStageInList(current.stages, fromIndex, toIndex),
        }))
    }

    const moveStage = (stageId: string, delta: -1 | 1) => {
        updateDraft((current) => {
            const index = current.stages.findIndex((stage) => stage.id === stageId)
            if (index < 0) return current
            return { ...current, stages: moveStageInList(current.stages, index, index + delta) }
        })
    }

    const setStageMilestones = (stageKey: string, milestoneSlugs: string[]) => {
        updateDraft((current) => ({
            ...current,
            featureConfig: withStageMilestones(current.featureConfig, stageKey, milestoneSlugs),
        }))
    }

    const setStageFunnel = (stageKey: string, included: boolean) => {
        updateDraft((current) => ({
            ...current,
            featureConfig: withStageFunnel(current.featureConfig, current.stages, stageKey, included),
        }))
    }

    /** Returns the new stage's id so the caller can open it. */
    const handleAddStage = (): string | null => {
        if (!currentDraft) return null
        const insertIndex = getDefaultStageInsertIndex(currentDraft.stages)
        const newStage = buildNewStage(currentDraft, entityType, insertIndex)
        updateDraft((current) => {
            const nextStages = [...current.stages]
            nextStages.splice(insertIndex, 0, newStage)
            return {
                ...current,
                stages: nextStages.map((stage, index) => ({ ...stage, order: index + 1 })),
            }
        })
        // The new row's label input scrolls into view and takes focus when it mounts.
        setFocusStageId(newStage.id)
        return newStage.id
    }

    /** Returns the copy's id so the drawer can switch to it. */
    const handleDuplicateStage = (stageKey: string): string | null => {
        if (!currentDraft) return null
        const sourceIndex = currentDraft.stages.findIndex((stage) => stage.stage_key === stageKey)
        const source = currentDraft.stages[sourceIndex]
        if (!source || source.is_locked) return null
        const duplicate = buildDuplicateStage(source, currentDraft)
        updateDraft((current) => {
            const nextStages = [...current.stages]
            nextStages.splice(sourceIndex + 1, 0, duplicate)
            return {
                ...current,
                stages: nextStages.map((stage, index) => ({ ...stage, order: index + 1 })),
            }
        })
        return duplicate.id
    }

    const handleRequestDeleteStage = (stageKey: string) => {
        const stage = currentStages.find((item) => item.stage_key === stageKey)
        if (!stage || stage.is_locked) return
        const requiresRemap = getDeleteRequirements(
            dependencyGraph,
            stageKey,
            entityType,
        ).length > 0
        setScopedDeleteStageState({
            stageKey,
            targetStageKey: requiresRemap
                ? getDefaultRemapTargetStageKey(currentStages, stageKey)
                : "",
        })
    }

    const handleConfirmDeleteStage = () => {
        if (!deleteStageState) return
        const removedStageKey = deleteStageState.stageKey
        const targetStageKey = deleteStageState.targetStageKey || undefined
        updateDraft((current) => {
            const nextStages: EditableStage[] = []
            for (const stage of current.stages) {
                if (stage.stage_key === removedStageKey) continue
                nextStages.push({ ...stage, order: nextStages.length + 1 })
            }

            return {
                ...current,
                stages: nextStages,
                featureConfig: applyLocalFeatureConfigRemap(
                    current.featureConfig,
                    removedStageKey,
                    targetStageKey,
                ),
                remaps: [
                    ...current.remaps.filter((item) => item.removed_stage_key !== removedStageKey),
                    ...(targetStageKey
                        ? [
                              {
                                  removed_stage_key: removedStageKey,
                                  target_stage_key: targetStageKey,
                              },
                          ]
                        : []),
                ],
            }
        })
        setScopedDeleteStageState(null)
    }

    const handleReset = () => {
        setScopedDraft(null)
        setScopedDeleteStageState(null)
    }

    const handleResetToRecommended = async () => {
        if (!pipeline) return
        const { data: recommended } = await recommendedDraft.refetch()
        if (!recommended) return

        const nextDraft = buildDraft(
            {
                name: recommended.name,
                stages: withCurrentLockMetadata(recommended.stages as PipelineStage[], pipeline.stages),
                feature_config: recommended.feature_config,
            },
            entityType,
        )
        if (!nextDraft) return
        nextDraft.remaps = buildRecommendedDraftRemaps(pipeline.stages, nextDraft.stages)
        setScopedDraft(nextDraft)
    }

    const handleSave = async () => {
        if (!pipeline || !currentDraft) return
        if (stageErrorCount > 0) return
        if (previewQuery.isLoading) return
        if (preview && (preview.validation_errors.length > 0 || preview.blocking_issues.length > 0)) {
            return
        }

        try {
            await applyDraft.mutateAsync({
                id: pipeline.id,
                data: {
                    ...buildApiDraft(currentDraft),
                    expected_version: pipeline.current_version,
                    comment: "Applied pipeline draft",
                },
                entityType,
            })
            setScopedDraft(null)
            setScopedDeleteStageState(null)
        } catch {
            // Hook toasts surface the error.
        }
    }

    const handleRollback = async (version: number) => {
        if (!pipeline) return
        try {
            await rollbackPipeline.mutateAsync({ id: pipeline.id, version, entityType })
            setScopedDraft(null)
            setScopedDeleteStageState(null)
        } catch {
            // Hook toasts surface the error.
        }
    }

    const selectedDeleteStage = deleteStageState
        ? currentStages.find((stage) => stage.stage_key === deleteStageState.stageKey)
        : undefined
    const impactAreas = (preview?.impact_areas ?? []) as ImpactArea[]
    const validationErrors = preview?.validation_errors ?? []
    const blockingIssues = preview?.blocking_issues ?? []
    const requiredRemaps = preview?.required_remaps ?? []
    const showSurrogateEditors = entityType === "surrogate"

    return {
        entityType,
        setEntityType,
        isDeveloper,
        isLoading,
        loadErrorQuery,
        pipeline,
        currentStages,
        currentFeatureConfig,
        dependencyGraph,
        deleteStageState,
        selectedDeleteStage,
        impactAreas,
        validationErrors,
        blockingIssues,
        requiredRemaps,
        safeAutoFixes: preview?.safe_auto_fixes ?? [],
        showSurrogateEditors,
        hasChanges,
        changeCount,
        stageErrors,
        stageErrorCount,
        focusStageId,
        isResetPending: recommendedDraft.isFetching,
        isSaving: applyDraft.isPending,
        isPreviewLoading: previewQuery.isLoading,
        setDeleteStageState: setScopedDeleteStageState,
        handleAddStage,
        handleDuplicateStage,
        handleRequestDeleteStage,
        handleConfirmDeleteStage,
        handleDeleteStageDialogOpenChange: (open: boolean) => {
            if (!open) setScopedDeleteStageState(null)
        },
        handleReset,
        handleResetToRecommended,
        handleRollback,
        handleSave,
        updateDraftFeatureConfig,
        updateStage,
        reorderStages,
        moveStage,
        setStageMilestones,
        setStageFunnel,
    }
}

export default function PipelinesSettingsPage() {
    return (
        <SettingsPageGate
            title="Pipelines"
            permission="manage_pipelines"
            deniedDescription="Pipeline settings need the Manage pipelines permission. Ask an admin to update your role."
        >
            <PipelinesSettingsContent />
        </SettingsPageGate>
    )
}

type StageSelection = {
    entityType: PipelineEntityType
    id: string
    stageKey: string
}

function PipelinesSettingsContent() {
    const editor = usePipelineSettingsEditor()
    const {
        entityType,
        setEntityType,
        isDeveloper,
        isLoading,
        loadErrorQuery,
        pipeline,
        currentStages,
        currentFeatureConfig,
        dependencyGraph,
        deleteStageState,
        selectedDeleteStage,
        impactAreas,
        validationErrors,
        blockingIssues,
        requiredRemaps,
        safeAutoFixes,
        showSurrogateEditors,
        hasChanges,
        changeCount,
        stageErrors,
        stageErrorCount,
        focusStageId,
        isResetPending,
        isSaving,
        isPreviewLoading,
    } = editor
    const isMobile = useIsMobile()
    const [versionHistoryOpen, setVersionHistoryOpen] = useState(false)
    // UI-only state: which stage the drawer (desktop) or stage page (phone) shows.
    const [selection, setSelection] = useState<StageSelection | null>(null)
    const [drawerOpen, setDrawerOpen] = useState(false)
    const [reorderMode, setReorderMode] = useState(false)
    const [lastMovedStageId, setLastMovedStageId] = useState<string | null>(null)
    const [autoFocusStageId, setAutoFocusStageId] = useState<string | null>(null)
    const contentRef = useRef<HTMLDivElement>(null)
    const serverErrorCount = validationErrors.length + blockingIssues.length

    const scopedSelection = selection?.entityType === entityType ? selection : null
    const selectedIndex = scopedSelection
        ? (() => {
            const byId = currentStages.findIndex((stage) => stage.id === scopedSelection.id)
            return byId >= 0
                ? byId
                : currentStages.findIndex((stage) => stage.stage_key === scopedSelection.stageKey)
        })()
        : -1
    const selectedStage = selectedIndex >= 0 ? currentStages[selectedIndex] : undefined
    const lockedCount = currentStages.filter((stage) => stage.is_locked).length
    const pipelineName = pipeline?.name || "Default Pipeline"

    const openStage = (stageId: string) => {
        const stage = currentStages.find((item) => item.id === stageId)
        if (!stage) return
        setSelection({ entityType, id: stage.id, stageKey: stage.stage_key })
        setDrawerOpen(true)
    }

    /**
     * Phone only: commits the stage page (or the list when `stage` is null) synchronously, so the
     * caller can move focus into it.
     */
    const showMobileView = (stage: EditableStage | null) => {
        flushSync(() => {
            setReorderMode(false)
            setAutoFocusStageId(null)
            setSelection(stage ? { entityType, id: stage.id, stageKey: stage.stage_key } : null)
        })
    }

    const closeStage = () => {
        setDrawerOpen(false)
        if (!isMobile) return
        const stageId = selectedStage?.id
        showMobileView(null)
        if (stageId) document.getElementById(getMobileStageRowId(stageId))?.focus()
    }

    const handleEntityTypeChange = (next: PipelineEntityType) => {
        setSelection(null)
        setDrawerOpen(false)
        setReorderMode(false)
        setEntityType(next)
    }

    const handleAddStage = () => {
        const stageId = editor.handleAddStage()
        if (stageId && isMobile) {
            setReorderMode(false)
            setAutoFocusStageId(stageId)
            setSelection({ entityType, id: stageId, stageKey: stageId })
        }
    }

    const handleDuplicateSelected = () => {
        if (!selectedStage) return
        const copyId = editor.handleDuplicateStage(selectedStage.stage_key)
        if (copyId) setSelection({ entityType, id: copyId, stageKey: copyId })
    }

    const handleMobileMove = (stageId: string, delta: -1 | 1) => {
        editor.moveStage(stageId, delta)
        setLastMovedStageId(stageId)
    }

    const handleErrorsClick = () => {
        if (focusFirstInvalid(contentRef.current)) return
        if (isMobile) {
            // The phone list has no inputs, and only the list mounts the impact preview: open the
            // first stage with a field error, or return to the list for server validation errors.
            const firstInvalidStage = currentStages.find((stage) => stageErrors[stage.id])
            showMobileView(firstInvalidStage ?? null)
            if (firstInvalidStage && focusFirstInvalid(contentRef.current)) return
        }
        const impactPreview = document.getElementById(IMPACT_PREVIEW_ID)
        impactPreview?.scrollIntoView?.({ block: "center" })
        impactPreview?.focus({ preventScroll: true })
    }

    const mobileStage = isMobile ? selectedStage : undefined
    const showPageHeader = !mobileStage && !(isMobile && reorderMode)

    const header = showPageHeader ? (
        <PageHeader
            title="Pipelines"
            meta={pipeline ? <Badge variant="outline">v{pipeline.current_version}</Badge> : null}
            actions={
                isMobile ? (
                    <>
                        <PipelineEntitySelect entityType={entityType} onEntityTypeChange={handleEntityTypeChange} />
                        <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            onClick={() => setVersionHistoryOpen(true)}
                            disabled={!pipeline}
                            aria-label="Version history"
                        >
                            <HistoryIcon aria-hidden="true" />
                        </Button>
                    </>
                ) : (
                    <>
                        <PipelineEntityToggle entityType={entityType} onEntityTypeChange={handleEntityTypeChange} />
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setVersionHistoryOpen(true)}
                            disabled={!pipeline}
                        >
                            <HistoryIcon className="mr-2 size-4" aria-hidden="true" />
                            Version history
                        </Button>
                    </>
                )
            }
        />
    ) : null

    if (isLoading || loadErrorQuery || !pipeline) {
        return (
            <div className="flex flex-1 flex-col">
                {header}
                <div className="p-6">
                    {isLoading ? (
                        <div className="flex items-center justify-center p-6" role="status" aria-label="Loading">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" aria-hidden="true" />
                        </div>
                    ) : loadErrorQuery ? (
                        <QueryErrorState
                            error={loadErrorQuery.error}
                            onRetry={() => void loadErrorQuery.refetch()}
                            isRetrying={loadErrorQuery.isFetching}
                            title="Couldn't load the pipeline"
                            headingLevel={2}
                        />
                    ) : (
                        <EmptyState icon={WorkflowIcon} title="No default pipeline" headingLevel={2} />
                    )}
                </div>
            </div>
        )
    }

    const stageSettingsProps = selectedStage
        ? {
            entityType,
            stage: selectedStage,
            index: selectedIndex,
            total: currentStages.length,
            errors: stageErrors[selectedStage.id],
            dependency: getDependencyByStageKey(dependencyGraph, selectedStage.stage_key),
            featureConfig: currentFeatureConfig,
            showSurrogateEditors,
            onStageChange: (updater: (stage: EditableStage) => EditableStage) =>
                editor.updateStage(selectedStage.id, updater),
            onMove: (delta: -1 | 1) => editor.moveStage(selectedStage.id, delta),
            onMilestonesChange: (milestoneSlugs: string[]) =>
                editor.setStageMilestones(selectedStage.stage_key, milestoneSlugs),
            onFunnelChange: (included: boolean) => editor.setStageFunnel(selectedStage.stage_key, included),
            onDuplicate: handleDuplicateSelected,
            onRequestDelete: () => editor.handleRequestDeleteStage(selectedStage.stage_key),
        }
        : null

    const surrogateSections = showSurrogateEditors && currentFeatureConfig ? (
        <SurrogatePipelineSections
            stages={currentStages}
            featureConfig={currentFeatureConfig}
            onFeatureConfigChange={editor.updateDraftFeatureConfig}
        />
    ) : null
    const impactPreview = hasChanges ? (
        <ImpactPreviewCard
            isLoading={isPreviewLoading}
            impactAreas={impactAreas}
            safeAutoFixes={safeAutoFixes}
            requiredRemaps={requiredRemaps}
            validationErrors={validationErrors}
            blockingIssues={blockingIssues}
        />
    ) : null

    return (
        <div className="flex flex-1 flex-col">
            {header}
            {isMobile ? (
                <div ref={contentRef} className="flex flex-1 flex-col">
                    {mobileStage && stageSettingsProps ? (
                        <MobileStagePage
                            {...stageSettingsProps}
                            autoFocusLabel={mobileStage.id === autoFocusStageId}
                            onBack={closeStage}
                        />
                    ) : reorderMode ? (
                        <MobileReorderList
                            stages={currentStages}
                            lastMovedStageId={lastMovedStageId}
                            onMove={handleMobileMove}
                            onDone={() => {
                                setReorderMode(false)
                                setLastMovedStageId(null)
                            }}
                        />
                    ) : (
                        <>
                            <MobileStagesBar
                                pipelineName={pipelineName}
                                stageCount={currentStages.length}
                                lockedCount={lockedCount}
                                isResetPending={isResetPending}
                                onReorder={() => setReorderMode(true)}
                                onAddStage={handleAddStage}
                                onResetToRecommended={() => void editor.handleResetToRecommended()}
                            />
                            <MobileStageList
                                entityType={entityType}
                                stages={currentStages}
                                stageErrors={stageErrors}
                                dependencyGraph={dependencyGraph}
                                onOpenStage={openStage}
                            />
                            {surrogateSections || impactPreview ? (
                                <div className="flex flex-col gap-6 p-4">
                                    {surrogateSections}
                                    {impactPreview}
                                </div>
                            ) : null}
                        </>
                    )}
                </div>
            ) : (
                <div ref={contentRef} className="flex flex-1 flex-col gap-6 p-6">
                    <section aria-label="Stages" className="flex flex-col gap-3">
                        <StagesToolbar
                            pipelineName={pipelineName}
                            stageCount={currentStages.length}
                            lockedCount={lockedCount}
                            isResetPending={isResetPending}
                            onResetToRecommended={() => void editor.handleResetToRecommended()}
                            onAddStage={handleAddStage}
                        />
                        <StageTable
                            entityType={entityType}
                            stages={currentStages}
                            stageErrors={stageErrors}
                            dependencyGraph={dependencyGraph}
                            featureConfig={currentFeatureConfig}
                            showSurrogateEditors={showSurrogateEditors}
                            focusStageId={focusStageId}
                            selectedStageId={drawerOpen ? selectedStage?.id ?? null : null}
                            onStageChange={editor.updateStage}
                            onReorder={editor.reorderStages}
                            onOpenStage={openStage}
                            onDuplicateStage={editor.handleDuplicateStage}
                            onRequestDeleteStage={editor.handleRequestDeleteStage}
                            onFunnelChange={editor.setStageFunnel}
                        />
                    </section>
                    {surrogateSections}
                    {impactPreview}
                </div>
            )}

            {isMobile ? null : (
                <StageDrawer
                    open={drawerOpen}
                    entityType={entityType}
                    stage={selectedStage}
                    index={Math.max(selectedIndex, 0)}
                    total={currentStages.length}
                    errors={selectedStage ? stageErrors[selectedStage.id] : undefined}
                    dependency={stageSettingsProps?.dependency}
                    featureConfig={currentFeatureConfig}
                    showSurrogateEditors={showSurrogateEditors}
                    onClose={closeStage}
                    onStageChange={(updater) => {
                        if (selectedStage) editor.updateStage(selectedStage.id, updater)
                    }}
                    onMove={(delta) => {
                        if (selectedStage) editor.moveStage(selectedStage.id, delta)
                    }}
                    onMilestonesChange={(slugs) => {
                        if (selectedStage) editor.setStageMilestones(selectedStage.stage_key, slugs)
                    }}
                    onFunnelChange={(included) => {
                        if (selectedStage) editor.setStageFunnel(selectedStage.stage_key, included)
                    }}
                    onDuplicate={handleDuplicateSelected}
                    onRequestDelete={() => {
                        if (selectedStage) editor.handleRequestDeleteStage(selectedStage.stage_key)
                    }}
                />
            )}

            <DeleteStageDialog
                entityType={entityType}
                stage={selectedDeleteStage}
                stages={currentStages}
                dependencyGraph={dependencyGraph}
                open={Boolean(deleteStageState)}
                state={deleteStageState}
                onOpenChange={editor.handleDeleteStageDialogOpenChange}
                onStateChange={editor.setDeleteStageState}
                onConfirm={editor.handleConfirmDeleteStage}
            />

            <VersionHistorySheet
                open={versionHistoryOpen}
                onOpenChange={setVersionHistoryOpen}
                pipeline={pipeline}
                entityType={entityType}
                onRollback={editor.handleRollback}
                canRollback={isDeveloper}
            />

            <SaveBar
                dirty={changeCount > 0}
                changeCount={changeCount}
                errorCount={stageErrorCount + serverErrorCount}
                onErrorsClick={handleErrorsClick}
                details={
                    impactAreas.length > 0 ? (
                        <span className="text-muted-foreground hidden flex-wrap items-center gap-1.5 text-[13px] sm:flex">
                            Impact
                            {impactAreas.map((area) => (
                                <Badge key={area} variant="outline">
                                    {IMPACT_LABELS[area]}
                                </Badge>
                            ))}
                        </span>
                    ) : null
                }
                saving={isSaving}
                saveDisabled={isPreviewLoading}
                onSave={() => void editor.handleSave()}
                onDiscard={editor.handleReset}
            />
        </div>
    )
}
