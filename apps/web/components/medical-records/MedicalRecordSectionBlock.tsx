"use client"

import { useId, useState, type FormEvent } from "react"
import { ChevronDownIcon, HistoryIcon, Loader2Icon, PlusIcon } from "lucide-react"

import { InlineDateField } from "@/components/inline-date-field"
import { InlineEditField } from "@/components/inline-edit-field"
import {
    fieldLabel,
    formatRecordDate,
    recordName,
    recordRange,
    recordStatusLabel,
    type MedicalRecordFieldConfig,
    type MedicalRecordSectionConfig,
    type RecordStatusLabel,
} from "@/components/medical-records/medical-record-sections"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "@/components/ui/toast"
import { formatDate } from "@/lib/formatters"
import { useCorrectMedicalRecord, useCreateMedicalRecord } from "@/lib/hooks/use-medical-records"
import type {
    MedicalRecord,
    MedicalRecordField,
    MedicalRecordOwner,
} from "@/lib/types/medical-record"
import { cn } from "@/lib/utils"

const STATUS_BADGE_CLASS: Record<RecordStatusLabel, string> = {
    Current: "bg-primary/10 text-primary",
    Past: "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
    Archived: "border border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
    Scheduled: "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
}

function StatusBadges({ record }: { record: MedicalRecord }) {
    const label = recordStatusLabel(record)
    return (
        <>
            <span className={cn("inline-flex h-[18px] items-center rounded-full px-1.5 text-[11px] font-semibold whitespace-nowrap", STATUS_BADGE_CLASS[label])}>
                {label}
            </span>
            {!record.effective_date && (
                <span className="inline-flex h-[18px] items-center rounded-full bg-muted px-1.5 text-[11px] font-semibold whitespace-nowrap text-muted-foreground">
                    Imported
                </span>
            )}
        </>
    )
}

function newIdempotencyKey(): string {
    return crypto.randomUUID()
}

type KeptValues = Partial<Record<MedicalRecordField, string>>

type PendingIdentityChange = { record: MedicalRecord; field: MedicalRecordField; from: string; to: string }

type SectionMode =
    | { kind: "view" }
    | { kind: "prompt"; pending: PendingIdentityChange }
    | { kind: "new"; copyFrom: string | null; keep: KeptValues }

export interface MedicalRecordSectionBlockProps {
    owner: MedicalRecordOwner
    config: MedicalRecordSectionConfig
    /** API order: scheduled first, then newest to oldest. */
    records: MedicalRecord[]
    today: string
    canEdit: boolean
    archived?: boolean
    /** Opens straight into the new-record form (section added from the menu). */
    startInForm?: boolean
    onFormClosed?: () => void
    onRestore?: () => void
    isRestoring?: boolean
}

export function MedicalRecordSectionBlock({
    owner,
    config,
    records,
    today,
    canEdit,
    archived = false,
    startInForm = false,
    onFormClosed,
    onRestore,
    isRestoring = false,
}: MedicalRecordSectionBlockProps) {
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const [mode, setMode] = useState<SectionMode>(
        startInForm ? { kind: "new", copyFrom: null, keep: {} } : { kind: "view" },
    )
    const [showLog, setShowLog] = useState(false)
    const correctRecord = useCorrectMedicalRecord(owner)

    const current = records.find((record) => record.status === "current") ?? null
    const scheduled = records.filter((record) => record.status === "scheduled")
    const selected =
        records.find((record) => record.id === selectedId) ?? current ?? scheduled.at(-1) ?? records[0] ?? null

    const closeForm = () => {
        setMode({ kind: "view" })
        onFormClosed?.()
    }

    const saveCorrection = async (record: MedicalRecord, field: MedicalRecordField, value: string | null) => {
        await correctRecord.mutateAsync({
            recordId: record.id,
            data: { [field]: value, expected_revision: record.revision },
        })
    }

    const handleFieldSave = async (record: MedicalRecord, field: MedicalRecordField, raw: string | null) => {
        const from = (record[field] ?? "").trim()
        const to = (raw ?? "").trim()
        if (from === to) return
        if (
            config.identityFields.includes(field) &&
            record.status === "current" &&
            from &&
            to &&
            from.toLowerCase() !== to.toLowerCase()
        ) {
            setMode({ kind: "prompt", pending: { record, field, from, to } })
            return
        }
        await saveCorrection(record, field, to || null)
    }

    const tone =
        mode.kind === "view" && selected
            ? selected.status === "past"
                ? "past"
                : selected.status === "scheduled"
                  ? "scheduled"
                  : null
            : null
    const fromId = selected && selected.status !== "current" ? selected.id : null

    return (
        <section
            aria-label={config.title}
            className={cn(
                "flex min-w-0 flex-col gap-2.5 rounded-lg border bg-card p-3",
                tone === "past" && "border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/25",
                tone === "scheduled" && "bg-sky-50/70 dark:bg-sky-950/25",
            )}
        >
            <div className="flex items-center gap-2">
                <h4 className="mr-auto flex items-center gap-2 text-sm font-medium">
                    {config.icon}
                    {config.title}
                </h4>
                {archived && canEdit && mode.kind === "view" && onRestore && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={onRestore}
                        disabled={isRestoring}
                        aria-label={`Restore ${config.title}`}
                    >
                        {isRestoring ? <Loader2Icon className="size-3.5 animate-spin" /> : <HistoryIcon className="size-3.5" />}
                        Restore
                    </Button>
                )}
                {canEdit && mode.kind === "view" && selected && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => setMode({ kind: "new", copyFrom: fromId, keep: {} })}
                        aria-label={`New ${config.title} record`}
                    >
                        <PlusIcon className="size-3.5" />
                        New
                    </Button>
                )}
            </div>

            {selected && mode.kind !== "new" && (
                <div>
                    <RecordSelector
                        config={config}
                        records={records}
                        selected={selected}
                        onSelect={(record) => {
                            setSelectedId(record.id)
                            setShowLog(false)
                            if (mode.kind === "prompt") setMode({ kind: "view" })
                        }}
                    />
                </div>
            )}

            {mode.kind === "new" ? (
                <NewRecordForm
                    owner={owner}
                    config={config}
                    records={records}
                    today={today}
                    initialCopyFrom={mode.copyFrom}
                    keep={mode.keep}
                    onCancel={closeForm}
                    onSaved={() => {
                        setSelectedId(null)
                        setShowLog(false)
                        closeForm()
                    }}
                />
            ) : mode.kind === "prompt" ? (
                <IdentityPrompt
                    config={config}
                    pending={mode.pending}
                    onNewRecord={() =>
                        setMode({ kind: "new", copyFrom: mode.pending.record.id, keep: { [mode.pending.field]: mode.pending.to } })
                    }
                    onCorrect={async () => {
                        const { record, field, to } = mode.pending
                        setMode({ kind: "view" })
                        try {
                            await saveCorrection(record, field, to)
                        } catch (error) {
                            toast.error(error instanceof Error ? error.message : "Couldn't save this change. Try again.")
                        }
                    }}
                    onCancel={() => setMode({ kind: "view" })}
                />
            ) : selected ? (
                <RecordView
                    config={config}
                    record={selected}
                    hasCurrent={current !== null}
                    canEdit={canEdit}
                    showLog={showLog}
                    onToggleLog={() => setShowLog((value) => !value)}
                    onBackToCurrent={() => {
                        setSelectedId(null)
                        setShowLog(false)
                    }}
                    onFieldSave={handleFieldSave}
                />
            ) : null}
        </section>
    )
}

function RecordSelector({
    config,
    records,
    selected,
    onSelect,
}: {
    config: MedicalRecordSectionConfig
    records: MedicalRecord[]
    selected: MedicalRecord
    onSelect: (record: MedicalRecord) => void
}) {
    return (
        <DropdownMenu>
            <DropdownMenuTrigger
                render={
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1.5 rounded-full px-2.5 text-xs font-normal shadow-none"
                        aria-label={`${config.title} records, ${records.length} total`}
                    />
                }
            >
                <HistoryIcon className="size-3.5 text-muted-foreground" />
                <StatusBadges record={selected} />
                <span>{recordRange(selected)}</span>
                <ChevronDownIcon className="size-3.5 text-muted-foreground" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72">
                <DropdownMenuGroup>
                    <DropdownMenuLabel>
                        {records.length} {records.length === 1 ? "record" : "records"}
                    </DropdownMenuLabel>
                    {records.map((record) => (
                        <DropdownMenuItem
                            key={record.id}
                            onClick={() => onSelect(record)}
                            aria-current={record.id === selected.id ? "true" : undefined}
                            className={cn("flex-col items-start gap-0.5", record.id === selected.id && "bg-accent/60")}
                        >
                            <span className="flex w-full items-center gap-1.5">
                                <span className="mr-auto truncate font-medium">{recordName(record)}</span>
                                <StatusBadges record={record} />
                            </span>
                            <span className="text-xs text-muted-foreground">{recordRange(record)}</span>
                        </DropdownMenuItem>
                    ))}
                </DropdownMenuGroup>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

function FieldValue({
    config,
    record,
    field,
    canEdit,
    onFieldSave,
}: {
    config: MedicalRecordSectionConfig
    record: MedicalRecord
    field: MedicalRecordFieldConfig
    canEdit: boolean
    onFieldSave: (record: MedicalRecord, field: MedicalRecordField, value: string | null) => Promise<void>
}) {
    const label = `${config.title} ${field.label}`
    if (field.type === "date") {
        return (
            <InlineDateField
                value={record[field.key]}
                onSave={(value) => onFieldSave(record, field.key, value)}
                label={label}
                disabled={!canEdit}
            />
        )
    }
    return (
        <InlineEditField
            readOnly={!canEdit}
            value={record[field.key]}
            onSave={(value) => onFieldSave(record, field.key, value)}
            label={label}
            placeholder={field.placeholder}
            className="min-w-0 wrap-anywhere"
            displayClassName="min-w-0 max-w-full text-left"
            {...(field.type ? { type: field.type } : {})}
            {...(field.key === "state"
                ? { validate: (value: string) => (value && value.length !== 2 ? "Use 2-letter code" : null) }
                : {})}
        />
    )
}

function RecordView({
    config,
    record,
    hasCurrent,
    canEdit,
    showLog,
    onToggleLog,
    onBackToCurrent,
    onFieldSave,
}: {
    config: MedicalRecordSectionConfig
    record: MedicalRecord
    hasCurrent: boolean
    canEdit: boolean
    showLog: boolean
    onToggleLog: () => void
    onBackToCurrent: () => void
    onFieldSave: (record: MedicalRecord, field: MedicalRecordField, value: string | null) => Promise<void>
}) {
    const rows: React.ReactNode[] = []
    const cityStateZip = config.fields.filter((field) => field.cityStateZip)
    for (const field of config.fields) {
        if (field.cityStateZip && field !== cityStateZip[0]) continue
        if (field.divider) {
            rows.push(<div key={`${field.key}-divider`} className="col-span-2 border-t" />)
        }
        const values = field.cityStateZip ? cityStateZip : [field]
        rows.push(
            <span key={`${field.key}-label`} className="pt-0.5 text-sm text-muted-foreground">
                {field.cityStateZip ? "City/State/ZIP" : field.label}
            </span>,
            <div key={`${field.key}-value`} className="flex min-w-0 flex-wrap items-center gap-x-2">
                {values.map((item) => (
                    <FieldValue
                        key={item.key}
                        config={config}
                        record={record}
                        field={item}
                        canEdit={canEdit}
                        onFieldSave={onFieldSave}
                    />
                ))}
            </div>,
        )
    }

    const corrections = record.corrections
    const added =
        record.source === "import"
            ? `Imported on ${formatDate(record.created_at)}`
            : `Added by ${record.created_by_name ?? "Unknown"} on ${formatDate(record.created_at)}`

    return (
        <>
            {record.status !== "current" && hasCurrent && (
                <div
                    className={cn(
                        "flex flex-wrap items-center justify-between gap-2 text-xs",
                        record.status === "past" ? "text-amber-700 dark:text-amber-300" : "text-sky-700 dark:text-sky-300",
                    )}
                >
                    <span>
                        {record.status === "past"
                            ? "Viewing a past record"
                            : `Starts ${formatRecordDate(record.effective_date)}`}
                    </span>
                    <Button type="button" variant="link" className="h-auto p-0 text-xs text-current" onClick={onBackToCurrent}>
                        Back to current
                    </Button>
                </div>
            )}
            <div
                className={cn(
                    "grid items-start gap-x-2.5 gap-y-1",
                    config.key === "insurance" ? "grid-cols-[112px_minmax(0,1fr)]" : "grid-cols-[92px_minmax(0,1fr)]",
                )}
            >
                {rows}
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t pt-2 text-xs text-muted-foreground">
                <span>{added}</span>
                {record.archived_on && (
                    <>
                        <span aria-hidden="true">·</span>
                        <span>
                            Archived by {record.archived_by_name ?? "Unknown"} on {formatRecordDate(record.archived_on)}
                        </span>
                    </>
                )}
                {corrections.length > 0 && (
                    <>
                        <span aria-hidden="true">·</span>
                        <Button
                            type="button"
                            variant="link"
                            className="h-auto p-0 text-xs font-normal text-muted-foreground"
                            aria-expanded={showLog}
                            onClick={onToggleLog}
                        >
                            {corrections.length} {corrections.length === 1 ? "correction" : "corrections"}
                        </Button>
                    </>
                )}
            </div>
            {showLog && corrections.length > 0 && (
                <ul className="flex flex-col gap-1.5 text-xs">
                    {[...corrections].reverse().map((correction) => (
                        <li key={correction.id} className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
                            <time className="whitespace-nowrap text-muted-foreground tabular-nums" dateTime={correction.corrected_at}>
                                {formatDate(correction.corrected_at)}
                            </time>
                            <span>
                                {correction.corrected_by_name ?? (correction.source === "form" ? "Form submission" : "Unknown")}
                                {" · "}
                                {fieldLabel(record.section, correction.field)}
                                {correction.redacted ? (
                                    " changed"
                                ) : (
                                    <>
                                        {": "}
                                        <s className="text-muted-foreground">{correction.old_value || "empty"}</s>
                                        {" → "}
                                        {correction.new_value || "empty"}
                                    </>
                                )}
                            </span>
                        </li>
                    ))}
                </ul>
            )}
        </>
    )
}

function IdentityPrompt({
    config,
    pending,
    onNewRecord,
    onCorrect,
    onCancel,
}: {
    config: MedicalRecordSectionConfig
    pending: PendingIdentityChange
    onNewRecord: () => void
    onCorrect: () => void
    onCancel: () => void
}) {
    const headingId = useId()
    return (
        <div role="group" aria-labelledby={headingId} className="flex flex-col gap-2.5 rounded-lg bg-muted p-3">
            <h5 id={headingId} className="text-sm font-semibold">
                Is this a new {config.noun}?
            </h5>
            <div className="flex flex-wrap items-center gap-1.5 text-sm">
                <span className="text-muted-foreground">{fieldLabel(config.key, pending.field)}:</span>
                <s className="text-muted-foreground">{pending.from}</s>
                <span aria-hidden="true">→</span>
                <strong className="font-medium">{pending.to}</strong>
            </div>
            <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={onNewRecord} autoFocus>
                    Yes, start a new record
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={onCorrect}>
                    No, correct this record
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
                    Cancel
                </Button>
            </div>
        </div>
    )
}

const NO_COPY_SOURCE = "none"

function valuesFrom(record: MedicalRecord | undefined, config: MedicalRecordSectionConfig): Record<string, string> {
    return Object.fromEntries(config.fields.map((field) => [field.key, record?.[field.key] ?? ""]))
}

function NewRecordForm({
    owner,
    config,
    records,
    today,
    initialCopyFrom,
    keep,
    onCancel,
    onSaved,
}: {
    owner: MedicalRecordOwner
    config: MedicalRecordSectionConfig
    records: MedicalRecord[]
    today: string
    initialCopyFrom: string | null
    keep: KeptValues
    onCancel: () => void
    onSaved: () => void
}) {
    const idPrefix = useId()
    const createRecord = useCreateMedicalRecord(owner)
    const [idempotencyKey] = useState(newIdempotencyKey)
    const [effectiveDate, setEffectiveDate] = useState(today)
    const [copyFrom, setCopyFrom] = useState(initialCopyFrom ?? NO_COPY_SOURCE)
    const [values, setValues] = useState<Record<string, string>>(() => ({
        ...valuesFrom(records.find((record) => record.id === initialCopyFrom), config),
        ...keep,
    }))
    const [error, setError] = useState<string | null>(null)
    const isFirst = records.length === 0
    const saving = createRecord.isPending

    const copyLabel = (value: string | null) => {
        const record = records.find((item) => item.id === value)
        if (!record) return "Nothing"
        return `${recordName(record)} · ${record.status === "current" ? "Current" : recordRange(record)}`
    }

    const handleCopyChange = (value: string | null) => {
        const next = value ?? NO_COPY_SOURCE
        setCopyFrom(next)
        setValues({ ...valuesFrom(records.find((record) => record.id === next), config), ...keep })
    }

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (saving) return
        setError(null)
        if (!effectiveDate) {
            setError("Enter the effective date.")
            return
        }
        if (!config.identityFields.some((field) => (values[field] ?? "").trim())) {
            setError(
                config.key === "insurance"
                    ? "Enter the insurance company."
                    : config.identityFields.length > 1
                      ? "Enter the provider or clinic name."
                      : "Enter the name.",
            )
            return
        }
        const fields = Object.fromEntries(
            config.fields.map((field) => [field.key, (values[field.key] ?? "").trim() || null]),
        )
        try {
            await createRecord.mutateAsync({
                ...fields,
                section: config.key,
                effective_date: effectiveDate,
                idempotency_key: idempotencyKey,
            })
        } catch (saveError) {
            setError(saveError instanceof Error ? saveError.message : "Couldn't save the record. Try again.")
            return
        }
        const current = records.find((record) => record.status === "current")
        if (effectiveDate > today) {
            toast.success(`${config.title}: scheduled for ${formatRecordDate(effectiveDate)}`)
        } else if (current?.effective_date && effectiveDate < current.effective_date) {
            toast.success(`${config.title}: saved as a past record`)
        } else if (isFirst) {
            toast.success(`${config.title} added`)
        } else {
            toast.success(`${config.title}: new record saved`)
        }
        onSaved()
    }

    return (
        <form className="flex flex-col gap-3" onSubmit={handleSubmit} noValidate>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor={`${idPrefix}-effective`}>Effective date</Label>
                    <Input
                        id={`${idPrefix}-effective`}
                        type="date"
                        value={effectiveDate}
                        onChange={(event) => setEffectiveDate(event.target.value)}
                        disabled={saving}
                        autoFocus
                    />
                </div>
                {records.length > 0 && (
                    <div className="flex flex-col gap-1.5">
                        <Label id={`${idPrefix}-copy-label`}>Copy details from</Label>
                        <Select value={copyFrom} onValueChange={handleCopyChange} disabled={saving}>
                            <SelectTrigger aria-labelledby={`${idPrefix}-copy-label`} className="w-full">
                                <SelectValue>{(value: string | null) => copyLabel(value)}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={NO_COPY_SOURCE}>Nothing</SelectItem>
                                {records.map((record) => (
                                    <SelectItem key={record.id} value={record.id}>
                                        {copyLabel(record.id)}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
                {config.fields.map((field) => (
                    <div
                        key={field.key}
                        className={cn(
                            "flex flex-col gap-1.5",
                            field.cityStateZip ? "col-span-2" : field.half ? "col-span-2 sm:col-span-3" : "col-span-2 sm:col-span-6",
                        )}
                    >
                        <Label htmlFor={`${idPrefix}-${field.key}`}>{field.label}</Label>
                        <Input
                            id={`${idPrefix}-${field.key}`}
                            type={field.type ?? "text"}
                            value={values[field.key] ?? ""}
                            placeholder={field.placeholder}
                            onChange={(event) => setValues((prev) => ({ ...prev, [field.key]: event.target.value }))}
                            disabled={saving}
                        />
                    </div>
                ))}
            </div>
            {error && (
                <p role="alert" className="text-sm text-destructive">
                    {error}
                </p>
            )}
            <div className="flex flex-wrap gap-2">
                <Button type="submit" size="sm" disabled={saving}>
                    {saving && <Loader2Icon className="size-3.5 animate-spin" />}
                    {saving ? "Saving" : "Save record"}
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
                    Cancel
                </Button>
            </div>
        </form>
    )
}
