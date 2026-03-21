"use client"

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
import { PublishDialog } from "@/components/ops/templates/PublishDialog"
import type { TemplateFormBuilderPageController } from "@/lib/forms/use-template-form-builder-page"

import { DeletePageDialog } from "@/components/forms/builder/DeletePageDialog"
import { FormBuilderHeader } from "@/components/forms/builder/FormBuilderHeader"
import { FormBuilderWorkspace } from "@/components/forms/builder/FormBuilderWorkspace"
import { FormBuilderWorkspaceTabs } from "@/components/forms/builder/FormBuilderWorkspaceTabs"
import { TemplateFormSettingsPanel } from "@/components/forms/builder/TemplateFormSettingsPanel"
import { Loader2Icon } from "lucide-react"

type TemplateFormBuilderScreenProps = {
    controller: TemplateFormBuilderPageController
}

export function TemplateFormBuilderScreen({
    controller,
}: TemplateFormBuilderScreenProps) {
    if (controller.showLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-background">
                <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2Icon className="size-5 animate-spin" />
                    <span>Loading template...</span>
                </div>
            </div>
        )
    }

    if (controller.shouldRenderNull) {
        return null
    }

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <AlertDialog
                open={controller.state.showDeleteTemplateDialog}
                onOpenChange={controller.onDeleteTemplateDialogOpenChange}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete template?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This permanently deletes{" "}
                            <span className="font-medium text-foreground">
                                {controller.state.formName.trim() || "this template"}
                            </span>
                            . This cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={controller.deleteTemplateMutation.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            onClick={controller.handleDeleteTemplate}
                            disabled={controller.deleteTemplateMutation.isPending}
                            className="bg-destructive text-white hover:bg-destructive/90"
                        >
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <FormBuilderHeader
                backAriaLabel="Back to form templates"
                formName={controller.state.formName}
                isMobilePreview={controller.state.isMobilePreview}
                isPublished={controller.state.isPublished}
                isPublishing={controller.state.isPublishing}
                isSaving={controller.state.isSaving}
                autoSaveLabel={controller.autoSaveLabel}
                autoSaveTone={controller.state.autoSaveStatus === "error" ? "error" : "default"}
                onBack={controller.onBack}
                onFormNameChange={controller.onFormNameChange}
                onPreview={controller.handlePreview}
                onToggleMobilePreview={controller.onToggleMobilePreview}
                onSave={controller.handleSave}
                onPublish={controller.handlePublish}
                publishDisabled={controller.state.isPublished}
                {...(!controller.isNewForm
                    ? {
                        deleteAction: {
                            onClick: () => controller.patchState({ showDeleteTemplateDialog: true }),
                            isPending: controller.deleteTemplateMutation.isPending,
                            disabled: controller.state.isSaving || controller.state.isPublishing,
                        },
                    }
                    : {})}
            />

            <FormBuilderWorkspaceTabs
                value={controller.state.workspaceTab}
                onValueChange={controller.onWorkspaceTabChange}
                tabs={[
                    { value: "builder", label: "Builder" },
                    { value: "settings", label: "Settings" },
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
                <TemplateFormSettingsPanel {...controller.formSettingsProps} />
            </div>

            <PublishDialog
                open={controller.state.showPublishDialog}
                onOpenChange={controller.onPublishDialogOpenChange}
                onPublish={controller.confirmPublish}
                isLoading={controller.state.isPublishing}
                title="Publish Form Template"
                description="Publish this form template to org libraries. Draft edits stay private until you re-publish."
                defaultPublishAll={controller.templateData?.is_published_globally ?? true}
                initialOrgIds={controller.templateData?.target_org_ids ?? []}
            />

            <DeletePageDialog
                open={controller.state.showDeletePageDialog}
                onOpenChange={controller.onDeletePageDialogOpenChange}
                onConfirm={controller.confirmDeletePage}
            />
        </div>
    )
}
