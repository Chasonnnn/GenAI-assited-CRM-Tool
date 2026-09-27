"use client"

import { CircleAlertIcon, CircleCheckIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { BuilderPaletteField } from "@/lib/forms/form-builder-library"
import type { PublishReadinessItem, PublishReadinessStatus } from "@/lib/forms/form-publish-readiness"
import { cn } from "@/lib/utils"

const STATUS_LABELS: Record<PublishReadinessStatus, string> = {
    ready: "Added",
    missing: "Missing",
    not_required: "Not required",
    wrong_type: "Wrong field type",
}

type FormPublishReadinessProps = {
    items: PublishReadinessItem[]
    onAddField: (field: BuilderPaletteField) => void
    onMarkRequired: (fieldId: string) => void
}

export function FormPublishReadiness({ items, onAddField, onMarkRequired }: FormPublishReadinessProps) {
    return (
        <section
            aria-labelledby="form-publish-readiness-title"
            className="space-y-3 rounded-2xl border border-border/70 bg-background p-4"
        >
            <h4 id="form-publish-readiness-title" className="text-sm font-semibold text-foreground">
                Required to publish
            </h4>
            <ul className="space-y-1">
                {items.map((item) => {
                    const ready = item.status === "ready"
                    const StatusIcon = ready ? CircleCheckIcon : CircleAlertIcon
                    return (
                        <li key={item.key} className="flex min-h-8 items-center justify-between gap-3 text-sm">
                            <span className="flex min-w-0 items-center gap-2">
                                <StatusIcon
                                    aria-hidden="true"
                                    className={cn("size-4 shrink-0", ready ? "text-primary" : "text-destructive")}
                                />
                                <span className={cn("truncate", ready && "text-muted-foreground")}>{item.label}</span>
                                <span className="sr-only">{STATUS_LABELS[item.status]}</span>
                            </span>
                            <ReadinessAction item={item} onAddField={onAddField} onMarkRequired={onMarkRequired} />
                        </li>
                    )
                })}
            </ul>
        </section>
    )
}

function ReadinessAction({
    item,
    onAddField,
    onMarkRequired,
}: {
    item: PublishReadinessItem
} & Pick<FormPublishReadinessProps, "onAddField" | "onMarkRequired">) {
    const { addField, fieldId } = item
    if (item.status === "missing" && addField) {
        return (
            <Button
                variant="outline"
                size="sm"
                className="h-7 shrink-0"
                aria-label={`Add ${item.label} to form`}
                onClick={() => onAddField(addField)}
            >
                Add
            </Button>
        )
    }
    if (item.status === "not_required" && fieldId) {
        return (
            <Button
                variant="outline"
                size="sm"
                className="h-7 shrink-0"
                aria-label={`Mark ${item.label} required`}
                onClick={() => onMarkRequired(fieldId)}
            >
                Mark required
            </Button>
        )
    }
    if (item.status === "ready") return null
    return (
        <span aria-hidden="true" className="shrink-0 text-xs text-destructive">
            {STATUS_LABELS[item.status]}
        </span>
    )
}
