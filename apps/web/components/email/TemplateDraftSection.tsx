import { EditIcon, TrashIcon, UserIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { EmailTemplateDraft, EmailTemplateDraftScope } from "@/lib/api/email-template-drafts"

export function TemplateDraftSection({
    drafts,
    scope,
    canDiscard,
    onDiscard,
    onResume,
}: {
    drafts: EmailTemplateDraft[]
    scope: EmailTemplateDraftScope
    canDiscard: (draft: EmailTemplateDraft) => boolean
    onDiscard: (draft: EmailTemplateDraft) => void
    onResume: (draft: EmailTemplateDraft) => void
}) {
    if (drafts.length === 0) return null
    const headingId = `${scope}-template-drafts-heading`
    return (
        <section className="space-y-3" aria-labelledby={headingId}>
            <div>
                <h2 id={headingId} className="text-sm font-semibold">Drafts</h2>
                <p className="text-sm text-muted-foreground">Continue work without changing the published template.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {drafts.map((draft) => (
                    <Card key={draft.id}>
                        <CardHeader className="pb-2">
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0 space-y-1">
                                    <CardTitle className="truncate text-base">{draft.name}</CardTitle>
                                    <CardDescription className="line-clamp-2">{draft.subject}</CardDescription>
                                    {scope === "personal" && draft.owner_name ? <p className="flex items-center gap-1 text-xs text-muted-foreground"><UserIcon className="size-3" aria-hidden="true" />{draft.owner_name}</p> : null}
                                </div>
                                <Badge variant="secondary">{draft.template_id ? "Draft changes" : "Unpublished draft"}</Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="flex items-center justify-between gap-3">
                            <p className="text-xs text-muted-foreground">Revision {draft.revision}</p>
                            <div className="flex items-center gap-2">
                                {canDiscard(draft) ? <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" aria-label={`Discard ${draft.name}`} onClick={() => onDiscard(draft)}><TrashIcon className="mr-2 size-4" />Discard</Button> : null}
                                <Button size="sm" aria-label={`Resume ${draft.name}`} onClick={() => onResume(draft)}><EditIcon className="mr-2 size-4" />Resume</Button>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </section>
    )
}
