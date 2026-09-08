"use client"

import { useId } from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { usePipelines } from "@/lib/hooks/use-pipelines"
import type { RecordModule, RecordScopeRule } from "@/lib/api/record-scopes"

export const ROLE_LABELS: Record<string, string> = {
    intake_specialist: "Intake Specialist", case_manager: "Case Manager", operations: "Operations", admin: "Admin", developer: "Dev",
}
export const MODULE_LABELS: Record<RecordModule, string> = { surrogates: "Surrogates", donors: "Donors", intended_parents: "Intended Parents" }
export const ASSIGNMENT_LABELS = { all: "All records", assigned: "Assigned records", none: "No role access" }
export const PHASE_LABELS = { all: "All phases", pre_approval: "Before approval", post_approval: "After approval" }
export const emptyScope: RecordScopeRule = { assignment: "none", phase: "all", stage_ids: [] }

export function PermissionLoading() {
    return <div role="status" className="flex items-center gap-2 p-8 text-muted-foreground"><Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />Loading permissions…</div>
}

export function PermissionError({ error, retry }: { error: unknown; retry?: () => void }) {
    return <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        <p>{error instanceof Error ? error.message : "Unable to load permissions."}</p>
        {retry && <Button variant="outline" size="sm" className="mt-3" onClick={retry}>Try again</Button>}
    </div>
}

export function ChoiceField<T extends string>({ label, value, options, onChange, disabled = false, placeholder = "Select" }: {
    label: string; value: T | ""; options: Partial<Record<T, string>>; onChange: (value: T) => void; disabled?: boolean; placeholder?: string
}) {
    const id = useId()
    return <div className="space-y-2">
        <label htmlFor={id} className="text-sm font-medium">{label}</label>
        <Select value={value || null} onValueChange={(next) => { if (next !== null) onChange(next as T) }} disabled={disabled}>
            <SelectTrigger id={id} className="w-full rounded-xl"><SelectValue placeholder={placeholder}>{(current: string | null) => current ? options[current as T] ?? placeholder : placeholder}</SelectValue></SelectTrigger>
            <SelectContent>{(Object.entries(options) as [T, string][]).map(([key, text]) => <SelectItem key={key} value={key}>{text}</SelectItem>)}</SelectContent>
        </Select>
    </div>
}

export function scopeLabel(rule: RecordScopeRule) {
    if (rule.assignment === "none") return ASSIGNMENT_LABELS.none
    return `${ASSIGNMENT_LABELS[rule.assignment]} · ${PHASE_LABELS[rule.phase]}${rule.stage_ids.length ? ` · ${rule.stage_ids.length} selected stages` : ""}`
}

export function ScopeFields({ module, rule, onChange, disabled = false, addition = false }: {
    module: RecordModule; rule: RecordScopeRule; onChange: (rule: RecordScopeRule) => void; disabled?: boolean; addition?: boolean
}) {
    const surrogate = usePipelines("surrogate", module === "surrogates")
    const egg = usePipelines("egg_donor", module === "donors")
    const sperm = usePipelines("sperm_donor", module === "donors")
    const pipelines = module === "surrogates" ? surrogate.data ?? [] : module === "donors" ? [...(egg.data ?? []), ...(sperm.data ?? [])] : []
    const loading = module === "surrogates" ? surrogate.isLoading : module === "donors" && (egg.isLoading || sperm.isLoading)
    const error = module === "surrogates" ? surrogate.error : module === "donors" ? egg.error || sperm.error : null
    const stages = pipelines.flatMap((pipeline) => pipeline.stages.map((stage) => ({ id: stage.id, label: stage.label, pipeline: pipeline.name })))
    const assignments = addition ? { all: "All records", assigned: "Assigned records" } : ASSIGNMENT_LABELS
    return <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
            <ChoiceField label="Assignment" value={rule.assignment} options={assignments} onChange={(assignment) => onChange({ ...rule, assignment })} disabled={disabled} />
            <ChoiceField label="Phase" value={rule.phase} options={PHASE_LABELS} onChange={(phase) => onChange({ ...rule, phase })} disabled={disabled || module === "intended_parents" || rule.assignment === "none"} />
        </div>
        {module !== "intended_parents" && rule.assignment !== "none" && <details className="rounded-xl border p-3">
            <summary className="cursor-pointer text-sm font-medium">Specific stages{rule.stage_ids.length ? ` (${rule.stage_ids.length})` : ""}</summary>
            <p className="mt-3 text-xs text-muted-foreground">No selection includes every stage in the selected phase.</p>
            {loading && <PermissionLoading />}
            {error && <PermissionError error={error} />}
            {!loading && !error && stages.length === 0 && <p className="mt-3 text-sm text-muted-foreground">No pipeline stages available.</p>}
            <div className="mt-3 max-h-52 space-y-3 overflow-y-auto">{stages.map((stage) => <label key={stage.id} className="flex cursor-pointer items-center gap-3 text-sm">
                <Checkbox disabled={disabled} checked={rule.stage_ids.includes(stage.id)} onCheckedChange={(checked) => onChange({ ...rule, stage_ids: checked ? [...rule.stage_ids, stage.id] : rule.stage_ids.filter((id) => id !== stage.id) })} />
                <span>{stage.label}<span className="ml-2 text-xs text-muted-foreground">{stage.pipeline}</span></span>
            </label>)}</div>
        </details>}
    </div>
}
