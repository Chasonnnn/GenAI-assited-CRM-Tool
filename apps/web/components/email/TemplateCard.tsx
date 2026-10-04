import * as React from "react"
import {
    CircleCheckIcon,
    CircleOffIcon,
    CopyIcon,
    EditIcon,
    LockIcon,
    MoreHorizontalIcon,
    SendIcon,
    ShareIcon,
    TrashIcon,
} from "lucide-react"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { EmailTemplateDraft } from "@/lib/api/email-template-drafts"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import { formatDate } from "@/lib/formatters"
import { getTemplateStudioHref } from "@/components/email/template-studio-route"

export type TemplateCardActionKind =
    | "send_test"
    | "edit"
    | "set_active"
    | "set_inactive"
    | "copy"
    | "share"
    | "delete"

type TemplateCardActionGroup = "test" | "edit" | "status" | "share" | "danger"
type TemplateCardActionConfig = { group: TemplateCardActionGroup; label: string }

export type TemplateCardControls =
    | { kind: "actions"; actions: TemplateCardActionKind[]; onAction: (action: TemplateCardActionKind) => void }
    | { kind: "read_only" }

export const templateChipClassName = {
    active: "border-transparent bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    inactive: "border-transparent bg-muted text-muted-foreground",
    draft: "border-transparent bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
}

export const templateCardClassName = "relative min-w-0 gap-3 py-4 transition-colors hover:bg-accent/40"
export const templateCardTitleClassName =
    "min-w-0 flex-1 break-words text-[15px] font-semibold leading-snug"
export const templateCardLinkClassName =
    "line-clamp-2 after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"

export function TemplateCardMenuTrigger({ name }: { name: string }) {
    return (
        <DropdownMenuTrigger
            render={
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="relative z-10 -mr-2 -mt-1 size-8 shrink-0"
                    aria-label={`Actions for ${name}`}
                >
                    <MoreHorizontalIcon className="size-4" aria-hidden="true" />
                </Button>
            }
        />
    )
}

export function TemplateCardSubject({ subject }: { subject: string }) {
    return (
        <p className="truncate px-4 font-mono text-xs text-muted-foreground" title={subject}>
            {subject}
        </p>
    )
}

export function TemplateCardMeta({ ownerName, updatedAt }: { ownerName: string | null; updatedAt: string }) {
    return (
        <p className="px-4 text-xs text-muted-foreground">
            {ownerName ? `${ownerName} · ` : null}Updated {formatDate(updatedAt)}
        </p>
    )
}

export function getTemplateDraftLabel(draft: EmailTemplateDraft) {
    return draft.template_id ? "Draft changes" : "Unpublished draft"
}

function getTemplateCardActionConfig(kind: TemplateCardActionKind): TemplateCardActionConfig {
    switch (kind) {
        case "send_test": return { group: "test", label: "Send test email" }
        case "edit": return { group: "edit", label: "Edit" }
        case "set_inactive": return { group: "status", label: "Set inactive" }
        case "set_active": return { group: "status", label: "Set active" }
        case "copy": return { group: "share", label: "Copy to My Templates" }
        case "share": return { group: "share", label: "Share with Org" }
        case "delete": return { group: "danger", label: "Delete" }
    }
}

function getTemplateCardActionIcon(kind: TemplateCardActionKind) {
    switch (kind) {
        case "send_test": return <SendIcon className="mr-2 size-4" />
        case "edit": return <EditIcon className="mr-2 size-4" />
        case "set_inactive": return <CircleOffIcon className="mr-2 size-4" />
        case "set_active": return <CircleCheckIcon className="mr-2 size-4" />
        case "copy": return <CopyIcon className="mr-2 size-4" />
        case "share": return <ShareIcon className="mr-2 size-4" />
        case "delete": return <TrashIcon className="mr-2 size-4" />
    }
}

export function TemplateCard({
    template,
    controls,
    draft,
    onDiscardDraft,
}: {
    template: EmailTemplateListItem
    controls: TemplateCardControls
    draft?: EmailTemplateDraft | undefined
    onDiscardDraft?: (() => void) | undefined
}) {
    const canEdit = controls.kind === "actions" && controls.actions.includes("edit")
    const actions = controls.kind === "actions" ? controls.actions : []
    const hasMenu = actions.length > 0 || Boolean(draft && onDiscardDraft)
    return (
        <Card className={templateCardClassName}>
            <div className="flex items-start gap-2 px-4">
                <h3 className={templateCardTitleClassName}>
                    {canEdit ? (
                        <Link
                            href={getTemplateStudioHref(template)}
                            fallbackMode="router"
                            aria-label={`Edit ${template.name}`}
                            className={templateCardLinkClassName}
                        >
                            {template.name}
                        </Link>
                    ) : (
                        <span className="line-clamp-2">{template.name}</span>
                    )}
                </h3>
                {hasMenu ? (
                    <DropdownMenu>
                        <TemplateCardMenuTrigger name={template.name} />
                        <DropdownMenuContent align="end">
                            {actions.map((action, index) => {
                                const actionConfig = getTemplateCardActionConfig(action)
                                const previousAction = actions[index - 1]
                                const previousActionConfig = previousAction ? getTemplateCardActionConfig(previousAction) : null
                                return (
                                    <React.Fragment key={action}>
                                        {previousActionConfig && previousActionConfig.group !== actionConfig.group && <DropdownMenuSeparator />}
                                        <DropdownMenuItem
                                            onClick={() => controls.kind === "actions" && controls.onAction(action)}
                                            className={actionConfig.group === "danger" ? "text-destructive" : undefined}
                                        >
                                            {getTemplateCardActionIcon(action)}
                                            {actionConfig.label}
                                        </DropdownMenuItem>
                                    </React.Fragment>
                                )
                            })}
                            {draft && onDiscardDraft ? (
                                <>
                                    {actions.length > 0 ? <DropdownMenuSeparator /> : null}
                                    <DropdownMenuItem className="text-destructive" onClick={onDiscardDraft}>
                                        <TrashIcon className="mr-2 size-4" />
                                        Discard draft changes
                                    </DropdownMenuItem>
                                </>
                            ) : null}
                        </DropdownMenuContent>
                    </DropdownMenu>
                ) : null}
            </div>
            <TemplateCardSubject subject={template.subject} />
            <div className="flex flex-wrap items-center gap-1.5 px-4">
                <Badge
                    variant="outline"
                    className={template.is_active ? templateChipClassName.active : templateChipClassName.inactive}
                >
                    {template.is_active ? "Active" : "Inactive"}
                </Badge>
                {template.is_system_template ? <Badge variant="outline">System</Badge> : null}
                {draft ? (
                    <Badge variant="outline" className={templateChipClassName.draft}>
                        {getTemplateDraftLabel(draft)}
                    </Badge>
                ) : null}
                {controls.kind === "read_only" ? (
                    <Badge variant="outline">
                        <LockIcon className="mr-1 size-3" aria-hidden="true" />
                        View Only
                    </Badge>
                ) : null}
            </div>
            <TemplateCardMeta ownerName={template.owner_name} updatedAt={draft?.updated_at ?? template.updated_at} />
        </Card>
    )
}
