"use client"

import { Loader2Icon } from "lucide-react"

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { QueryErrorState } from "@/components/error-state"
import { AutomationFormSettingsPanel } from "@/components/forms/builder/AutomationFormSettingsPanel"
import { AutomationFormSubmissionsPanel } from "@/components/forms/builder/AutomationFormSubmissionsPanel"
import { DeletePageDialog } from "@/components/forms/builder/DeletePageDialog"
import {
    FORM_BUILDER_EDITOR_DENIED,
    FormBuilderBlockedScreen,
    FormBuilderLoadingState,
} from "@/components/forms/builder/FormBuilderAccessStates"
import { FormBuilderHeader } from "@/components/forms/builder/FormBuilderHeader"
import { FormBuilderPreviewPane } from "@/components/forms/builder/FormBuilderPreviewPane"
import { FormPublishReadiness } from "@/components/forms/builder/FormPublishReadiness"
import { FormBuilderWorkspace } from "@/components/forms/builder/FormBuilderWorkspace"
import { FormBuilderWorkspaceTabs } from "@/components/forms/builder/FormBuilderWorkspaceTabs"
import { ShareApplicationDialog } from "@/components/forms/builder/ShareApplicationDialog"
import type { AutomationFormBuilderPageController } from "@/lib/forms/use-automation-form-builder-page"

type AutomationFormBuilderScreenProps = {
    controller: AutomationFormBuilderPageController
}

export function AutomationFormBuilderScreen({
    controller,
}: AutomationFormBuilderScreenProps) {
    if (controller.loadError) {
        return (
            <FormBuilderBlockedScreen>
                <QueryErrorState
                    error={controller.loadError.error}
                    onRetry={controller.loadError.retry}
                    isRetrying={controller.loadError.isRetrying}
                    title="Couldn't load form"
                    forbidden={FORM_BUILDER_EDITOR_DENIED}
                    notFound={{ title: "Form not found", backHref: "/automation/forms", backLabel: "Back to forms" }}
                    headingLevel={2}
                />
            </FormBuilderBlockedScreen>
        )
    }

    if (controller.showLoading) {
        return <FormBuilderLoadingState label="Loading form…" />
    }

    if (controller.shouldRenderNull) {
        return null
    }

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <FormBuilderHeader
                backAriaLabel="Back to forms"
                formName={controller.state.formName}
                publicationStatus={controller.publicationStatus}
                isPublishing={controller.state.isPublishing}
                isSaving={controller.state.isSaving}
                autoSaveLabel={controller.autoSaveLabel}
                autoSaveTone={controller.state.autoSaveStatus === "error" ? "error" : "default"}
                contextBadgeLabel={controller.formLeadKindLabel}
                onBack={controller.onBack}
                onFormNameChange={controller.onFormNameChange}
                onSave={controller.handleSave}
                onPublish={controller.handlePublish}
                saveDisabled={controller.hasPendingSave}
                publishDisabled={controller.publishDisabled}
                publishDisabledReason={controller.publishBlockedReason}
            />

            <FormBuilderWorkspaceTabs
                value={controller.state.workspaceTab}
                onValueChange={controller.onWorkspaceTabChange}
                tabs={[
                    { value: "edit", label: "Edit" },
                    { value: "preview", label: "Preview" },
                    { value: "settings", label: "Settings" },
                    {
                        value: "submissions",
                        label: "Submissions",
                        badgeCount: controller.submissionsPanelProps.pendingSubmissionHistory.length,
                    },
                ]}
            />

            {controller.state.workspaceTab === "edit" ? (
                <FormBuilderWorkspace
                    {...controller.workspaceProps}
                    inspectorHeader={
                        controller.publishBlockedReason ? (
                            <FormPublishReadiness
                                items={controller.publishReadiness}
                                onAddField={controller.onAddReadinessField}
                                onMarkRequired={controller.onMarkReadinessFieldRequired}
                            />
                        ) : null
                    }
                />
            ) : (
                <div data-testid="form-builder-workspace" className="hidden" />
            )}

            <div className={controller.state.workspaceTab === "preview" ? "flex-1 overflow-hidden" : "hidden"}>
                <FormBuilderPreviewPane {...controller.previewProps} />
            </div>

            <div
                className={
                    controller.state.workspaceTab === "settings"
                        ? "flex-1 overflow-y-auto bg-muted/20 p-4 sm:p-6 xl:p-8"
                        : "hidden"
                }
            >
                <AutomationFormSettingsPanel {...controller.settingsPanelProps} />
            </div>

            <div className={controller.state.workspaceTab === "submissions" ? "flex-1 overflow-y-auto p-6" : "hidden"}>
                <AutomationFormSubmissionsPanel {...controller.submissionsPanelProps} />
            </div>

            <ShareApplicationDialog
                open={controller.state.showSharePrompt}
                selectedQrLink={controller.settingsPanelProps.selectedQrLink}
                formLeadKind={controller.state.formLeadKind}
                onOpenChange={controller.onShareDialogOpenChange}
                onCopyLink={controller.handleCopySharedLink}
                onDownloadQrSvg={controller.handleDownloadQrSvg}
                onDownloadQrPng={controller.handleDownloadQrPng}
                onUpdateEmbedSettings={controller.handleUpdateEmbedSettings}
                isEmbedSettingsPending={controller.updateIntakeLinkPending}
                embedHealth={controller.settingsPanelProps.selectedEmbedHealth}
                isEmbedHealthFetching={controller.settingsPanelProps.isEmbedHealthFetching}
                onRefreshEmbedHealth={controller.settingsPanelProps.onRefreshEmbedHealth}
            />

            <AlertDialog
                open={controller.state.showPublishDialog}
                onOpenChange={controller.onPublishDialogOpenChange}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Publish Form</AlertDialogTitle>
                        <AlertDialogDescription>
                            Publishing will make this form available for submissions. You can still edit the draft version, but the
                            published version will be locked until you re-publish.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={controller.state.isPublishing}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={controller.confirmPublish}
                            disabled={controller.state.isPublishing || controller.hasPendingSave}
                        >
                            {controller.state.isPublishing ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                            Publish
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <DeletePageDialog
                open={controller.state.showDeletePageDialog}
                onOpenChange={controller.onDeletePageDialogOpenChange}
                onConfirm={controller.confirmDeletePage}
            />
        </div>
    )
}
