import { Button } from "@/components/ui/button"
import { DialogBody, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Loader2Icon, CheckCircleIcon } from "lucide-react"
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import type { Pipeline, StageSemantics } from "@/lib/api/pipelines"
import type { ZapierStageBucket, ZapierOutboundEvent } from "@/lib/api/zapier"
import { getStageSemantics } from "@/lib/surrogate-stage-context"
import { humanizeSelectKey } from "@/lib/select-labels"

export const ZAPIER_BUCKET_EVENT_NAME: Record<ZapierStageBucket, string> = {
    qualified: "Qualified",
    converted: "Converted",
    lost: "Lost",
    not_qualified: "Not Qualified",
}

const ZAPIER_BUCKET_OPTIONS: Array<{ value: ZapierStageBucket; label: string }> = [
    { value: "qualified", label: "Qualified" },
    { value: "converted", label: "Converted" },
    { value: "lost", label: "Lost" },
    { value: "not_qualified", label: "Not Qualified" },
]

export const UNTRACKED_BUCKET_VALUE = "__none__"

export const isZapierStageBucket = (value: unknown): value is ZapierStageBucket =>
    value === "qualified" ||
    value === "converted" ||
    value === "lost" ||
    value === "not_qualified"

type StageEventMappingLike = {
    stage_key: string
    event_name: string
    enabled: boolean
    bucket?: ZapierStageBucket | null
}

function buildDefaultStageEventMappingItem<T extends StageEventMappingLike>(
    stageKey: string,
    bucket: ZapierStageBucket | null,
): T {
    if (bucket) {
        return {
            stage_key: stageKey,
            event_name: ZAPIER_BUCKET_EVENT_NAME[bucket],
            enabled: true,
            bucket,
        } as T
    }
    return {
        stage_key: stageKey,
        event_name: "",
        enabled: false,
        bucket: null,
    } as T
}

export function mergeEventMappingWithPipelineStages<T extends StageEventMappingLike>(
    eventMapping: T[] | null | undefined,
    pipelines: Pipeline[] | null | undefined,
): T[] {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    if (!defaultPipeline?.stages?.length) {
        return [...(eventMapping ?? [])]
    }

    const byStageKey = new Map((eventMapping ?? []).map((item) => [item.stage_key, item]))
    const merged: T[] = []

    for (const stage of defaultPipeline.stages) {
        if (stage.is_active === false) continue
        const stageKey = (stage.stage_key ?? stage.slug ?? "").trim()
        if (!stageKey) continue

        const existing = byStageKey.get(stageKey)
        if (existing) {
            merged.push(existing)
            continue
        }

        const stageBucket = getStageSemantics(stage).integration_bucket
        merged.push(
            buildDefaultStageEventMappingItem(
                stageKey,
                isZapierStageBucket(stageBucket) ? stageBucket : null,
            ) as T,
        )
    }

    return merged
}

export function buildRecommendedBucketByStage(
    pipelines:
        | Array<{
            is_default?: boolean
            stages?: Array<{
                stage_key?: string
                slug?: string
                is_active?: boolean
                semantics?: Partial<StageSemantics>
                stage_type?: string
            }>
        }>
        | null
        | undefined,
): Record<string, ZapierStageBucket> {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    if (!defaultPipeline?.stages?.length) {
        return {}
    }

    const mapping: Record<string, ZapierStageBucket> = {}
    for (const stage of defaultPipeline.stages) {
        if (stage.is_active === false) continue
        const stageKey = (stage.stage_key ?? stage.slug ?? "").trim()
        if (!stageKey) continue
        const bucket = getStageSemantics(stage).integration_bucket
        if (isZapierStageBucket(bucket)) {
            mapping[stageKey] = bucket
        }
    }
    return mapping
}

export function buildStageLabelByKey(pipelines: Pipeline[] | null | undefined): Record<string, string> {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    if (!defaultPipeline?.stages?.length) {
        return {}
    }

    const labels: Record<string, string> = {}
    for (const stage of defaultPipeline.stages) {
        if (stage.is_active === false) continue
        const stageKey = (stage.stage_key ?? stage.slug ?? "").trim()
        const stageLabel = stage.label?.trim()
        if (!stageKey || !stageLabel) continue
        labels[stageKey] = stageLabel
    }

    return labels
}

export function getSelectOptionLabel(
    options: ReadonlyArray<{ value: string; label: string }>,
    value: string | null | undefined,
): string {
    if (!value) return ""
    return options.find((option) => option.value === value)?.label ?? ""
}

function getBucketSelectLabel(value: string | null | undefined): string {
    if (value === UNTRACKED_BUCKET_VALUE) return "Not Tracked"
    return getSelectOptionLabel(ZAPIER_BUCKET_OPTIONS, value)
}

export const ZAPIER_OUTBOUND_STATUS_BADGE: Record<
    ZapierOutboundEvent["status"],
    { label: string; variant: "default" | "secondary" | "destructive" }
> = {
    queued: { label: "Queued", variant: "secondary" },
    delivered: { label: "Delivered", variant: "default" },
    failed: { label: "Failed", variant: "destructive" },
    skipped: { label: "Skipped", variant: "secondary" },
}

export function formatZapierRate(rate: number): string {
    return `${Math.round(rate * 100)}%`
}

const ZAPIER_SOURCE_LABELS: Record<string, string> = {
    automatic: "Automatic",
    workflow: "Workflow",
    test: "Test",
}

const ZAPIER_SKIP_REASON_LABELS: Record<string, string> = {
    duplicate: "Already sent",
    not_meta_source: "Not a Meta lead",
    missing_meta_lead_fk: "No linked Meta lead",
    missing_meta_lead: "Meta lead not found",
    missing_meta_lead_id: "Meta lead ID missing",
    synthetic_meta_lead_id: "Not a real Meta lead ID",
    stale_meta_lead: "Meta lead older than 90 days",
    outbound_disabled: "Surrogate reporting disabled",
    missing_webhook_url: "Webhook URL missing",
    unmapped_stage: "Stage not mapped",
    unmapped_donor_stage: "Stage not mapped",
    donor_outbound_disabled: "Donor reporting disabled",
    donor_stage_undo: "Undo of an earlier change",
    donor_stage_undone: "Withdrawn by undo",
    missing_donor_attribution: "No Meta lead or website form",
    missing_matching_data: "No click ID or contact data",
    donor_dispatch_disabled: "Donor reporting disabled before sending",
    donor_dispatch_url_missing: "Webhook URL removed before sending",
    donor_event_invalid: "Invalid event record",
    donor_subject_missing: "Donor stage change not found",
    donor_attribution_missing: "Attribution no longer linked",
    donor_stage_inactive: "Stage no longer active",
    donor_mapping_changed: "Mapping changed before sending",
    donor_config_changed: "Configuration changed before sending",
}

export function formatZapierSource(source: string): string {
    return ZAPIER_SOURCE_LABELS[source] ?? humanizeSelectKey(source) ?? "Other"
}

export function formatZapierReason(reason: string | null | undefined): string {
    if (!reason) return "—"
    return ZAPIER_SKIP_REASON_LABELS[reason] ?? humanizeSelectKey(reason) ?? "Other reason"
}

/** Loading body and footer shared by the sectioned integration dialogs. */
export function IntegrationDialogLoadingState() {
    return (
        <>
            <DialogBody>
                <div role="status" className="flex items-center justify-center py-8">
                    <Loader2Icon
                        className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground"
                        aria-hidden="true"
                    />
                    <span className="sr-only">Loading</span>
                </div>
            </DialogBody>
            <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
            </DialogFooter>
        </>
    )
}

/**
 * Stage → event bucket table shared by the Meta CRM dataset and the Zapier surrogate mapping.
 * A tracked bucket fixes the event name; "Not Tracked" rows take a custom event name.
 */
export function StageEventMappingTable<T extends StageEventMappingLike>({
    items,
    namePrefix,
    getStageKeyLabel,
    getSendLabel,
    getUntrackedEnabled,
    onChange,
}: {
    items: T[]
    namePrefix: string
    getStageKeyLabel: (stageKey: string) => string
    getSendLabel: (stageLabel: string) => string
    /** Send state after a row is set to Not Tracked. */
    getUntrackedEnabled: (item: T) => boolean
    onChange: (next: T[]) => void
}) {
    const updateItem = (index: number, updater: (existing: T) => T) => {
        const existing = items[index]
        if (!existing) return
        const next = [...items]
        next[index] = updater(existing)
        onChange(next)
    }

    return (
        <div className="rounded-lg border">
            <Table className="min-w-[36rem]">
                <TableHeader>
                    <TableRow>
                        <TableHead>Stage</TableHead>
                        <TableHead className="w-48">Event bucket</TableHead>
                        <TableHead className="w-56">Event name</TableHead>
                        <TableHead className="w-16 text-center">Send</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {items.map((item, index) => {
                        const stageLabel = getStageKeyLabel(item.stage_key)
                        const tracked = isZapierStageBucket(item.bucket)
                        return (
                            <TableRow key={item.stage_key}>
                                <TableCell className="whitespace-normal font-medium">{stageLabel}</TableCell>
                                <TableCell>
                                    <Select
                                        value={tracked ? item.bucket : UNTRACKED_BUCKET_VALUE}
                                        onValueChange={(value) => {
                                            if (value === UNTRACKED_BUCKET_VALUE) {
                                                updateItem(index, (existing) => ({
                                                    ...existing,
                                                    bucket: null,
                                                    enabled: getUntrackedEnabled(existing),
                                                }))
                                            } else if (isZapierStageBucket(value)) {
                                                updateItem(index, (existing) => ({
                                                    ...existing,
                                                    bucket: value,
                                                    event_name: ZAPIER_BUCKET_EVENT_NAME[value],
                                                    enabled: true,
                                                }))
                                            }
                                        }}
                                    >
                                        <SelectTrigger
                                            size="sm"
                                            className="w-full"
                                            aria-label={`Event bucket for ${stageLabel}`}
                                        >
                                            <SelectValue placeholder="Bucket">
                                                {(value: string | null) => getBucketSelectLabel(value)}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value={UNTRACKED_BUCKET_VALUE}>
                                                {getBucketSelectLabel(UNTRACKED_BUCKET_VALUE)}
                                            </SelectItem>
                                            {ZAPIER_BUCKET_OPTIONS.map((option) => (
                                                <SelectItem key={option.value} value={option.value}>
                                                    {option.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </TableCell>
                                <TableCell>
                                    {tracked ? (
                                        <span className="text-muted-foreground">{item.event_name}</span>
                                    ) : (
                                        <Input
                                            value={item.event_name}
                                            onChange={(event) => {
                                                const eventName = event.target.value
                                                updateItem(index, (existing) => ({ ...existing, event_name: eventName }))
                                            }}
                                            placeholder="Event name"
                                            aria-label={`Event name for ${stageLabel}`}
                                            name={`${namePrefix}-event-${item.stage_key}`}
                                            autoComplete="off"
                                            className="h-8"
                                        />
                                    )}
                                </TableCell>
                                <TableCell>
                                    <div className="flex justify-center">
                                        <Checkbox
                                            checked={item.enabled}
                                            onCheckedChange={(checked) => {
                                                updateItem(index, (existing) => ({ ...existing, enabled: checked === true }))
                                            }}
                                            aria-label={getSendLabel(stageLabel)}
                                        />
                                    </div>
                                </TableCell>
                            </TableRow>
                        )
                    })}
                </TableBody>
            </Table>
        </div>
    )
}

export type BadgeVariant = "default" | "secondary" | "destructive"
export type IconComponent = typeof CheckCircleIcon
