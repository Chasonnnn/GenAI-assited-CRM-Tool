"use client"

import { useRef, useState } from "react"
import { CheckIcon, ClipboardCheckIcon, MessageCircleIcon, MinusIcon, XIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import { InlineSelectField } from "@/components/records/RecordProfileFields"
import { InlineEditField } from "@/components/inline-edit-field"
import { useRecordEditing } from "@/components/records/RecordEditingContext"
import type { DonorChecklistItem } from "@/lib/types/donor-profile"
import type { DonorUpdate } from "@/lib/types/donor"

export function DonorChecklistAnswer({ item, onSave }: {
    item: DonorChecklistItem
    onSave: (value: string | null) => Promise<void>
}) {
    const canEdit = useRecordEditing()
    const saving = useRef(false)
    const [pending, setPending] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const values = [null, ...item.options.map(option => option.value)]
    const nextValue = values[(values.indexOf(item.value) + 1) % values.length] ?? null
    const label = item.options.find(option => option.value === item.value)?.label ?? item.value ?? "Not answered"
    const Icon = item.value === "Yes" ? CheckIcon : item.value === "No" ? XIcon : item.value ? MessageCircleIcon : MinusIcon
    const changeAnswer = async () => {
        if (!canEdit || saving.current) return
        saving.current = true
        setPending(true)
        setError(null)
        await onSave(nextValue)
            .catch(() => setError("Unable to save answer. Try again."))
            .finally(() => { saving.current = false; setPending(false) })
    }
    return <div className="min-w-0">
        <Button unstyled type="button" disabled={!canEdit || pending} onClick={() => { void changeAnswer() }}
            aria-label={`${item.label}: ${label}.${canEdit ? " Click to change." : ""}`}
            aria-busy={pending}
            className="flex min-w-0 items-center gap-2 rounded px-1 py-0.5 text-left text-sm hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default">
            <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span>{label}</span>
        </Button>
        {error && <p role="alert" className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
}

export function DonorEligibilityChecklist({ items, onUpdate }: {
    items: DonorChecklistItem[]
    onUpdate: (data: DonorUpdate) => Promise<void>
}) {
    return <SurrogateOverviewCard title="Eligibility Checklist" icon={ClipboardCheckIcon}>
        {items.length === 0 && <p className="text-sm text-muted-foreground">No screening questions in the submitted form.</p>}
        {items.map(item => <div key={item.key} className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-center">
            <Tooltip>
                <TooltipTrigger render={<Button unstyled type="button" className="text-left text-sm text-muted-foreground" />}>
                    {item.label}:
                </TooltipTrigger>
                <TooltipContent className="max-w-72">{item.question}</TooltipContent>
            </Tooltip>
            {item.key === "education" && item.options.length > 0
                ? <InlineSelectField label={item.label} value={item.value} options={item.options} placeholder="Not answered" onSave={value => onUpdate({ [item.key]: value })} triggerClassName="w-full" />
                : item.options.length > 0
                    ? <DonorChecklistAnswer item={item} onSave={value => onUpdate({ [item.key]: value })} />
                    : <InlineEditField label={item.label} value={item.value} placeholder="Not answered" onSave={value => onUpdate({ [item.key]: value || null })} />}
        </div>)}
    </SurrogateOverviewCard>
}
