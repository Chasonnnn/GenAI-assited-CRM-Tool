"use client"

import * as React from "react"
import { ArrowLeftIcon, Loader2Icon, MoreHorizontalIcon, Trash2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

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
    contextBadgeLabel?: string
    onBack: () => void
    onFormNameChange: (value: string) => void
    onSave: () => void
    onPublish: () => void
    publishDisabled?: boolean
    /** Disables Publish and explains why in a tooltip and to screen readers. */
    publishDisabledReason?: string | null
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
    contextBadgeLabel,
    onBack,
    onFormNameChange,
    onSave,
    onPublish,
    publishDisabled = false,
    publishDisabledReason = null,
    deleteAction,
}: FormBuilderHeaderProps) {
    const publishReasonId = React.useId()
    const publishBlocked = Boolean(publishDisabledReason) && !publishDisabled
    return (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/95 px-4 py-2.5 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6 lg:h-14 lg:flex-nowrap lg:py-0">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2.5 sm:gap-3">
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
                    className="h-8 min-w-0 flex-1 border-none bg-transparent px-0 text-base font-medium focus-visible:ring-0 sm:max-w-xs lg:w-72 lg:flex-none"
                />
                <Badge variant={isPublished ? "default" : "secondary"} className="h-5 rounded-full px-2 text-[11px]">
                    {isPublished ? "Published" : "Draft"}
                </Badge>
                {contextBadgeLabel ? (
                    <Badge variant="outline" className="h-5 rounded-full px-2 text-[11px]">
                        {contextBadgeLabel}
                    </Badge>
                ) : null}
            </div>

            <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
                {deleteAction ? (
                    // Deleting the whole form lives in an overflow menu so it is not confused with
                    // the page toolbar's "Delete page". The confirm dialog renders outside the menu.
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            render={<Button variant="outline" size="icon-sm" aria-label="More actions" />}
                            disabled={deleteAction.disabled || deleteAction.isPending}
                        >
                            {deleteAction.isPending ? (
                                <Loader2Icon className="animate-spin" aria-hidden="true" />
                            ) : (
                                <MoreHorizontalIcon aria-hidden="true" />
                            )}
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem variant="destructive" onClick={deleteAction.onClick}>
                                <Trash2Icon aria-hidden="true" />
                                {deleteAction.label ?? "Delete"}
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                ) : null}
                {autoSaveLabel ? (
                    <span
                        className={`w-full text-right text-[11px] lg:w-auto ${
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
                {publishBlocked ? (
                    <>
                        <Tooltip>
                            {/* focusableWhenDisabled keeps hover and focus working so the reason can show. */}
                            <TooltipTrigger
                                render={
                                    <Button
                                        size="sm"
                                        disabled
                                        focusableWhenDisabled
                                        aria-describedby={publishReasonId}
                                        className="data-disabled:cursor-not-allowed data-disabled:opacity-50"
                                    />
                                }
                            >
                                Publish
                            </TooltipTrigger>
                            <TooltipContent>{publishDisabledReason}</TooltipContent>
                        </Tooltip>
                        <span id={publishReasonId} className="sr-only">
                            {publishDisabledReason}
                        </span>
                    </>
                ) : (
                    <Button size="sm" onClick={onPublish} disabled={publishDisabled || isPublishing}>
                        {isPublishing ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                        Publish
                    </Button>
                )}
            </div>
        </div>
    )
}
