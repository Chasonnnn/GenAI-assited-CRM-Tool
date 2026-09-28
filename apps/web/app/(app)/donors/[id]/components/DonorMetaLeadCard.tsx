"use client"

import type * as React from "react"
import { Loader2Icon, MegaphoneIcon } from "lucide-react"

import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import { Button } from "@/components/ui/button"
import { getSurrogateFieldLabel } from "@/lib/constants/surrogate-field-labels"
import { formatDateTime } from "@/lib/formatters"
import { useDonorMetaLead } from "@/lib/hooks/use-donors"
import { humanizeSelectKey } from "@/lib/select-labels"

function getAnswerLabel(answer: { key: string; label: string | null }): string {
    return answer.label || humanizeSelectKey(answer.key) || answer.key
}

/** Read-only answers of the Meta lead the donor was converted from. */
export function DonorMetaLeadCard({ donorId, enabled }: { donorId: string; enabled: boolean }) {
    const metaLeadQuery = useDonorMetaLead(enabled ? donorId : null)
    if (!enabled) return null
    const card = (children: React.ReactNode) => (
        <SurrogateOverviewCard title="Meta Lead" icon={MegaphoneIcon}>{children}</SurrogateOverviewCard>
    )
    if (metaLeadQuery.isLoading) {
        return card(
            <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                Loading…
            </div>,
        )
    }
    if (metaLeadQuery.isError) {
        return card(
            <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="text-muted-foreground">Couldn&apos;t load the Meta lead.</span>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={() => { void metaLeadQuery.refetch() }}
                    disabled={metaLeadQuery.isFetching}
                >
                    Try again
                </Button>
            </div>,
        )
    }
    const lead = metaLeadQuery.data
    if (!lead) return null
    const droppedLabels = lead.dropped_fields.map(
        (field) => getSurrogateFieldLabel(field) ?? humanizeSelectKey(field) ?? "Unknown field",
    )
    return card(
        <>
            <dl className="grid gap-3 text-sm">
                <div className="min-w-0">
                    <dt className="text-muted-foreground">Form</dt>
                    <dd className="break-words">{lead.form_name || "Unknown form"}</dd>
                </div>
                <div className="min-w-0">
                    <dt className="text-muted-foreground">Submitted</dt>
                    <dd>{formatDateTime(lead.meta_created_time ?? lead.received_at, "—")}</dd>
                </div>
                {droppedLabels.length > 0 ? (
                    <div className="min-w-0">
                        <dt className="text-muted-foreground">Not saved (invalid value)</dt>
                        <dd>{droppedLabels.join(", ")}</dd>
                    </div>
                ) : null}
            </dl>
            {lead.answers.length > 0 ? (
                <dl className="grid gap-3 border-t pt-3 text-sm" aria-label="Meta lead answers">
                    {lead.answers.map((answer) => (
                        <div key={answer.key} className="min-w-0">
                            <dt className="text-muted-foreground">{getAnswerLabel(answer)}</dt>
                            <dd className="break-words">{answer.value}</dd>
                        </div>
                    ))}
                </dl>
            ) : null}
        </>,
    )
}
