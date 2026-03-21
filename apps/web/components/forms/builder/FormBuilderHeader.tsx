"use client"

import { ArrowLeftIcon, EyeIcon, Loader2Icon, Trash2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type DeleteAction = {
    disabled?: boolean
    isPending?: boolean
    label?: string
    onClick: () => void
}

type FormBuilderHeaderProps = {
    backAriaLabel: string
    formName: string
    isPublished: boolean
    isPublishing: boolean
    isSaving: boolean
    autoSaveLabel: string | null
    autoSaveTone?: "default" | "error"
    onBack: () => void
    onFormNameChange: (value: string) => void
    onPreview: () => void
    onSave: () => void
    onPublish: () => void
    publishDisabled?: boolean
    deleteAction?: DeleteAction
}

export function FormBuilderHeader({
    backAriaLabel,
    formName,
    isPublished,
    isPublishing,
    isSaving,
    autoSaveLabel,
    autoSaveTone = "default",
    onBack,
    onFormNameChange,
    onPreview,
    onSave,
    onPublish,
    publishDisabled = false,
    deleteAction,
}: FormBuilderHeaderProps) {
    return (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/95 px-4 py-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6 lg:h-16 lg:flex-nowrap lg:py-0">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3 sm:gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    aria-label={backAriaLabel}
                    onClick={onBack}
                >
                    <ArrowLeftIcon className="size-5" />
                </Button>
                <Input
                    aria-label="Form name"
                    value={formName}
                    onChange={(event) => onFormNameChange(event.target.value)}
                    placeholder="Form name..."
                    className="h-9 min-w-0 flex-1 border-none bg-transparent px-0 text-lg font-semibold focus-visible:ring-0 sm:max-w-xs lg:w-64 lg:flex-none"
                />
                <Badge variant={isPublished ? "default" : "secondary"}>
                    {isPublished ? "Published" : "Draft"}
                </Badge>
            </div>

            <div className="flex w-full flex-wrap items-center gap-2 sm:gap-3 lg:w-auto lg:justify-end">
                {deleteAction ? (
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={deleteAction.onClick}
                        disabled={deleteAction.disabled || deleteAction.isPending}
                    >
                        {deleteAction.isPending ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : (
                            <Trash2Icon className="mr-2 size-4" />
                        )}
                        {deleteAction.label ?? "Delete"}
                    </Button>
                ) : null}
                <Button variant="outline" size="sm" onClick={onPreview}>
                    <EyeIcon className="mr-2 size-4" />
                    Preview
                </Button>
                {autoSaveLabel ? (
                    <span
                        className={`w-full text-right text-xs lg:w-auto ${
                            autoSaveTone === "error" ? "text-destructive" : "text-muted-foreground"
                        }`}
                    >
                        {autoSaveLabel}
                    </span>
                ) : null}
                <Button variant="secondary" size="sm" onClick={onSave} disabled={isSaving}>
                    {isSaving ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                    Save
                </Button>
                <Button size="sm" onClick={onPublish} disabled={publishDisabled || isPublishing}>
                    {isPublishing ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                    Publish
                </Button>
            </div>
        </div>
    )
}
