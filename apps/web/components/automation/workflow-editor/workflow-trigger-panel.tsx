"use client"

import { XIcon, ZapIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { WorkflowSubjectType } from "@/lib/api/workflows"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import {
    WORKFLOW_SUBJECT_LABELS,
    getConditionFieldLabel,
    getTriggerLabel,
    withIntakeTriggerForm,
} from "@/lib/workflows/workflow-editor-state"
import {
    APPLICANT_TYPE_BOTH,
    APPLICANT_TYPE_OPTIONS,
    getApplicantTypeLabel,
    isDonorLeadKind,
} from "@/components/automation/workflow-editor/shared"
import { InspectorPanel, InspectorSection } from "./inspector-section"
import { NodeIcon } from "./node-meta"

export function WorkflowTriggerPanel({ controller }: { controller: WorkflowEditorController }) {
    const { state, options, handlers, isEditing, createWorkflowSubjectOptions } = controller
    const { subjectType, triggerType, triggerConfig, workflowDescription } = state
    const {
        triggerTypeOptions,
        formOptions,
        statusOptions,
        activeStatusOptions,
        userOptions,
        availableConditionFields,
        selectedTriggerFields,
        isSharedDonorTriggerForm,
        configuredIntakeLeadKind,
    } = options
    const { setSubjectType, setTriggerType, setTriggerConfig, setIntakeApplicantType, setWorkflowDescription } = handlers

    return (
        <InspectorPanel title="Triggers" icon={<NodeIcon icon={ZapIcon} tone="violet" size="sm" />}>
            <InspectorSection title="Workflow will target">
                {isEditing ? (
                    <div className="flex items-center gap-2 text-sm">
                        <Badge variant="outline">{WORKFLOW_SUBJECT_LABELS[subjectType]}</Badge>
                    </div>
                ) : (
                    <RadioGroup
                        aria-label="Record type"
                        value={subjectType}
                        onValueChange={(value) => value && setSubjectType(value as WorkflowSubjectType)}
                        className="gap-2"
                    >
                        {createWorkflowSubjectOptions.map((option) => (
                            <label key={option.value} className="flex cursor-pointer items-center gap-2.5 text-sm">
                                <RadioGroupItem value={option.value} aria-label={option.label} />
                                <span>{option.label}</span>
                            </label>
                        ))}
                    </RadioGroup>
                )}
            </InspectorSection>

            <InspectorSection title="Run this workflow">
                <div className="grid gap-1.5">
                    <Label htmlFor="workflow-trigger-type">Trigger</Label>
                    <Select aria-label="Trigger type" value={triggerType} onValueChange={(value) => value && setTriggerType(value)}>
                        <SelectTrigger id="workflow-trigger-type" aria-label="Trigger type" className="w-full">
                            <SelectValue placeholder="Select trigger">
                                {(value: string | null) => {
                                    if (!value) return "Select trigger"
                                    const trigger = triggerTypeOptions.find((option) => option.value === value)
                                    return trigger?.label ?? getTriggerLabel(value)
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="min-w-[280px]">
                            {triggerTypeOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {(triggerType === "status_changed" || triggerType === "donor_stage_changed") && (
                    <>
                        <div className="grid gap-1.5">
                            <Label>To Stage (Optional)</Label>
                            <Select
                                value={typeof triggerConfig.to_stage_id === "string" ? triggerConfig.to_stage_id : ""}
                                onValueChange={(value) =>
                                    setTriggerConfig((currentConfig) => ({ ...currentConfig, to_stage_id: value }))
                                }
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Any stage">
                                        {(value: string | null) => {
                                            if (!value) return "Any stage"
                                            const status = statusOptions.find((option) => option.id === value)
                                            return status?.label ?? "Unknown stage"
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="">Any stage</SelectItem>
                                    {activeStatusOptions.map((option) => (
                                        <SelectItem key={option.id ?? option.value} value={option.id ?? option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="grid gap-1.5">
                            <Label>From Stage (Optional)</Label>
                            <Select
                                value={typeof triggerConfig.from_stage_id === "string" ? triggerConfig.from_stage_id : ""}
                                onValueChange={(value) =>
                                    setTriggerConfig((currentConfig) => ({ ...currentConfig, from_stage_id: value }))
                                }
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Any stage">
                                        {(value: string | null) => {
                                            if (!value) return "Any stage"
                                            const status = statusOptions.find((option) => option.id === value)
                                            return status?.label ?? "Unknown stage"
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="">Any stage</SelectItem>
                                    {statusOptions.map((option) => (
                                        <SelectItem key={option.id ?? option.value} value={option.id ?? option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </>
                )}

                {triggerType === "scheduled" && (
                    <>
                        <div className="grid gap-1.5">
                            <Label htmlFor="workflow-trigger-cron">Cron Schedule *</Label>
                            <Input
                                id="workflow-trigger-cron"
                                placeholder="0 9 * * 1"
                                value={typeof triggerConfig.cron === "string" ? triggerConfig.cron : ""}
                                onChange={(event) =>
                                    setTriggerConfig((currentConfig) => ({ ...currentConfig, cron: event.target.value }))
                                }
                            />
                        </div>
                        <div className="grid gap-1.5">
                            <Label htmlFor="workflow-trigger-timezone">Timezone</Label>
                            <Input
                                id="workflow-trigger-timezone"
                                placeholder="America/Los_Angeles"
                                value={
                                    typeof triggerConfig.timezone === "string"
                                        ? triggerConfig.timezone
                                        : "America/Los_Angeles"
                                }
                                onChange={(event) =>
                                    setTriggerConfig((currentConfig) => ({
                                        ...currentConfig,
                                        timezone: event.target.value,
                                    }))
                                }
                            />
                        </div>
                    </>
                )}

                {triggerType === "inactivity" && (
                    <div className="grid gap-1.5">
                        <Label htmlFor="workflow-trigger-days">Days Inactive *</Label>
                        <Input
                            id="workflow-trigger-days"
                            type="number"
                            min={1}
                            max={90}
                            value={typeof triggerConfig.days === "number" ? triggerConfig.days : 7}
                            onChange={(event) =>
                                setTriggerConfig((currentConfig) => ({
                                    ...currentConfig,
                                    days: Number(event.target.value),
                                }))
                            }
                        />
                    </div>
                )}

                {(triggerType === "form_started" ||
                    triggerType === "form_submitted" ||
                    triggerType === "intake_lead_created") && (
                    <div className="grid gap-1.5">
                        <Label>Form *</Label>
                        <Select
                            value={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                            onValueChange={(value) =>
                                setTriggerConfig((currentConfig) =>
                                    triggerType === "form_started"
                                        ? { ...currentConfig, form_id: value }
                                        : withIntakeTriggerForm(triggerType, currentConfig, value),
                                )
                            }
                        >
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select form">
                                    {(value: string | null) => {
                                        if (!value) return "Select form"
                                        const form = formOptions.find((option) => option.value === value)
                                        return form?.label ?? "Unknown form"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {formOptions.map((form) => (
                                    <SelectItem key={form.value} value={form.value}>
                                        {form.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {formOptions.length === 0 && (
                            <p className="text-xs text-muted-foreground">Publish a form to use this trigger.</p>
                        )}
                    </div>
                )}

                {isSharedDonorTriggerForm && (
                    <div className="grid gap-1.5">
                        <Label>Applicant Type</Label>
                        <Select
                            aria-label="Applicant Type"
                            value={isDonorLeadKind(configuredIntakeLeadKind) ? configuredIntakeLeadKind : APPLICANT_TYPE_BOTH}
                            onValueChange={setIntakeApplicantType}
                        >
                            <SelectTrigger aria-label="Applicant Type" className="w-full">
                                <SelectValue>{getApplicantTypeLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {APPLICANT_TYPE_OPTIONS.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {getApplicantTypeLabel(option.value)}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}

                {triggerType === "task_due" && (
                    <div className="grid gap-1.5">
                        <Label htmlFor="workflow-trigger-hours">Hours Before Due *</Label>
                        <Input
                            id="workflow-trigger-hours"
                            type="number"
                            min={1}
                            max={168}
                            value={typeof triggerConfig.hours_before === "number" ? triggerConfig.hours_before : 24}
                            onChange={(event) =>
                                setTriggerConfig((currentConfig) => ({
                                    ...currentConfig,
                                    hours_before: Number(event.target.value),
                                }))
                            }
                        />
                    </div>
                )}

                {(triggerType === "surrogate_updated" || triggerType === "donor_updated") && (
                    <div className="grid gap-2">
                        <Label>Fields to Watch *</Label>
                        <Select
                            value=""
                            onValueChange={(value) => {
                                if (!value || selectedTriggerFields.includes(value)) return
                                setTriggerConfig((currentConfig) => {
                                    const currentFields = Array.isArray(currentConfig.fields)
                                        ? currentConfig.fields.filter((field): field is string => typeof field === "string")
                                        : []
                                    return { ...currentConfig, fields: [...currentFields, value] }
                                })
                            }}
                        >
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select field to add">
                                    {(value: string | null) => (value ? getConditionFieldLabel(value) : "Select field to add")}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {availableConditionFields.map((field) => (
                                    <SelectItem key={field} value={field}>
                                        {getConditionFieldLabel(field)}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {selectedTriggerFields.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                                {selectedTriggerFields.map((field) => (
                                    <Badge key={field} variant="secondary" className="gap-1">
                                        {getConditionFieldLabel(field)}
                                        <Button
                                            unstyled
                                            type="button"
                                            className="ml-0.5 text-xs"
                                            aria-label="Remove field"
                                            onClick={() =>
                                                setTriggerConfig((currentConfig) => {
                                                    const currentFields = Array.isArray(currentConfig.fields)
                                                        ? currentConfig.fields.filter(
                                                            (item): item is string => typeof item === "string" && item !== field,
                                                        )
                                                        : []
                                                    return { ...currentConfig, fields: currentFields }
                                                })
                                            }
                                        >
                                            <XIcon className="size-3" />
                                        </Button>
                                    </Badge>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {(triggerType === "surrogate_assigned" || triggerType === "donor_assigned") && (
                    <div className="grid gap-1.5">
                        <Label>Assigned To (Optional)</Label>
                        <Select
                            value={typeof triggerConfig.to_user_id === "string" ? triggerConfig.to_user_id : ""}
                            onValueChange={(value) =>
                                setTriggerConfig((currentConfig) => ({ ...currentConfig, to_user_id: value || null }))
                            }
                        >
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Any user">
                                    {(value: string | null) => {
                                        if (!value) return "Any user"
                                        const user = userOptions.find((option) => option.id === value)
                                        return user?.display_name ?? "Unknown user"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="">Any user</SelectItem>
                                {userOptions.map((user) => (
                                    <SelectItem key={user.id} value={user.id}>
                                        {user.display_name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}
            </InspectorSection>

            <InspectorSection title="Details" defaultOpen={Boolean(workflowDescription)}>
                <div className="grid gap-1.5">
                    <Label htmlFor="workflow-description">Description</Label>
                    <Textarea
                        id="workflow-description"
                        placeholder="Describe what this workflow does"
                        value={workflowDescription}
                        onChange={(event) => setWorkflowDescription(event.target.value)}
                        rows={3}
                    />
                </div>
            </InspectorSection>
        </InspectorPanel>
    )
}
