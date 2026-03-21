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
import { AutomationFormSettingsPanel } from "@/components/forms/builder/AutomationFormSettingsPanel"
import { AutomationFormSubmissionsPanel } from "@/components/forms/builder/AutomationFormSubmissionsPanel"
import { DeletePageDialog } from "@/components/forms/builder/DeletePageDialog"
import { FormBuilderHeader } from "@/components/forms/builder/FormBuilderHeader"
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
    if (controller.showLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-background">
                <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2Icon className="size-5 animate-spin" />
                    <span>Loading form...</span>
                </div>
            </div>
        )
    }

    if (controller.shouldRenderNull) {
        return null
    }

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <FormBuilderHeader
                backAriaLabel="Back to forms"
                formName={controller.state.formName}
                isPublished={controller.state.isPublished}
                isPublishing={controller.state.isPublishing}
                isSaving={controller.state.isSaving}
                autoSaveLabel={controller.autoSaveLabel}
                autoSaveTone={controller.state.autoSaveStatus === "error" ? "error" : "default"}
                onBack={controller.onBack}
                onFormNameChange={controller.onFormNameChange}
                onPreview={controller.handlePreview}
                onSave={controller.handleSave}
                onPublish={controller.handlePublish}
                publishDisabled={controller.state.isPublished}
            />

            <FormBuilderWorkspaceTabs
                value={controller.state.workspaceTab}
                onValueChange={controller.onWorkspaceTabChange}
                tabs={[
                    { value: "builder", label: "Builder" },
                    { value: "settings", label: "Settings" },
                    {
                        value: "submissions",
                        label: "Submissions",
                        badgeCount: controller.submissionsPanelProps.pendingSubmissionHistory.length,
                    },
                ]}
            />

            {controller.state.workspaceTab === "builder" ? (
                <FormBuilderWorkspace {...controller.workspaceProps} />
            ) : (
                <div data-testid="form-builder-workspace" className="hidden" />
            )}

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
                onOpenChange={controller.onShareDialogOpenChange}
                onCopyLink={controller.handleCopySharedLink}
                onDownloadQrSvg={controller.handleDownloadQrSvg}
                onDownloadQrPng={controller.handleDownloadQrPng}
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
                            className="bg-teal-600 hover:bg-teal-700"
                            disabled={controller.state.isPublishing}
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
