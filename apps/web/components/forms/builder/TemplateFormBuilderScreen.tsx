"use client"

import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import type { TemplateFormBuilderPageController } from "@/lib/forms/use-template-form-builder-page"

import { DeletePageDialog } from "@/components/forms/builder/DeletePageDialog"
import { FormBuilderHeader } from "@/components/forms/builder/FormBuilderHeader"
import { FormBuilderPreviewPane } from "@/components/forms/builder/FormBuilderPreviewPane"
import { TemplateFormPublishDialog } from "@/components/forms/builder/TemplateFormPublishDialog"
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
                    <span>Loading template&hellip;</span>
                </div>
            </div>
        )
    }

    if (controller.shouldRenderNull) {
        return null
    }

    return (
        <div className="flex min-h-[calc(100vh-3.5rem)] flex-col bg-background lg:h-[calc(100vh-3.5rem)]">
            <ConfirmDialog
                open={controller.state.showDeleteTemplateDialog}
                onOpenChange={controller.onDeleteTemplateDialogOpenChange}
                title={`Delete ${controller.state.formName.trim() || "this template"}?`}
                description="This cannot be undone."
                confirmLabel="Delete"
                errorFallback="Couldn't delete template."
                onConfirm={controller.handleDeleteTemplate}
            />

            <FormBuilderHeader
                backAriaLabel="Back to form templates"
                formName={controller.state.formName}
                publicationStatus={controller.publicationStatus}
                isPublishing={controller.state.isPublishing}
                isSaving={controller.state.isSaving}
                autoSaveLabel={controller.autoSaveLabel}
                autoSaveTone={controller.state.autoSaveStatus === "error" ? "error" : "default"}
                navigation={
                    <FormBuilderWorkspaceTabs
                        value={controller.state.workspaceTab}
                        onValueChange={controller.onWorkspaceTabChange}
                        tabs={[
                            { value: "edit", label: "Edit" },
                            { value: "preview", label: "Preview" },
                            { value: "settings", label: "Settings" },
                        ]}
                    />
                }
                onBack={controller.onBack}
                onFormNameChange={controller.onFormNameChange}
                onSave={controller.handleSave}
                onPublish={controller.handlePublish}
                saveDisabled={controller.hasPendingSave}
                publishDisabled={controller.hasPendingSave}
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

            {controller.state.workspaceTab === "edit" ? (
                <FormBuilderWorkspace {...controller.workspaceProps} />
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
                <TemplateFormSettingsPanel {...controller.formSettingsProps} />
            </div>

            <TemplateFormPublishDialog
                open={controller.state.showPublishDialog}
                onOpenChange={controller.onPublishDialogOpenChange}
                onPublish={controller.confirmPublish}
                isLoading={controller.state.isPublishing}
                disabled={controller.hasPendingSave}
            />

            <DeletePageDialog
                open={controller.state.showDeletePageDialog}
                onOpenChange={controller.onDeletePageDialogOpenChange}
                onConfirm={controller.confirmDeletePage}
            />
        </div>
    )
}
