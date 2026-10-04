import type { Route } from "next"
import { TrashIcon } from "lucide-react"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"
import {
    TemplateCardMenuTrigger,
    TemplateCardMeta,
    TemplateCardSubject,
    getTemplateDraftLabel,
    templateCardClassName,
    templateCardLinkClassName,
    templateCardTitleClassName,
    templateChipClassName,
} from "@/components/email/TemplateCard"
import type { EmailTemplateDraft } from "@/lib/api/email-template-drafts"

export function getTemplateDraftHref(draft: EmailTemplateDraft): Route {
    return `/automation/email-templates/${draft.scope}/${draft.template_id ?? draft.id}` as Route
}

/** A draft with no visible published template: unpublished, or its template is hidden by a filter. */
export function TemplateDraftCard({
    draft,
    onDiscard,
}: {
    draft: EmailTemplateDraft
    onDiscard?: (() => void) | undefined
}) {
    const href = getTemplateDraftHref(draft)
    return (
        <Card className={templateCardClassName}>
            <div className="flex items-start gap-2 px-4">
                <h3 className={templateCardTitleClassName}>
                    <Link
                        href={href}
                        fallbackMode="router"
                        aria-label={`Resume ${draft.name}`}
                        className={templateCardLinkClassName}
                    >
                        {draft.name}
                    </Link>
                </h3>
                {onDiscard ? (
                    <DropdownMenu>
                        <TemplateCardMenuTrigger name={draft.name} />
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem className="text-destructive" onClick={onDiscard}>
                                <TrashIcon className="mr-2 size-4" />
                                Discard draft
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                ) : null}
            </div>
            <TemplateCardSubject subject={draft.subject} />
            <div className="flex flex-wrap items-center gap-1.5 px-4">
                <Badge variant="outline" className={templateChipClassName.draft}>
                    {getTemplateDraftLabel(draft)}
                </Badge>
            </div>
            <TemplateCardMeta ownerName={draft.scope === "personal" ? draft.owner_name : null} updatedAt={draft.updated_at} />
        </Card>
    )
}
