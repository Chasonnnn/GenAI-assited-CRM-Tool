"use client"

import { useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import {
    CalendarClockIcon,
    CrosshairIcon,
    FileTextIcon,
    FilterIcon,
    PlusIcon,
    WorkflowIcon,
    XIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { WorkflowSubjectType } from "@/lib/api/workflows"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import {
    TIME_TRIGGER_TYPES,
    WEEKDAY_LABELS,
    WORKFLOW_SUBJECT_LABELS,
    APPOINTMENT_TIMING_OPTIONS,
    buildSimpleCron,
    getAppointmentTimingLabel,
    getAppointmentTypeNames,
    getConditionFieldLabel,
    getTriggerLabel,
    parseSimpleCron,
    withIntakeTriggerForm,
    type ScheduleFrequency,
} from "@/lib/workflows/workflow-editor-state"
import {
    APPLICANT_TYPE_BOTH,
    APPLICANT_TYPE_OPTIONS,
    ConditionValueInput,
    FORM_SUBMISSION_TRIGGER_TYPES,
    FORM_TRIGGER_TYPES,
    getApplicantTypeLabel,
    isDonorLeadKind,
} from "@/components/automation/workflow-editor/shared"
import { DotOptionGroup, EditorColumn, FieldRow, PanelCard, PanelHeading, PanelSection } from "./inspector-section"

type TriggerMode = "event" | "time"

const TRIGGER_MODE_OPTIONS: { value: TriggerMode; label: string }[] = [
    { value: "event", label: "Trigger event" },
    { value: "time", label: "Date or scheduled" },
]

const SCHEDULE_FREQUENCY_OPTIONS: { value: ScheduleFrequency; label: string }[] = [
    { value: "daily", label: "Run every day" },
    { value: "weekdays", label: "Run every weekday" },
    { value: "weekly", label: "Run every week" },
    { value: "custom", label: "Custom cron" },
]

export function WorkflowTriggerPanel({ controller }: { controller: WorkflowEditorController }) {
    const { state, handlers, isEditing, createWorkflowSubjectOptions } = controller
    const { subjectType, savedSubjectType, actionSubjectType, isAppointmentTrigger, triggerType, workflowDescription } =
        state
    const { setSubjectType, setTriggerType, setTriggerConfig, setWorkflowDescription } = handlers
    const [selectedMode, setSelectedMode] = useState<TriggerMode>("event")
    const mode: TriggerMode = triggerType ? (TIME_TRIGGER_TYPES.has(triggerType) ? "time" : "event") : selectedMode
    const triggerOptions = controller.options.triggerTypeOptions.filter(
        (option) => TIME_TRIGGER_TYPES.has(option.value) === (mode === "time"),
    )
    // Editing and fixed-subject triggers lock the record type to the one that will be saved.
    const subjectLocked = isEditing || savedSubjectType !== subjectType
    const subjectOptions = subjectLocked
        ? [{ value: savedSubjectType, label: WORKFLOW_SUBJECT_LABELS[savedSubjectType] }]
        : createWorkflowSubjectOptions

    return (
        <EditorColumn aria-label="Triggers">
            <PanelHeading title="Triggers" />

            <PanelSection title="Run this workflow">
                <PanelCard icon={WorkflowIcon} title="Workflow run">
                    <DotOptionGroup
                        ariaLabel="Trigger kind"
                        value={mode}
                        options={TRIGGER_MODE_OPTIONS}
                        onValueChange={(value) => {
                            const nextMode = value as TriggerMode
                            setSelectedMode(nextMode)
                            if (triggerType && TIME_TRIGGER_TYPES.has(triggerType) !== (nextMode === "time")) {
                                setTriggerType("")
                            }
                        }}
                    />
                    <Select aria-label="Trigger type" value={triggerType} onValueChange={(value) => value && setTriggerType(value)}>
                        <SelectTrigger aria-label="Trigger type" className="w-full">
                            <SelectValue placeholder={mode === "time" ? "Select schedule" : "Select event"}>
                                {(value: string | null) => {
                                    if (!value) return mode === "time" ? "Select schedule" : "Select event"
                                    return triggerOptions.find((option) => option.value === value)?.label ?? getTriggerLabel(value)
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="min-w-[260px]">
                            {triggerOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <TriggerConfigFields controller={controller} />
                </PanelCard>
            </PanelSection>

            <PanelSection title="Workflow will target">
                {isAppointmentTrigger ? (
                    <PanelCard icon={CrosshairIcon} title="Linked record">
                        <DotOptionGroup
                            ariaLabel="Linked record"
                            value={actionSubjectType}
                            options={createWorkflowSubjectOptions}
                            onValueChange={(value) =>
                                setTriggerConfig((currentConfig) => ({ ...currentConfig, record_type: value }))
                            }
                        />
                    </PanelCard>
                ) : (
                    <PanelCard icon={CrosshairIcon} title="Target by">
                        <DotOptionGroup
                            ariaLabel="Record type"
                            value={subjectLocked ? savedSubjectType : subjectType}
                            options={subjectOptions}
                            onValueChange={(value) => setSubjectType(value as WorkflowSubjectType)}
                            disabled={subjectLocked}
                        />
                    </PanelCard>
                )}
            </PanelSection>

            {triggerType === "scheduled" ? (
                <PanelSection title="Start workflow">
                    <ScheduleCard controller={controller} />
                </PanelSection>
            ) : null}

            <FiltersSection controller={controller} />

            <PanelSection title="Details" defaultOpen={Boolean(workflowDescription)}>
                <PanelCard icon={FileTextIcon} title="Description">
                    <Textarea
                        id="workflow-description"
                        aria-label="Description"
                        placeholder="Describe what this workflow does"
                        value={workflowDescription}
                        onChange={(event) => setWorkflowDescription(event.target.value)}
                        rows={3}
                    />
                </PanelCard>
            </PanelSection>
        </EditorColumn>
    )
}

function TriggerConfigFields({ controller }: { controller: WorkflowEditorController }) {
    const { state, options, handlers } = controller
    const { triggerType, triggerConfig, isAppointmentTrigger } = state
    const {
        appointmentTypeNames,
        formOptions,
        statusOptions,
        activeStatusOptions,
        userOptions,
        availableConditionFields,
        selectedTriggerFields,
        isSharedDonorTriggerForm,
        configuredIntakeLeadKind,
    } = options
    const { setTriggerConfig, setIntakeApplicantType } = handlers

    return (
        <>
            {(triggerType === "status_changed" || triggerType === "donor_stage_changed") && (
                <div className="grid grid-cols-2 gap-2">
                    <FieldRow label="From">
                        <Select
                            aria-label="From stage"
                            value={typeof triggerConfig.from_stage_id === "string" ? triggerConfig.from_stage_id : ""}
                            onValueChange={(value) =>
                                setTriggerConfig((currentConfig) => ({ ...currentConfig, from_stage_id: value }))
                            }
                        >
                            <SelectTrigger aria-label="From stage" className="w-full">
                                <SelectValue placeholder="Any stage">
                                    {(value: string | null) => {
                                        if (!value) return "Any stage"
                                        return statusOptions.find((option) => option.id === value)?.label ?? "Unknown stage"
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
                    </FieldRow>
                    <FieldRow label="To">
                        <Select
                            aria-label="To stage"
                            value={typeof triggerConfig.to_stage_id === "string" ? triggerConfig.to_stage_id : ""}
                            onValueChange={(value) =>
                                setTriggerConfig((currentConfig) => ({ ...currentConfig, to_stage_id: value }))
                            }
                        >
                            <SelectTrigger aria-label="To stage" className="w-full">
                                <SelectValue placeholder="Any stage">
                                    {(value: string | null) => {
                                        if (!value) return "Any stage"
                                        return statusOptions.find((option) => option.id === value)?.label ?? "Unknown stage"
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
                    </FieldRow>
                </div>
            )}

            {triggerType === "inactivity" && (
                <FieldRow label="Days inactive" htmlFor="workflow-trigger-days">
                    <Input
                        id="workflow-trigger-days"
                        type="number"
                        min={1}
                        max={90}
                        value={typeof triggerConfig.days === "number" ? triggerConfig.days : 7}
                        onChange={(event) =>
                            setTriggerConfig((currentConfig) => ({ ...currentConfig, days: Number(event.target.value) }))
                        }
                    />
                </FieldRow>
            )}

            {triggerType === "task_due" && (
                <FieldRow label="Hours before due" htmlFor="workflow-trigger-hours">
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
                </FieldRow>
            )}

            {triggerType === "appointment_time" && (
                <div className="grid grid-cols-2 gap-2">
                    <FieldRow label="When">
                        <Select
                            aria-label="When"
                            value={triggerConfig.when === "after_end" ? "after_end" : "before_start"}
                            onValueChange={(value) =>
                                value && setTriggerConfig((currentConfig) => ({ ...currentConfig, when: value }))
                            }
                        >
                            <SelectTrigger aria-label="When" className="w-full">
                                <SelectValue>{getAppointmentTimingLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {APPOINTMENT_TIMING_OPTIONS.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </FieldRow>
                    <FieldRow label="Hours" htmlFor="workflow-trigger-appointment-hours">
                        <Input
                            id="workflow-trigger-appointment-hours"
                            type="number"
                            min={1}
                            max={168}
                            value={typeof triggerConfig.hours === "number" ? triggerConfig.hours : 24}
                            onChange={(event) =>
                                setTriggerConfig((currentConfig) => ({
                                    ...currentConfig,
                                    hours: Number(event.target.value),
                                }))
                            }
                        />
                    </FieldRow>
                </div>
            )}

            {FORM_TRIGGER_TYPES.has(triggerType) && (
                <FieldRow label="Form">
                    <Select
                        aria-label="Form"
                        value={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                        onValueChange={(value) =>
                            setTriggerConfig((currentConfig) => withIntakeTriggerForm(triggerType, currentConfig, value))
                        }
                    >
                        <SelectTrigger aria-label="Form" className="w-full">
                            <SelectValue placeholder="Select form">
                                {(value: string | null) => {
                                    if (!value) return "Select form"
                                    return formOptions.find((option) => option.value === value)?.label ?? "Unknown form"
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
                        <p className="text-[11px] text-muted-foreground">Publish a form to use this trigger.</p>
                    )}
                </FieldRow>
            )}

            {FORM_SUBMISSION_TRIGGER_TYPES.has(triggerType) &&
            typeof triggerConfig.form_id === "string" &&
            triggerConfig.form_id ? (
                <Link
                    href={`/automation/forms/${encodeURIComponent(triggerConfig.form_id)}?tab=routing` as Route}
                    className="text-xs font-medium text-primary hover:underline"
                >
                    Matching and lead creation:{" "}
                    <span className="whitespace-nowrap">
                        Routing tab<span aria-hidden="true">{"\u00a0→"}</span>
                    </span>
                </Link>
            ) : null}

            {isSharedDonorTriggerForm && (
                <FieldRow label="Applicant type">
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
                </FieldRow>
            )}

            {(triggerType === "surrogate_updated" || triggerType === "donor_updated") && (
                <FieldRow label="Fields to watch">
                    <Select
                        aria-label="Fields to watch"
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
                        <SelectTrigger aria-label="Fields to watch" className="w-full">
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
                        <div className="flex flex-wrap gap-1">
                            {selectedTriggerFields.map((field) => (
                                <Badge key={field} variant="outline" className="gap-1 bg-card">
                                    {getConditionFieldLabel(field)}
                                    <Button
                                        unstyled
                                        type="button"
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
                </FieldRow>
            )}

            {isAppointmentTrigger && (
                <AppointmentTypeFilter
                    typeNames={appointmentTypeNames}
                    selected={getAppointmentTypeNames(triggerConfig)}
                    onChange={(names) =>
                        setTriggerConfig((currentConfig) => ({ ...currentConfig, appointment_type_names: names }))
                    }
                />
            )}

            {(triggerType === "surrogate_assigned" || triggerType === "donor_assigned") && (
                <FieldRow label="Assigned to">
                    <Select
                        aria-label="Assigned to"
                        value={typeof triggerConfig.to_user_id === "string" ? triggerConfig.to_user_id : ""}
                        onValueChange={(value) =>
                            setTriggerConfig((currentConfig) => ({ ...currentConfig, to_user_id: value || null }))
                        }
                    >
                        <SelectTrigger aria-label="Assigned to" className="w-full">
                            <SelectValue placeholder="Any user">
                                {(value: string | null) => {
                                    if (!value) return "Any user"
                                    return userOptions.find((option) => option.id === value)?.display_name ?? "Unknown user"
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
                </FieldRow>
            )}
        </>
    )
}

function AppointmentTypeFilter({
    typeNames,
    selected,
    onChange,
}: {
    typeNames: string[]
    selected: string[]
    onChange: (names: string[]) => void
}) {
    const selectedKeys = new Set(selected.map((name) => name.toLocaleLowerCase()))
    const available = typeNames.filter((name) => !selectedKeys.has(name.toLocaleLowerCase()))
    return (
        <FieldRow label="Appointment types">
            <Select
                aria-label="Appointment types"
                value=""
                onValueChange={(value) => {
                    if (value) onChange([...selected, value])
                }}
            >
                <SelectTrigger aria-label="Appointment types" className="w-full">
                    <SelectValue placeholder="Any type">
                        {(value: string | null) => value || (selected.length > 0 ? "Add type" : "Any type")}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {available.map((name) => (
                        <SelectItem key={name} value={name}>
                            {name}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            {selected.length > 0 && (
                <div className="flex flex-wrap gap-1">
                    {selected.map((name) => (
                        <Badge key={name} variant="outline" className="gap-1 bg-card">
                            {name}
                            <Button
                                unstyled
                                type="button"
                                aria-label={`Remove ${name}`}
                                onClick={() => onChange(selected.filter((item) => item !== name))}
                            >
                                <XIcon className="size-3" />
                            </Button>
                        </Badge>
                    ))}
                </div>
            )}
        </FieldRow>
    )
}

function ScheduleCard({ controller }: { controller: WorkflowEditorController }) {
    const { triggerConfig } = controller.state
    const { setTriggerConfig } = controller.handlers
    const cron = typeof triggerConfig.cron === "string" ? triggerConfig.cron : ""
    const parsed = parseSimpleCron(cron)
    // "Custom cron" is a view choice: a preset-shaped cron still edits as raw text once chosen.
    const [customChosen, setCustomChosen] = useState(false)
    const frequency: ScheduleFrequency | "" = customChosen ? "custom" : parsed?.frequency ?? ""
    const schedule = parsed ?? { frequency: "daily" as const, time: "09:00", dayOfWeek: 1 }
    const setCron = (value: string) => setTriggerConfig((currentConfig) => ({ ...currentConfig, cron: value }))

    return (
        <PanelCard icon={CalendarClockIcon} title="Schedule">
            <DotOptionGroup
                ariaLabel="Schedule frequency"
                value={frequency}
                options={SCHEDULE_FREQUENCY_OPTIONS}
                onValueChange={(value) => {
                    const next = value as ScheduleFrequency
                    if (next === "custom") {
                        setCustomChosen(true)
                        return
                    }
                    setCustomChosen(false)
                    setCron(buildSimpleCron({ ...schedule, frequency: next }))
                }}
            />
            {frequency === "custom" ? (
                <FieldRow label="Cron schedule" htmlFor="workflow-trigger-cron">
                    <Input
                        id="workflow-trigger-cron"
                        placeholder="0 9 * * 1"
                        value={cron}
                        onChange={(event) => setCron(event.target.value)}
                    />
                </FieldRow>
            ) : frequency ? (
                <div className="grid grid-cols-2 gap-2">
                    {frequency === "weekly" ? (
                        <FieldRow label="On">
                            <Select
                                aria-label="Day of week"
                                value={String(schedule.dayOfWeek)}
                                onValueChange={(value) =>
                                    value && setCron(buildSimpleCron({ ...schedule, frequency, dayOfWeek: Number(value) }))
                                }
                            >
                                <SelectTrigger aria-label="Day of week" className="w-full">
                                    <SelectValue>{(value: string | null) => WEEKDAY_LABELS[Number(value ?? 1)]}</SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {WEEKDAY_LABELS.map((label, day) => (
                                        <SelectItem key={label} value={String(day)}>
                                            {label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </FieldRow>
                    ) : null}
                    <FieldRow label="At" htmlFor="workflow-trigger-time">
                        <Input
                            id="workflow-trigger-time"
                            type="time"
                            value={schedule.time}
                            onChange={(event) =>
                                event.target.value &&
                                setCron(buildSimpleCron({ ...schedule, frequency, time: event.target.value }))
                            }
                        />
                    </FieldRow>
                </div>
            ) : null}
            <FieldRow label="Timezone" htmlFor="workflow-trigger-timezone">
                <Input
                    id="workflow-trigger-timezone"
                    placeholder="America/Los_Angeles"
                    value={typeof triggerConfig.timezone === "string" ? triggerConfig.timezone : "America/Los_Angeles"}
                    onChange={(event) =>
                        setTriggerConfig((currentConfig) => ({ ...currentConfig, timezone: event.target.value }))
                    }
                />
            </FieldRow>
        </PanelCard>
    )
}

function FiltersSection({ controller }: { controller: WorkflowEditorController }) {
    const { state, options, handlers } = controller
    const { conditions, conditionLogic } = state
    const { availableConditionFields, conditionOperators, getConditionOptions } = options
    const { addCondition, removeCondition, updateCondition, setConditionLogic } = handlers

    return (
        <PanelSection
            title="Others filter"
            actions={
                conditions.length > 0 ? (
                    <Button size="icon-sm" variant="ghost" className="size-6" aria-label="Add filter" onClick={addCondition}>
                        <PlusIcon aria-hidden="true" className="size-3.5" />
                    </Button>
                ) : undefined
            }
        >
            {conditions.length > 1 ? (
                <DotOptionGroup
                    ariaLabel="Condition logic"
                    value={conditionLogic}
                    options={[
                        { value: "AND", label: "All filters match" },
                        { value: "OR", label: "Any filter matches" },
                    ]}
                    onValueChange={(value) => (value === "AND" || value === "OR") && setConditionLogic(value)}
                />
            ) : null}
            {conditions.map((condition, index) => (
                <PanelCard
                    key={condition.clientId}
                    icon={FilterIcon}
                    title={condition.field ? getConditionFieldLabel(condition.field) : `Filter ${index + 1}`}
                    actions={
                        <Button
                            size="icon-sm"
                            variant="ghost"
                            className="size-6"
                            aria-label="Remove condition"
                            onClick={() => removeCondition(index)}
                        >
                            <XIcon aria-hidden="true" className="size-3.5" />
                        </Button>
                    }
                >
                    <Select value={condition.field} onValueChange={(value) => value && updateCondition(index, { field: value })}>
                        <SelectTrigger aria-label={`Condition ${index + 1} field`} className="w-full">
                            <SelectValue placeholder="Field">
                                {(value: string | null) => (value ? getConditionFieldLabel(value) : "Field")}
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
                    <Select
                        value={condition.operator}
                        onValueChange={(value) => value && updateCondition(index, { operator: value })}
                    >
                        <SelectTrigger aria-label={`Condition ${index + 1} operator`} className="w-full">
                            <SelectValue placeholder="Operator">
                                {(value: string | null) => {
                                    if (!value) return "Operator"
                                    return conditionOperators.find((option) => option.value === value)?.label ?? "Unknown operator"
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {conditionOperators.map((operator) => (
                                <SelectItem key={operator.value} value={operator.value}>
                                    {operator.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <div className="flex min-w-0">
                        <ConditionValueInput
                            condition={condition}
                            options={getConditionOptions(condition.field)}
                            onChange={(value) => updateCondition(index, { value })}
                        />
                    </div>
                </PanelCard>
            ))}
            {conditions.length === 0 ? (
                <Button
                    unstyled
                    type="button"
                    onClick={addCondition}
                    className="flex h-8 w-full items-center gap-2 rounded-md border border-dashed border-border px-2.5 text-xs text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                >
                    <PlusIcon aria-hidden="true" className="size-3.5" />
                    Add filter
                </Button>
            ) : null}
        </PanelSection>
    )
}
