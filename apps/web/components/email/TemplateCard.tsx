import * as React from "react"
import {
    CircleCheckIcon,
    CircleOffIcon,
    CopyIcon,
    EditIcon,
    LockIcon,
    MoreVerticalIcon,
    SendIcon,
    ShareIcon,
    TrashIcon,
    UserIcon,
} from "lucide-react"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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

export function TemplateCard({ template, controls }: { template: EmailTemplateListItem; controls: TemplateCardControls }) {
    const canEdit = controls.kind === "actions" && controls.actions.includes("edit")
    return (
        <Card className="group relative min-w-0">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-2">
                            <CardTitle className="min-h-12 text-base leading-6 break-words">
                                {canEdit ? (
                                    <Link href={getTemplateStudioHref(template)} fallbackMode="router" aria-label={`Edit ${template.name}`} className="block w-full cursor-pointer rounded-sm text-left transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                                        <span className="line-clamp-2">{template.name}</span>
                                    </Link>
                                ) : <span className="line-clamp-2">{template.name}</span>}
                            </CardTitle>
                            {template.is_system_template && <Badge variant="secondary" className="text-xs shrink-0">System</Badge>}
                        </div>
                        <CardDescription className="mt-1 line-clamp-2 min-h-10 break-words" title={template.subject}>{template.subject}</CardDescription>
                        {template.owner_name && <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1"><UserIcon className="size-3" />{template.owner_name}</p>}
                    </div>
                    {controls.kind === "actions" && controls.actions.length > 0 && (
                        <DropdownMenu>
                            <DropdownMenuTrigger render={<Button type="button" variant="outline" size="icon" className="size-8 shrink-0" aria-label={`Actions for ${template.name}`}><MoreVerticalIcon className="size-4" aria-hidden="true" /></Button>} />
                            <DropdownMenuContent align="end">
                                {controls.actions.map((action, index) => {
                                    const actionConfig = getTemplateCardActionConfig(action)
                                    const previousAction = controls.actions[index - 1]
                                    const previousActionConfig = previousAction ? getTemplateCardActionConfig(previousAction) : null
                                    return (
                                        <React.Fragment key={action}>
                                            {previousActionConfig && previousActionConfig.group !== actionConfig.group && <DropdownMenuSeparator />}
                                            <DropdownMenuItem onClick={() => controls.onAction(action)} className={actionConfig.group === "danger" ? "text-destructive" : undefined}>
                                                {getTemplateCardActionIcon(action)}{actionConfig.label}
                                            </DropdownMenuItem>
                                        </React.Fragment>
                                    )
                                })}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                    {controls.kind === "read_only" && <Badge variant="outline" className="text-xs shrink-0"><LockIcon className="size-3 mr-1" />View Only</Badge>}
                </div>
            </CardHeader>
            <CardContent className="pt-0">
                <div className="flex items-center gap-2">
                    <Badge variant={template.is_active ? "default" : "secondary"}>{template.is_active ? "Active" : "Inactive"}</Badge>
                    <span className="text-xs text-muted-foreground">Updated {formatDate(template.updated_at)}</span>
                </div>
            </CardContent>
        </Card>
    )
}
