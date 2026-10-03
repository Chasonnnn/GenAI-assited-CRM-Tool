"use client"

import Link from "next/link"
import type { Route } from "next"
import { useState, type ReactNode } from "react"
import { ChevronDownIcon, Loader2Icon, PlusIcon } from "lucide-react"

import type { FormRoutingExactMatch, FormRoutingNoMatch, FormRoutingRead } from "@/lib/api/forms"
import { isPermissionError } from "@/lib/error-utils"
import { isDonorFormLeadKind } from "@/lib/forms/form-lead-kind"
import {
    FORM_WORKFLOW_TRIGGER_TYPES,
    ROUTING_EXACT_MATCH_OPTIONS,
    ROUTING_LEAD_SOURCE_DEFAULT,
    ROUTING_LEAD_SOURCE_OPTIONS,
    ROUTING_NO_MATCH_OPTIONS,
    getRoutingLeadSourceLabel,
    isSameSavedRouting,
    newFormWorkflowHref,
    parseRoutingLeadSource,
    pruneRoutingDraft,
    toRoutingUpdate,
    type RoutingDraft,
} from "@/lib/forms/form-routing"
import { useFormRouting, useFormWorkflows, useUpdateFormRouting } from "@/lib/hooks/use-forms"
import { cn } from "@/lib/utils"
import { getTriggerLabel } from "@/lib/workflows/workflow-editor-state"
import { QueryErrorState } from "@/components/error-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Card, CardContent } from "@/components/ui/card"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuLinkItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "@/components/ui/toast"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

type AutomationFormRoutingPanelProps = {
    formId: string | null
    /** Manage access to this form; donor forms also need donor edit access. */
    canEdit: boolean
    canCreateWorkflows: boolean
}

const TOGGLE_ITEM_CLASS = "h-9 bg-background text-muted-foreground aria-pressed:bg-muted aria-pressed:text-foreground"

function StepCard({ step, title, children }: { step: number; title: string; children: ReactNode }) {
    return (
        <Card>
            <CardContent className="space-y-4 p-5">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                    <span
                        aria-hidden="true"
                        className="flex size-5 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground"
                    >
                        {step}
                    </span>
                    {title}
                </h3>
                <div className="divide-y divide-border">{children}</div>
            </CardContent>
        </Card>
    )
}

function SettingRow({ label, labelId, htmlFor, children }: {
    label: string
    labelId?: string
    htmlFor?: string
    children: ReactNode
}) {
    return (
        <div className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
            {htmlFor ? (
                <Label id={labelId} htmlFor={htmlFor}>{label}</Label>
            ) : (
                <span id={labelId} className="text-sm font-medium">{label}</span>
            )}
            {children}
        </div>
    )
}

function OptionToggle<T extends string>({
    labelledBy,
    value,
    options,
    disabled,
    onChange,
}: {
    labelledBy: string
    value: T
    options: ReadonlyArray<{ value: T; label: string }>
    disabled: boolean
    onChange: (value: T) => void
}) {
    return (
        <ToggleGroup
            aria-labelledby={labelledBy}
            variant="outline"
            spacing={0}
            value={[value]}
            disabled={disabled}
            onValueChange={(next) => {
                const nextValue = options.find((option) => option.value === next[0])?.value
                if (nextValue) onChange(nextValue)
            }}
        >
            {options.map((option) => (
                <ToggleGroupItem key={option.value} value={option.value} className={TOGGLE_ITEM_CLASS}>
                    {option.label}
                </ToggleGroupItem>
            ))}
        </ToggleGroup>
    )
}

function NewWorkflowMenu({ formId }: { formId: string }) {
    return (
        <DropdownMenu>
            <DropdownMenuTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1")}>
                <PlusIcon aria-hidden="true" className="size-4" />
                New workflow
                <ChevronDownIcon aria-hidden="true" className="size-3.5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
                {FORM_WORKFLOW_TRIGGER_TYPES.map((triggerType) => (
                    <DropdownMenuLinkItem
                        key={triggerType}
                        render={<Link href={newFormWorkflowHref(formId, triggerType) as Route} />}
                    >
                        {getTriggerLabel(triggerType)}
                    </DropdownMenuLinkItem>
                ))}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

function FormWorkflowsCard({ formId, canCreateWorkflows }: { formId: string; canCreateWorkflows: boolean }) {
    const workflowsQuery = useFormWorkflows(formId)
    const workflows = workflowsQuery.data ?? []

    return (
        <Card>
            <CardContent className="space-y-4 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold">Workflows for this form</h3>
                    {canCreateWorkflows ? <NewWorkflowMenu formId={formId} /> : null}
                </div>
                {workflowsQuery.isLoading ? (
                    <p className="text-sm text-muted-foreground" role="status">Loading workflows…</p>
                ) : workflowsQuery.isError && workflowsQuery.data === undefined ? (
                    isPermissionError(workflowsQuery.error) ? (
                        <p className="text-sm text-muted-foreground">No access to workflows.</p>
                    ) : (
                        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
                            <p>Unable to load workflows.</p>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={workflowsQuery.isFetching}
                                onClick={() => void workflowsQuery.refetch()}
                            >
                                Retry
                            </Button>
                        </div>
                    )
                ) : workflows.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No workflows for this form.</p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Trigger</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>
                                    <span className="sr-only">Actions</span>
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {workflows.map((workflow) => (
                                <TableRow key={workflow.id}>
                                    <TableCell className="font-medium">{workflow.name}</TableCell>
                                    <TableCell>{getTriggerLabel(workflow.trigger_type)}</TableCell>
                                    <TableCell>
                                        {workflow.is_enabled ? (
                                            <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                                                Active
                                            </Badge>
                                        ) : (
                                            <Badge variant="secondary">Paused</Badge>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            aria-label={`Open ${workflow.name}`}
                                            render={<Link href={`/automation/workflows/${workflow.id}` as Route} />}
                                        >
                                            Open
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function RoutingSettings({ formId, canEdit, canCreateWorkflows }: AutomationFormRoutingPanelProps & { formId: string }) {
    const routingQuery = useFormRouting(formId)
    const updateRouting = useUpdateFormRouting()
    // Holds only changed fields, so a refetch still shows server changes to the other fields.
    const [draft, setDraft] = useState<RoutingDraft>({})
    const [draftRouting, setDraftRouting] = useState<FormRoutingRead | undefined>(routingQuery.data)
    const next = routingQuery.data
    if (next && !(draftRouting && isSameSavedRouting(next, draftRouting))) {
        setDraftRouting(next)
        // Drop edits that now match the server. A lead kind change resets every edit.
        setDraft(next.lead_kind === draftRouting?.lead_kind ? pruneRoutingDraft(draft, toRoutingUpdate(next)) : {})
    }

    if (routingQuery.isLoading) {
        return (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <Loader2Icon aria-hidden="true" className="size-4 animate-spin" />
                Loading routing…
            </p>
        )
    }

    const routing = routingQuery.data
    if (!routing) {
        return (
            <QueryErrorState
                error={routingQuery.error}
                onRetry={() => void routingQuery.refetch()}
                isRetrying={routingQuery.isFetching}
                title="Couldn't load routing"
                headingLevel={2}
            />
        )
    }

    const saved = toRoutingUpdate(routing)
    const values = { ...saved, ...draft }
    const isDirty = Object.keys(draft).length > 0
    const isDonorForm = isDonorFormLeadKind(routing.lead_kind)
    const controlsDisabled = !canEdit || updateRouting.isPending
    const update = (patch: RoutingDraft) => setDraft((current) => pruneRoutingDraft({ ...current, ...patch }, saved))

    const save = async () => {
        try {
            await updateRouting.mutateAsync({
                formId,
                // The server rejects automatic donor creation on surrogate forms.
                payload: isDonorForm ? values : { ...values, auto_create_donor: false },
            })
            setDraft({})
            toast.success("Routing saved")
        } catch (error) {
            toast.error(error instanceof Error && error.message ? error.message : "Failed to save routing")
        }
    }

    return (
        <>
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <h2 className="text-xl font-semibold tracking-tight">Routing</h2>
                    {!canEdit ? <Badge variant="secondary">Read-only</Badge> : null}
                </div>
                {canEdit ? (
                    <Button type="button" onClick={() => void save()} disabled={!isDirty || updateRouting.isPending}>
                        {updateRouting.isPending ? <Loader2Icon aria-hidden="true" className="mr-2 size-4 animate-spin" /> : null}
                        Save routing
                    </Button>
                ) : null}
            </div>

            <StepCard step={1} title="Match to an existing record">
                <SettingRow label="One exact match" labelId="routing-exact-match-label">
                    <OptionToggle<FormRoutingExactMatch>
                        labelledBy="routing-exact-match-label"
                        value={values.exact_match}
                        options={ROUTING_EXACT_MATCH_OPTIONS}
                        disabled={controlsDisabled}
                        onChange={(exact_match) => update({ exact_match })}
                    />
                </SettingRow>
                <SettingRow label="Several possible matches">
                    <Badge variant="secondary">Ambiguous match queue</Badge>
                </SettingRow>
            </StepCard>

            <StepCard step={2} title="No match">
                <SettingRow label="Create intake lead" labelId="routing-no-match-label">
                    <OptionToggle<FormRoutingNoMatch>
                        labelledBy="routing-no-match-label"
                        value={values.no_match}
                        options={ROUTING_NO_MATCH_OPTIONS}
                        disabled={controlsDisabled}
                        onChange={(no_match) => update({ no_match })}
                    />
                </SettingRow>
                <SettingRow label="Lead source" htmlFor="routing-lead-source">
                    <Select
                        value={values.lead_source ?? ROUTING_LEAD_SOURCE_DEFAULT}
                        onValueChange={(value) => update({ lead_source: parseRoutingLeadSource(value) })}
                        disabled={controlsDisabled}
                    >
                        <SelectTrigger id="routing-lead-source" className="w-full sm:w-56">
                            <SelectValue>{getRoutingLeadSourceLabel}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {ROUTING_LEAD_SOURCE_OPTIONS.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {getRoutingLeadSourceLabel(option.value)}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </SettingRow>
                {isDonorForm ? (
                    <SettingRow label="Create donor when photo scan passes" htmlFor="routing-auto-create-donor">
                        <Switch
                            id="routing-auto-create-donor"
                            checked={values.auto_create_donor}
                            onCheckedChange={(auto_create_donor) => update({ auto_create_donor })}
                            disabled={controlsDisabled}
                        />
                    </SettingRow>
                ) : null}
            </StepCard>

            <FormWorkflowsCard formId={formId} canCreateWorkflows={canCreateWorkflows} />
        </>
    )
}

export function AutomationFormRoutingPanel({ formId, canEdit, canCreateWorkflows }: AutomationFormRoutingPanelProps) {
    return (
        <div className="mx-auto max-w-5xl space-y-6">
            {formId ? (
                <RoutingSettings formId={formId} canEdit={canEdit} canCreateWorkflows={canCreateWorkflows} />
            ) : (
                <Card>
                    <CardContent className="p-6 text-sm text-stone-600">
                        Save the form before configuring routing.
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
