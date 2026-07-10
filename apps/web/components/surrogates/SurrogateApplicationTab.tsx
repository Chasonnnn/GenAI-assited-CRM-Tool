"use client"

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    CopyIcon,
    CheckIcon,
    XIcon,
    ChevronDownIcon,
    ChevronUpIcon,
    FileTextIcon,
    DownloadIcon,
    AlertTriangleIcon,
    SendIcon,
    ClipboardCheckIcon,
    Loader2Icon,
    PencilIcon,
    SaveIcon,
    EditIcon,
    PlusIcon,
    Trash2Icon,
    UploadIcon,
} from "lucide-react"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import {
    useApproveFormSubmission,
    useSurrogateFormSubmission,
    useSurrogateFormDraftStatus,
    useFormIntakeLinks,
    useSendFormIntakeLink,
    useRejectFormSubmission,
    useUpdateSubmissionAnswers,
    useUploadSubmissionFile,
    useDeleteSubmissionFile,
} from "@/lib/hooks/use-forms"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import {
    exportSubmissionPdf,
    getSubmissionFileDownloadUrl,
    type FormIntakeLinkRead,
    type FormSchema,
    type FormSubmissionFileRead,
    type FormSubmissionRead,
    type FormSummary,
} from "@/lib/api/forms"
import { getFormOptionLabel, getFormOptionLabels } from "@/lib/forms/option-labels"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { cn } from "@/lib/utils"
import { openDownloadUrlWithSpreadsheetWarning } from "@/lib/utils/csv-download-warning"

interface SurrogateApplicationTabProps {
    surrogateId: string
    formId: string | null
    publishedForms?: FormSummary[]
}

const EMPTY_PUBLISHED_FORMS: FormSummary[] = []

function resolveIntakeLink(baseUrl: string, link: FormIntakeLinkRead): string {
    const serverUrl = link.intake_url?.trim()
    const fallback = `/intake/${link.slug}`
    const candidate = serverUrl || fallback
    const normalizedBase = baseUrl.trim()

    if (!normalizedBase) return candidate
    try {
        return new URL(candidate, normalizedBase.endsWith("/") ? normalizedBase : `${normalizedBase}/`).toString()
    } catch {
        return candidate
    }
}

// Format file size for display
function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Format date for display
function formatDateTime(dateString: string): string {
    const date = new Date(dateString)
    return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    })
}

type TableRow = Record<string, unknown>
type TableColumn = NonNullable<FormSchema["pages"][number]["fields"][number]["columns"]>[number]

function normalizeTableRows(value: unknown): TableRow[] {
    if (!Array.isArray(value)) return []
    return value.filter((row): row is TableRow => Boolean(row) && typeof row === "object")
}

function resolveTableColumns(
    field: FormSchema["pages"][number]["fields"][number],
    rows: TableRow[],
): TableColumn[] {
    if (field.columns && field.columns.length > 0) {
        return field.columns
    }
    if (rows.length === 0) return []
    return Object.keys(rows[0] || {}).flatMap((key) =>
        key === "row_key"
            ? []
            : [
                  {
                      key,
                      label: key,
                      type: "text" as const,
                      required: false,
                      options: null,
                  },
              ],
    )
}

function resolveFixedTableRows(
    field: FormSchema["pages"][number]["fields"][number],
    value: unknown,
): TableRow[] {
    const configuredRows = field.rows || []
    const existingRows = normalizeTableRows(value)
    const rowMap = new Map<string, TableRow>()

    existingRows.forEach((row) => {
        const rowKey = row.row_key
        if (typeof rowKey === "string" && rowKey) {
            rowMap.set(rowKey, row)
        }
    })

    return configuredRows.map((row) => ({
        ...(rowMap.get(row.key) || {}),
        row_key: row.key,
    }))
}

function formatTableCellValue(
    value: unknown,
    options?: TableColumn["options"],
): string {
    if (value === null || value === undefined || value === "") return "—"
    if (typeof value === "boolean") return value ? "Yes" : "No"
    if (Array.isArray(value)) {
        return value.length ? getFormOptionLabels(options, value).join(", ") : "—"
    }
    return getFormOptionLabel(options, value) ?? String(value)
}

function getFieldValueContent(
    field: FormSchema["pages"][number]["fields"][number],
    value: unknown,
) {
    if (value === null || value === undefined || value === "") {
        return <span className="text-sm text-muted-foreground">Not provided</span>
    }
    if (field.type === "repeatable_table" || field.type === "table") {
        const isFixedTable = field.type === "table"
        const rows = isFixedTable ? resolveFixedTableRows(field, value) : normalizeTableRows(value)
        const columns = resolveTableColumns(field, rows)
        if (rows.length === 0 || columns.length === 0) {
            return <span className="text-sm text-muted-foreground">Not provided</span>
        }
        return (
            <div className="max-w-[360px] overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                    <thead>
                        <tr className="text-muted-foreground">
                            {isFixedTable ? <th className="border-b border-border pb-1 pr-2">Item</th> : null}
                            {columns.map((column) => (
                                <th key={column.key} className="border-b border-border pb-1 pr-2">
                                    {column.label}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, rowIndex) => (
                            <tr key={typeof row.row_key === "string" ? row.row_key : `row-${rowIndex}`}>
                                {isFixedTable ? (
                                    <td className="py-1 pr-2 align-top font-medium">
                                        {field.rows?.find((configuredRow) => configuredRow.key === row.row_key)?.label || "—"}
                                    </td>
                                ) : null}
                                {columns.map((column) => (
                                    <td key={column.key} className="py-1 pr-2 align-top">
                                        {formatTableCellValue(row[column.key], column.options)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )
    }
    if (field.type === "date" && typeof value === "string") {
        return <span className="text-sm text-right">{formatLocalDate(parseDateInput(value))}</span>
    }
    if (typeof value === "boolean") {
        return value ? (
            <Badge variant="default" className="bg-green-500 hover:bg-green-500/80">
                Yes
            </Badge>
        ) : (
            <Badge variant="secondary">No</Badge>
        )
    }
    if (
        typeof value === "string" &&
        (field.type === "select" || field.type === "radio")
    ) {
        return (
            <span className="text-sm text-right">
                {getFormOptionLabel(field.options, value) ?? value}
            </span>
        )
    }
    if (Array.isArray(value)) {
        return value.length ? (
            <span className="text-sm text-right">
                {getFormOptionLabels(field.options, value).join(", ")}
            </span>
        ) : (
            <span className="text-sm text-muted-foreground">Not provided</span>
        )
    }
    return <span className="text-sm text-right">{String(value)}</span>
}

type SelectControlOption = {
    value: string
    label: string
}

function formatSelectControlValue(
    value: string | null | undefined,
    options: readonly SelectControlOption[],
    placeholder: string,
) {
    if (!value) return placeholder
    return options.find((option) => option.value === value)?.label ?? value
}

function SelectControl({
    id,
    value,
    onValueChange,
    options,
    placeholder,
    ariaLabel,
    size = "default",
    triggerClassName,
    contentClassName,
    disabled,
}: {
    id?: string
    value: string
    onValueChange: (value: string) => void
    options: readonly SelectControlOption[]
    placeholder: string
    ariaLabel?: string
    size?: "sm" | "default"
    triggerClassName?: string
    contentClassName?: string
    disabled?: boolean
}) {
    return (
        <Select
            value={value}
            onValueChange={(nextValue) => onValueChange(nextValue ?? "")}
            {...(disabled === undefined ? {} : { disabled })}
        >
            <SelectTrigger
                {...(id ? { id } : {})}
                {...(ariaLabel ? { "aria-label": ariaLabel } : {})}
                size={size}
                {...(triggerClassName ? { className: triggerClassName } : {})}
            >
                <SelectValue>
                    {(selectedValue: string | null) =>
                        formatSelectControlValue(selectedValue, options, placeholder)
                    }
                </SelectValue>
            </SelectTrigger>
            <SelectContent {...(contentClassName ? { className: contentClassName } : {})}>
                <SelectGroup>
                    <SelectItem value="">{placeholder}</SelectItem>
                    {options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectGroup>
            </SelectContent>
        </Select>
    )
}

type ApplicationField = FormSchema["pages"][number]["fields"][number]

function SurrogateApplicationLoadingCard() {
    return (
        <Card>
            <CardContent className="flex items-center justify-center py-16">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading application</span>
            </CardContent>
        </Card>
    )
}

function SurrogateApplicationErrorCard() {
    return (
        <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                <AlertTriangleIcon className="size-12 text-amber-500 mb-4" />
                <h3 className="text-lg font-semibold mb-2">Unable to load application</h3>
                <p className="text-sm text-muted-foreground max-w-md">
                    Please refresh the page or try again later.
                </p>
            </CardContent>
        </Card>
    )
}

function SurrogateApplicationFieldEditor({
    field,
    value,
    onFieldChange,
}: {
    field: ApplicationField
    value: unknown
    onFieldChange: (fieldKey: string, value: unknown) => void
}) {
    if (field.type === "repeatable_table" || field.type === "table") {
        const isFixedTable = field.type === "table"
        const rows = isFixedTable ? resolveFixedTableRows(field, value) : normalizeTableRows(value)
        const columns = resolveTableColumns(field, rows)
        const minRows = field.min_rows ?? 0
        const maxRows = field.max_rows ?? null
        const configuredRows = field.rows || []

        if (columns.length === 0) {
            return <span className="text-xs text-muted-foreground">No columns configured</span>
        }

        const addRow = () => {
            if (isFixedTable) return
            if (maxRows !== null && rows.length >= maxRows) return
            const nextRow: TableRow = {}
            columns.forEach((column) => {
                nextRow[column.key] = ""
            })
            onFieldChange(field.key, [...rows, nextRow])
        }

        const updateRow = (rowIndex: number, columnKey: string, nextValue: string) => {
            const nextRows = rows.map((row, index) =>
                index === rowIndex ? { ...row, [columnKey]: nextValue } : row,
            )
            onFieldChange(field.key, nextRows)
        }

        const removeRow = (rowIndex: number) => {
            if (isFixedTable) return
            if (rows.length <= minRows) return
            const nextRows = rows.filter((_, index) => index !== rowIndex)
            onFieldChange(field.key, nextRows)
        }

        return (
            <div className="space-y-2">
                {!isFixedTable && rows.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No rows added yet.</p>
                ) : (
                    <div className="space-y-2">
                        {rows.map((row, rowIndex) => (
                            <div
                                key={typeof row.row_key === "string" ? row.row_key : `row-${rowIndex}`}
                                className="rounded-md border border-border p-2"
                            >
                                {isFixedTable ? (
                                    <div className="mb-2">
                                        <div className="text-sm font-medium text-foreground">
                                            {configuredRows.find((configuredRow) => configuredRow.key === row.row_key)?.label ||
                                                `Row ${rowIndex + 1}`}
                                        </div>
                                        {configuredRows.find((configuredRow) => configuredRow.key === row.row_key)?.help_text ? (
                                            <p className="text-xs text-muted-foreground">
                                                {configuredRows.find((configuredRow) => configuredRow.key === row.row_key)?.help_text}
                                            </p>
                                        ) : null}
                                    </div>
                                ) : null}
                                <div className="grid gap-2 md:grid-cols-2">
                                    {columns.map((column) => {
                                        const cellValue = row[column.key]
                                        const valueText =
                                            cellValue === null || cellValue === undefined
                                                ? ""
                                                : String(cellValue)
                                        return (
                                            <div key={column.key} className="space-y-1">
                                                <Label className="text-xs text-muted-foreground">
                                                    {column.label}
                                                </Label>
                                                {column.type === "select" || column.type === "radio" ? (
                                                    <SelectControl
                                                        value={valueText}
                                                        onValueChange={(nextValue) =>
                                                            updateRow(rowIndex, column.key, nextValue)
                                                        }
                                                        options={(column.options || []).map((option) => ({
                                                            value: option.value,
                                                            label: option.label,
                                                        }))}
                                                        placeholder="Select"
                                                        ariaLabel={column.label}
                                                        size="sm"
                                                        triggerClassName="w-full"
                                                    />
                                                ) : column.type === "textarea" ? (
                                                    <Textarea
                                                        value={valueText}
                                                        onChange={(event) =>
                                                            updateRow(rowIndex, column.key, event.target.value)
                                                        }
                                                        rows={3}
                                                    />
                                                ) : (
                                                    <Input
                                                        type={
                                                            column.type === "number"
                                                                ? "number"
                                                                : column.type === "date"
                                                                  ? "date"
                                                                  : "text"
                                                        }
                                                        value={valueText}
                                                        onChange={(event) =>
                                                            updateRow(rowIndex, column.key, event.target.value)
                                                        }
                                                        className="h-8 text-sm"
                                                    />
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                                {!isFixedTable ? (
                                    <div className="mt-2 flex justify-end">
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => removeRow(rowIndex)}
                                            disabled={rows.length <= minRows}
                                        >
                                            Remove
                                        </Button>
                                    </div>
                                ) : null}
                            </div>
                        ))}
                    </div>
                )}
                {!isFixedTable ? (
                    <div className="flex justify-end">
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={addRow}
                            disabled={maxRows !== null && rows.length >= maxRows}
                        >
                            <PlusIcon className="size-3.5 mr-1" />
                            Add row
                        </Button>
                    </div>
                ) : null}
            </div>
        )
    }

    if (field.type === "textarea") {
        return (
            <Textarea
                value={typeof value === "string" ? value : ""}
                onChange={(event) => onFieldChange(field.key, event.target.value)}
                className="min-h-20 text-sm"
            />
        )
    }

    if (field.type === "date") {
        const dateValue = typeof value === "string" ? value : ""
        return (
            <Input
                type="date"
                value={dateValue}
                onChange={(event) => onFieldChange(field.key, event.target.value)}
                className="h-8 text-sm"
            />
        )
    }

    if (field.type === "select" || field.type === "radio") {
        return (
            <SelectControl
                value={typeof value === "string" ? value : ""}
                onValueChange={(nextValue) => onFieldChange(field.key, nextValue)}
                options={(field.options || []).map((option) => ({
                    value: option.value,
                    label: option.label,
                }))}
                placeholder="Select"
                ariaLabel={field.label}
                size="sm"
                triggerClassName="w-48"
            />
        )
    }

    if (field.type === "multiselect" || field.type === "checkbox") {
        const selectedValues = Array.isArray(value) ? value : []
        const selectedValueSet = new Set(selectedValues)
        return (
            <div className="flex flex-col gap-2">
                {(field.options || []).map((option) => {
                    const checked = selectedValueSet.has(option.value)
                    return (
                        <label key={option.value} className="flex items-center gap-2 text-sm">
                            <Checkbox
                                checked={checked}
                                onCheckedChange={(nextChecked) => {
                                    const isChecked = nextChecked === true
                                    const next = isChecked
                                        ? [...selectedValues, option.value]
                                        : selectedValues.filter((item) => item !== option.value)
                                    onFieldChange(field.key, next)
                                }}
                            />
                            <span>{option.label}</span>
                        </label>
                    )
                })}
            </div>
        )
    }

    const inputType =
        field.type === "email"
            ? "email"
            : field.type === "phone"
              ? "tel"
              : field.type === "number"
                ? "number"
                : "text"

    return (
        <Input
            type={inputType}
            value={
                typeof value === "string"
                    ? value
                    : value !== null && value !== undefined
                      ? String(value)
                      : ""
            }
            onChange={(event) => onFieldChange(field.key, event.target.value)}
            className="h-8 text-sm"
        />
    )
}

type ApplicationEmailTemplateOption = {
    id: string
    name: string
}

type SurrogateApplicationEmptyStateModel = {
    availableForms: FormSummary[]
    baseUrl: string
    canSendLink: boolean
    confirmOverride: boolean
    defaultForm: FormSummary | null
    draftStatus: { started_at?: string | null; updated_at?: string | null } | null | undefined
    emailTemplates: ApplicationEmailTemplateOption[]
    formId: string | null
    formLink: string
    formLinkCopied: boolean
    hasExplicitOverride: boolean
    isSendingLink: boolean
    requiresPurposeOverride: boolean
    selectedForm: FormSummary | null | undefined
    selectedFormId: string
    selectedIntakeLink: FormIntakeLinkRead | null
    selectedIntakeLinkId: string
    selectedTemplateId: string
    sendableIntakeLinks: FormIntakeLinkRead[]
    sendFormModalOpen: boolean
    useAdvancedOverride: boolean
}

type SurrogateApplicationEmptyStateActions = {
    copyFormLink: () => void
    handleGenerateFormLink: () => void
    handleSendEmailLink: () => void
    setConfirmOverride: (value: boolean) => void
    setSelectedFormIdOverride: (value: string) => void
    setSelectedIntakeLinkIdOverride: (value: string) => void
    setSelectedTemplateIdOverride: (value: string) => void
    setSendFormModalOpen: (value: boolean) => void
    setUseAdvancedOverride: (value: boolean) => void
}

function SurrogateApplicationEmptyState({
    actions,
    state,
}: {
    actions: SurrogateApplicationEmptyStateActions
    state: SurrogateApplicationEmptyStateModel
}) {
    return (
        <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                <FileTextIcon className="size-16 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Application Submitted</h3>
                <p className="text-sm text-muted-foreground mb-6 max-w-md">
                    This candidate has not yet submitted their application form. Send them a secure form link to get started.
                </p>
                {state.draftStatus?.started_at && state.draftStatus.updated_at && (
                    <div className="mb-6 w-full max-w-md rounded-xl border border-amber-200/70 bg-amber-50 px-4 py-3 text-left">
                        <div className="flex items-start gap-3">
                            <ClipboardCheckIcon className="mt-0.5 size-5 text-amber-700" />
                            <div className="space-y-1">
                                <div className="text-sm font-medium text-amber-900">Form started</div>
                                <div className="text-xs text-amber-900/70">
                                    Started {formatDateTime(state.draftStatus.started_at)}. Last saved{" "}
                                    {formatDateTime(state.draftStatus.updated_at)}.
                                </div>
                            </div>
                        </div>
                    </div>
                )}
                {state.defaultForm && !state.useAdvancedOverride && (
                    <div className="mb-4 flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                        <span className="text-muted-foreground">Default form:</span>
                        <span className="font-medium text-foreground">{state.defaultForm.name}</span>
                        <Badge variant="secondary" className="text-xs">
                            Published
                        </Badge>
                    </div>
                )}
                {state.availableForms.length > 0 && (
                    <SurrogateApplicationFormOverrideControls actions={actions} state={state} />
                )}
                {!state.defaultForm && state.availableForms.length > 0 && (
                    <div className="mb-4 text-xs text-amber-700">
                        No default surrogate application form is configured. Set one in Form Builder.
                    </div>
                )}
                {state.availableForms.length === 0 && (
                    <div className="mb-4 text-xs text-muted-foreground">
                        No published forms available. Publish a form to generate a link.
                    </div>
                )}
                {state.availableForms.length > 0 && (
                    <div className="mb-4 w-full max-w-xs text-left">
                        <Label htmlFor="intake-link-select" className="mb-2 block text-xs font-medium text-muted-foreground">
                            Shared intake link
                        </Label>
                        <SelectControl
                            id="intake-link-select"
                            value={state.selectedIntakeLinkId}
                            onValueChange={actions.setSelectedIntakeLinkIdOverride}
                            options={state.sendableIntakeLinks.map((link) => ({
                                value: link.id,
                                label: link.campaign_name || link.event_name || link.slug,
                            }))}
                            placeholder={
                                state.sendableIntakeLinks.length === 0
                                    ? "No shared links available"
                                    : "Select shared link"
                            }
                            triggerClassName="w-full"
                            disabled={state.sendableIntakeLinks.length === 0}
                        />
                        <p className="mt-2 text-xs text-muted-foreground">
                            Shared links can be reused by any applicant. Resume and autosave happen on the intake page.
                        </p>
                    </div>
                )}
                <Button
                    className="bg-teal-500 hover:bg-teal-600"
                    onClick={actions.handleGenerateFormLink}
                    disabled={!state.canSendLink || !state.selectedIntakeLink}
                >
                    <SendIcon className="size-4 mr-2" />
                    Send Form Link
                </Button>

                <Dialog open={state.sendFormModalOpen} onOpenChange={actions.setSendFormModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Send Application Form</DialogTitle>
                            <DialogDescription>
                                Use the shared intake URL for this form, then send it through an email template.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                            {state.selectedForm && (
                                <div className="text-sm text-muted-foreground">
                                    Form: <span className="font-medium text-foreground">{state.selectedForm.name}</span>
                                </div>
                            )}
                            {state.hasExplicitOverride && (
                                <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                                    Advanced override is active for this send.
                                </div>
                            )}
                            <div className="rounded-lg border p-4 bg-muted/50">
                                <p className="text-sm font-mono break-all">
                                    {state.formLink || `${state.baseUrl || ""}/intake/[slug]`}
                                </p>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="application-template">Email template</Label>
                                <SelectControl
                                    id="application-template"
                                    value={state.selectedTemplateId}
                                    onValueChange={actions.setSelectedTemplateIdOverride}
                                    options={state.emailTemplates.map((template) => ({
                                        value: template.id,
                                        label: template.name,
                                    }))}
                                    placeholder="Select template"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Uses template variable <code>{"{{form_link}}"}</code> with the selected shared intake URL.
                                </p>
                            </div>
                            <div className="flex items-start gap-2 text-sm text-muted-foreground">
                                <AlertTriangleIcon className="size-4 mt-0.5 shrink-0" />
                                <p>
                                    This is a shared link. Applicants can return later and resume from autosaved progress.
                                </p>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => actions.setSendFormModalOpen(false)}>
                                Close
                            </Button>
                            <Button onClick={actions.copyFormLink} disabled={!state.formLink}>
                                {state.formLinkCopied ? (
                                    <>
                                        <CheckIcon className="size-4 mr-2" />
                                        Copied!
                                    </>
                                ) : (
                                    <>
                                        <CopyIcon className="size-4 mr-2" />
                                        Copy Link
                                    </>
                                )}
                            </Button>
                            <Button
                                onClick={actions.handleSendEmailLink}
                                disabled={!state.formLink || !state.selectedTemplateId || state.isSendingLink}
                            >
                                {state.isSendingLink ? (
                                    <>
                                        <Loader2Icon className="size-4 mr-2 animate-spin" />
                                        Sending
                                    </>
                                ) : (
                                    <>
                                        <SendIcon className="size-4 mr-2" />
                                        Send Email
                                    </>
                                )}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </CardContent>
        </Card>
    )
}

function SurrogateApplicationFormOverrideControls({
    actions,
    state,
}: {
    actions: SurrogateApplicationEmptyStateActions
    state: SurrogateApplicationEmptyStateModel
}) {
    return (
        <div className="mb-4 w-full max-w-xs rounded-lg border p-3 text-left">
            <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">Advanced override</span>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                        const next = !state.useAdvancedOverride
                        actions.setUseAdvancedOverride(next)
                        if (!next) {
                            actions.setConfirmOverride(false)
                        } else {
                            actions.setSelectedFormIdOverride(
                                state.selectedFormId ||
                                    state.availableForms.find((form) => form.id !== (state.formId || ""))?.id ||
                                    "",
                            )
                        }
                    }}
                >
                    {state.useAdvancedOverride
                        ? state.defaultForm
                            ? "Use default"
                            : "Close override"
                        : "Use different form"}
                </Button>
            </div>
            {state.useAdvancedOverride && (
                <div className="space-y-3">
                    <SelectControl
                        value={state.selectedFormId}
                        onValueChange={(nextValue) => {
                            actions.setSelectedFormIdOverride(nextValue)
                            actions.setConfirmOverride(false)
                        }}
                        options={state.availableForms.map((form) => ({
                            value: form.id,
                            label: form.name,
                        }))}
                        placeholder="Choose a form"
                        ariaLabel="Application form"
                        triggerClassName="w-full"
                    />
                    {state.selectedForm && (
                        <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                            You are overriding the default form.
                            {state.requiresPurposeOverride && (
                                <span className="block mt-1">
                                    This form is not marked as <code>surrogate_application</code>.
                                </span>
                            )}
                        </div>
                    )}
                    {state.hasExplicitOverride && (
                        <div className="flex items-start gap-2 text-xs">
                            <Checkbox
                                id="confirm-non-default-form-override"
                                checked={state.confirmOverride}
                                onCheckedChange={(checked) => actions.setConfirmOverride(checked === true)}
                            />
                            <Label
                                htmlFor="confirm-non-default-form-override"
                                className="cursor-pointer text-xs font-normal leading-4"
                            >
                                I confirm I want to send a non-default form for this surrogate.
                            </Label>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

type SurrogateApplicationSubmittedState = {
    approveModalOpen: boolean
    approveNotes: string
    deletingFileId: string | null
    editedValues: Record<string, unknown>
    editingField: string | null
    fileFieldLabels: Map<string, string>
    fileFields: ApplicationField[]
    fileInputId: string
    filesOpen: boolean
    hasEdits: boolean
    isApproving: boolean
    isEditMode: boolean
    isExporting: boolean
    isPending: boolean
    isRejecting: boolean
    pages: FormSchema["pages"]
    previewFields: ApplicationField[]
    rejectModalOpen: boolean
    rejectReason: string
    sectionOpen: Record<number, boolean>
    submission: FormSubmissionRead
    updateAnswersPending: boolean
    uploadFieldKey: string
    uploadFilePending: boolean
}

type SurrogateApplicationSubmittedActions = {
    cancelEditing: () => void
    handleApprove: () => void
    handleCancelEdits: () => void
    handleDeleteFile: (fileId: string, filename: string) => void
    handleDownloadFile: (fileId: string) => void
    handleExport: () => void
    handleFieldChange: (fieldKey: string, value: unknown) => void
    handleFileUpload: React.ChangeEventHandler<HTMLInputElement>
    handleReject: () => void
    handleSaveEdits: () => void
    openFilePicker: () => void
    setApproveModalOpen: (value: boolean) => void
    setApproveNotes: (value: string) => void
    setEditingField: (value: string) => void
    setFilesOpen: (value: boolean) => void
    setIsEditMode: (value: boolean) => void
    setRejectModalOpen: (value: boolean) => void
    setRejectReason: (value: string) => void
    setSectionOpen: (index: number, open: boolean) => void
    setUploadFieldKeyOverride: (value: string) => void
}

function SurrogateApplicationStatusBadge({
    status,
}: {
    status: FormSubmissionRead["status"]
}) {
    if (status === "pending_review") {
        return (
            <Badge variant="default" className="bg-amber-500 hover:bg-amber-500/80">
                Pending Review
            </Badge>
        )
    }

    if (status === "approved") {
        return (
            <Badge variant="default" className="bg-green-500 hover:bg-green-500/80">
                Approved
            </Badge>
        )
    }

    if (status === "rejected") {
        return <Badge variant="destructive">Rejected</Badge>
    }

    return null
}

function SurrogateApplicationSubmittedHeader({
    actions,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    state: SurrogateApplicationSubmittedState
}) {
    const editCount = Object.keys(state.editedValues).length

    return (
        <div className="flex items-center justify-between">
            <div className="space-y-1">
                <div className="flex items-center gap-3">
                    <h2 className="text-xl font-semibold">Application</h2>
                    <SurrogateApplicationStatusBadge status={state.submission.status} />
                </div>
                <p className="text-sm text-muted-foreground">
                    Submitted {formatDateTime(state.submission.submitted_at)}
                </p>
            </div>
            <div className="flex items-center gap-2">
                <Button
                    variant="outline"
                    onClick={actions.handleExport}
                    disabled={state.isExporting}
                >
                    {state.isExporting ? (
                        <Loader2Icon className="size-4 animate-spin mr-2" />
                    ) : (
                        <DownloadIcon className="size-4 mr-2" />
                    )}
                    Export
                </Button>

                {state.isEditMode ? (
                    <>
                        <Button variant="ghost" onClick={actions.handleCancelEdits}>
                            Cancel
                        </Button>
                        <Button
                            onClick={actions.handleSaveEdits}
                            disabled={!state.hasEdits || state.updateAnswersPending}
                            className="bg-primary"
                        >
                            {state.updateAnswersPending ? (
                                <Loader2Icon className="size-4 animate-spin mr-2" />
                            ) : (
                                <SaveIcon className="size-4 mr-2" />
                            )}
                            Save Changes
                            {state.hasEdits && (
                                <Badge variant="secondary" className="ml-2">
                                    {editCount}
                                </Badge>
                            )}
                        </Button>
                    </>
                ) : (
                    <Button onClick={() => actions.setIsEditMode(true)}>
                        <EditIcon className="size-4 mr-2" />
                        Edit
                    </Button>
                )}
            </div>
        </div>
    )
}

function SurrogateApplicationPagesGrid({
    actions,
    fileInputRef,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    fileInputRef: React.RefObject<HTMLInputElement | null>
    state: SurrogateApplicationSubmittedState
}) {
    return (
        <div className="grid gap-4 md:grid-cols-2">
            {state.pages.length === 0 ? (
                <Card>
                    <CardContent className="py-8 text-center text-sm text-muted-foreground">
                        No schema snapshot available for this submission.
                    </CardContent>
                </Card>
            ) : (
                state.pages.map((page, index) => {
                    const pageTitle = page.title || `Page ${index + 1}`
                    const fields = page.fields.filter((field) => field.type !== "file")
                    const isOpen = state.sectionOpen[index] ?? true
                    const pageKey =
                        page.title?.trim() ||
                        page.fields.map((field) => field.key).join("|") ||
                        "page"

                    return (
                        <Card key={pageKey}>
                            <Collapsible
                                open={isOpen}
                                onOpenChange={(open) => actions.setSectionOpen(index, open)}
                            >
                                <CardHeader className="pb-3">
                                    <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-70 transition-opacity">
                                        <CardTitle>{pageTitle}</CardTitle>
                                        {isOpen ? (
                                            <ChevronUpIcon className="size-4 text-muted-foreground" />
                                        ) : (
                                            <ChevronDownIcon className="size-4 text-muted-foreground" />
                                        )}
                                    </CollapsibleTrigger>
                                </CardHeader>
                                <CollapsibleContent>
                                    <CardContent className="space-y-3">
                                        {fields.length === 0 ? (
                                            <p className="text-sm text-muted-foreground">
                                                No fields on this page.
                                            </p>
                                        ) : (
                                            fields.map((field) => (
                                                <SurrogateApplicationSubmittedField
                                                    key={field.key}
                                                    actions={actions}
                                                    field={field}
                                                    state={state}
                                                />
                                            ))
                                        )}
                                    </CardContent>
                                </CollapsibleContent>
                            </Collapsible>
                        </Card>
                    )
                })
            )}

            <SurrogateApplicationFilesCard
                actions={actions}
                fileInputRef={fileInputRef}
                state={state}
            />
        </div>
    )
}

function SurrogateApplicationSubmittedField({
    actions,
    field,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    field: ApplicationField
    state: SurrogateApplicationSubmittedState
}) {
    const originalValue = state.submission.answers[field.key]
    const editedValue = state.editedValues[field.key]
    const isEditing = state.isEditMode && state.editingField === field.key
    const hasEdit = editedValue !== undefined
    const displayValue = hasEdit ? editedValue : originalValue
    const isTableField = field.type === "repeatable_table" || field.type === "table"
    const fieldValueContent = getFieldValueContent(field, displayValue)
    const valueWrapperClass = cn(
        hasEdit && "bg-yellow-100 dark:bg-yellow-900/30 px-1.5 py-0.5 rounded",
    )

    return (
        <div className="flex justify-between items-start gap-4 group py-1">
            <span className="text-sm text-muted-foreground flex-shrink-0">
                {field.label}
            </span>
            <div className="flex items-center gap-2">
                {isEditing ? (
                    <div className={cn("flex gap-2", isTableField ? "items-start" : "items-center")}>
                        <SurrogateApplicationFieldEditor
                            field={field}
                            value={editedValue ?? originalValue}
                            onFieldChange={actions.handleFieldChange}
                        />
                        <Button
                            size="sm"
                            variant="ghost"
                            className="size-7 p-0"
                            onClick={actions.cancelEditing}
                            aria-label={`Cancel editing ${field.label || field.key || "field"}`}
                        >
                            <XIcon className="size-3.5" />
                        </Button>
                    </div>
                ) : (
                    <>
                        {isTableField ? (
                            <div className={valueWrapperClass}>{fieldValueContent}</div>
                        ) : (
                            <span className={valueWrapperClass}>{fieldValueContent}</span>
                        )}
                        {state.isEditMode && (
                            <Button
                                size="sm"
                                variant="ghost"
                                className="size-6 p-0 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                                onClick={() => actions.setEditingField(field.key)}
                                aria-label={`Edit ${field.label || field.key || "field"}`}
                            >
                                <PencilIcon className="size-3" />
                            </Button>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

function SurrogateApplicationFilesCard({
    actions,
    fileInputRef,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    fileInputRef: React.RefObject<HTMLInputElement | null>
    state: SurrogateApplicationSubmittedState
}) {
    const files = state.submission.files

    return (
        <Card>
            <Collapsible open={state.filesOpen} onOpenChange={actions.setFilesOpen}>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between w-full">
                        <CollapsibleTrigger className="flex items-center gap-2 hover:opacity-70 transition-opacity">
                            <CardTitle>Uploaded Files ({files.length})</CardTitle>
                            {state.filesOpen ? (
                                <ChevronUpIcon className="size-4 text-muted-foreground" />
                            ) : (
                                <ChevronDownIcon className="size-4 text-muted-foreground" />
                            )}
                        </CollapsibleTrigger>

                        {state.isEditMode && state.fileFields.length > 0 && (
                            <div className="flex flex-col items-end gap-1.5">
                                <div className="flex items-center gap-2">
                                    {state.fileFields.length > 1 && (
                                        <SelectControl
                                            value={state.uploadFieldKey}
                                            onValueChange={actions.setUploadFieldKeyOverride}
                                            options={state.fileFields.map((field) => ({
                                                value: field.key,
                                                label: field.label,
                                            }))}
                                            placeholder="Select field"
                                            ariaLabel="Upload field"
                                            size="sm"
                                            triggerClassName="h-8 text-xs"
                                        />
                                    )}
                                    <input
                                        id={state.fileInputId}
                                        name="surrogate_submission_upload"
                                        ref={fileInputRef}
                                        type="file"
                                        className="hidden"
                                        aria-label="Upload application file"
                                        onChange={actions.handleFileUpload}
                                        accept="*/*"
                                    />
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 gap-1.5 text-xs border-dashed border-primary/50 text-primary hover:bg-primary/5 hover:border-primary"
                                        onClick={actions.openFilePicker}
                                        disabled={
                                            state.uploadFilePending ||
                                            (state.fileFields.length > 1 && !state.uploadFieldKey)
                                        }
                                    >
                                        {state.uploadFilePending ? (
                                            <Loader2Icon className="size-3.5 animate-spin" />
                                        ) : (
                                            <PlusIcon className="size-3.5" />
                                        )}
                                        Upload File
                                    </Button>
                                </div>
                                {state.fileFields.length > 1 && (
                                    <p className="text-xs text-muted-foreground">
                                        Choose a file field to enable upload.
                                    </p>
                                )}
                            </div>
                        )}
                        {state.isEditMode && state.fileFields.length === 0 && (
                            <span className="text-xs text-muted-foreground">
                                No file fields configured
                            </span>
                        )}
                    </div>
                </CardHeader>
                <CollapsibleContent>
                    <CardContent className="space-y-3">
                        {files.length === 0 ? (
                            <div className="py-6 text-center">
                                <UploadIcon className="size-8 mx-auto mb-2 text-muted-foreground/40" />
                                <p className="text-sm text-muted-foreground">No files uploaded</p>
                                {state.isEditMode && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="mt-2 text-primary hover:text-primary/80"
                                        onClick={actions.openFilePicker}
                                    >
                                        <PlusIcon className="size-4 mr-1" />
                                        Add a file
                                    </Button>
                                )}
                            </div>
                        ) : (
                            files.map((file) => (
                                <SurrogateApplicationFileRow
                                    key={file.id}
                                    actions={actions}
                                    fieldLabel={
                                        file.field_key
                                            ? state.fileFieldLabels.get(file.field_key)
                                            : null
                                    }
                                    file={file}
                                    isDeleting={state.deletingFileId === file.id}
                                    isEditMode={state.isEditMode}
                                />
                            ))
                        )}
                    </CardContent>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    )
}

function SurrogateApplicationFileRow({
    actions,
    fieldLabel,
    file,
    isDeleting,
    isEditMode,
}: {
    actions: SurrogateApplicationSubmittedActions
    fieldLabel: string | null | undefined
    file: FormSubmissionFileRead
    isDeleting: boolean
    isEditMode: boolean
}) {
    return (
        <div
            className={cn(
                "flex items-center justify-between p-3 rounded-lg border transition-all",
                file.quarantined
                    ? "border-amber-500/50 bg-amber-500/10"
                    : "bg-card hover:bg-accent/50",
                isDeleting && "opacity-50",
            )}
        >
            <div className="flex items-center gap-3 min-w-0 flex-1">
                {file.quarantined ? (
                    <AlertTriangleIcon className="size-8 text-amber-500 shrink-0" />
                ) : (
                    <FileTextIcon className="size-8 text-muted-foreground shrink-0" />
                )}
                <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{file.filename}</p>
                    {fieldLabel && (
                        <p className="text-xs text-muted-foreground">
                            Field: {fieldLabel}
                        </p>
                    )}
                    <p
                        className={cn(
                            "text-xs",
                            file.quarantined ? "text-amber-600" : "text-muted-foreground",
                        )}
                    >
                        {file.quarantined ? "Virus scan pending" : formatFileSize(file.file_size)}
                    </p>
                </div>
            </div>

            <div className="flex items-center gap-1 shrink-0">
                <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    disabled={file.quarantined}
                    onClick={() => actions.handleDownloadFile(file.id)}
                    aria-label={`Download ${file.filename}`}
                >
                    <DownloadIcon className="size-4" aria-hidden="true" />
                </Button>

                {isEditMode && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        onClick={() => actions.handleDeleteFile(file.id, file.filename)}
                        disabled={isDeleting}
                        aria-label={`Delete ${file.filename}`}
                    >
                        {isDeleting ? (
                            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                        ) : (
                            <Trash2Icon className="size-4" aria-hidden="true" />
                        )}
                    </Button>
                )}
            </div>
        </div>
    )
}

function SurrogateApplicationReviewFooter({
    actions,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    state: SurrogateApplicationSubmittedState
}) {
    if (!state.isPending) return null

    return (
        <div className="sticky bottom-0 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 p-4 -mx-4 md:-mx-6">
            <div className="flex items-center justify-end gap-3">
                <Button
                    variant="outline"
                    className="text-destructive hover:text-destructive bg-transparent"
                    onClick={() => actions.setRejectModalOpen(true)}
                >
                    <XIcon className="size-4 mr-2" />
                    Reject
                </Button>
                <Button
                    className="bg-teal-500 hover:bg-teal-600"
                    onClick={() => actions.setApproveModalOpen(true)}
                >
                    <ClipboardCheckIcon className="size-4 mr-2" />
                    Approve & Update Surrogate
                </Button>
            </div>
        </div>
    )
}

function SurrogateApplicationReviewDialogs({
    actions,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    state: SurrogateApplicationSubmittedState
}) {
    return (
        <>
            <Dialog open={state.rejectModalOpen} onOpenChange={actions.setRejectModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Reject Application</DialogTitle>
                        <DialogDescription>
                            Please provide a reason for rejecting this application.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div>
                            <Label htmlFor="reject-reason">Rejection Reason *</Label>
                            <Textarea
                                id="reject-reason"
                                placeholder="Explain why this application is being rejected"
                                className="mt-2 min-h-24"
                                value={state.rejectReason}
                                onChange={(event) => actions.setRejectReason(event.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => actions.setRejectModalOpen(false)}
                            disabled={state.isRejecting}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            disabled={!state.rejectReason.trim() || state.isRejecting}
                            onClick={actions.handleReject}
                        >
                            {state.isRejecting && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                            Reject Application
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={state.approveModalOpen} onOpenChange={actions.setApproveModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Approve Application</DialogTitle>
                        <DialogDescription>
                            The following Surrogate fields will be updated with information from this application:
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="rounded-lg border p-4 space-y-2 text-sm">
                            {state.previewFields.length === 0 ? (
                                <p className="text-muted-foreground">
                                    Surrogate fields will be updated based on configured mappings.
                                </p>
                            ) : (
                                state.previewFields.map((field) => (
                                    <div key={field.key} className="flex justify-between">
                                        <span className="text-muted-foreground">{field.label}</span>
                                        {getFieldValueContent(field, state.submission.answers[field.key])}
                                    </div>
                                ))
                            )}
                        </div>
                        <div>
                            <Label htmlFor="approve-notes">Optional Notes</Label>
                            <Textarea
                                id="approve-notes"
                                placeholder="Add any notes about this approval"
                                className="mt-2 min-h-20"
                                value={state.approveNotes}
                                onChange={(event) => actions.setApproveNotes(event.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => actions.setApproveModalOpen(false)}
                            disabled={state.isApproving}
                        >
                            Cancel
                        </Button>
                        <Button
                            className="bg-teal-500 hover:bg-teal-600"
                            onClick={actions.handleApprove}
                            disabled={state.isApproving}
                        >
                            {state.isApproving && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                            Approve & Update
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}

function SurrogateApplicationSubmittedView({
    actions,
    fileInputRef,
    state,
}: {
    actions: SurrogateApplicationSubmittedActions
    fileInputRef: React.RefObject<HTMLInputElement | null>
    state: SurrogateApplicationSubmittedState
}) {
    return (
        <div className="space-y-4">
            <SurrogateApplicationSubmittedHeader actions={actions} state={state} />
            <SurrogateApplicationPagesGrid
                actions={actions}
                fileInputRef={fileInputRef}
                state={state}
            />
            <SurrogateApplicationReviewFooter actions={actions} state={state} />
            <SurrogateApplicationReviewDialogs actions={actions} state={state} />
        </div>
    )
}

type SurrogateApplicationEmptyStateRenderInput = {
    baseUrl: string
    confirmOverride: boolean
    copyFormLink: () => Promise<void>
    draftStatus: SurrogateApplicationEmptyStateModel["draftStatus"]
    effectiveFormId: string
    emailTemplates: ApplicationEmailTemplateOption[]
    formId: string | null
    formLink: string
    formLinkCopied: boolean
    handleGenerateFormLink: () => Promise<void>
    handleSendEmailLink: () => Promise<void>
    isSendingLink: boolean
    publishedForms: FormSummary[]
    requiresPurposeOverride: boolean
    selectedFormId: string
    selectedIntakeLink: FormIntakeLinkRead | null
    selectedIntakeLinkId: string
    selectedTemplateId: string
    sendableIntakeLinks: FormIntakeLinkRead[]
    sendFormModalOpen: boolean
    setConfirmOverride: (value: boolean) => void
    setSelectedFormIdOverride: (value: string) => void
    setSelectedIntakeLinkIdOverride: (value: string) => void
    setSelectedTemplateIdOverride: (value: string) => void
    setSendFormModalOpen: (value: boolean) => void
    setUseAdvancedOverride: (value: boolean) => void
    useAdvancedOverride: boolean
}

function renderSurrogateApplicationEmptyState(input: SurrogateApplicationEmptyStateRenderInput) {
    const availableForms = input.publishedForms
    const defaultForm = availableForms.find((form) => form.id === input.formId) || null
    const selectedForm =
        availableForms.find((form) => form.id === input.effectiveFormId) ?? defaultForm
    const hasExplicitOverride =
        input.useAdvancedOverride &&
        input.selectedFormId.length > 0 &&
        input.selectedFormId !== (input.formId || "")
    const canSendLink =
        Boolean(input.effectiveFormId) && (!hasExplicitOverride || input.confirmOverride)

    return (
        <SurrogateApplicationEmptyState
            actions={{
                copyFormLink: () => {
                    void input.copyFormLink()
                },
                handleGenerateFormLink: () => {
                    void input.handleGenerateFormLink()
                },
                handleSendEmailLink: () => {
                    void input.handleSendEmailLink()
                },
                setConfirmOverride: input.setConfirmOverride,
                setSelectedFormIdOverride: input.setSelectedFormIdOverride,
                setSelectedIntakeLinkIdOverride: input.setSelectedIntakeLinkIdOverride,
                setSelectedTemplateIdOverride: input.setSelectedTemplateIdOverride,
                setSendFormModalOpen: input.setSendFormModalOpen,
                setUseAdvancedOverride: input.setUseAdvancedOverride,
            }}
            state={{
                availableForms,
                baseUrl: input.baseUrl,
                canSendLink,
                confirmOverride: input.confirmOverride,
                defaultForm,
                draftStatus: input.draftStatus,
                emailTemplates: input.emailTemplates,
                formId: input.formId,
                formLink: input.formLink,
                formLinkCopied: input.formLinkCopied,
                hasExplicitOverride,
                isSendingLink: input.isSendingLink,
                requiresPurposeOverride: input.requiresPurposeOverride,
                selectedForm,
                selectedFormId: input.selectedFormId,
                selectedIntakeLink: input.selectedIntakeLink,
                selectedIntakeLinkId: input.selectedIntakeLinkId,
                selectedTemplateId: input.selectedTemplateId,
                sendableIntakeLinks: input.sendableIntakeLinks,
                sendFormModalOpen: input.sendFormModalOpen,
                useAdvancedOverride: input.useAdvancedOverride,
            }}
        />
    )
}

type SurrogateApplicationSubmittedRenderInput = SurrogateApplicationSubmittedState & {
    cancelEditing: () => void
    handleApprove: () => Promise<void>
    handleCancelEdits: () => void
    handleDeleteFile: (fileId: string, filename: string) => Promise<void>
    handleDownloadFile: (fileId: string) => Promise<void>
    handleExport: () => Promise<void>
    handleFieldChange: (fieldKey: string, value: unknown) => void
    handleFileUpload: (event: React.ChangeEvent<HTMLInputElement>) => Promise<void>
    handleReject: () => Promise<void>
    handleSaveEdits: () => Promise<void>
    openFilePicker: () => void
    setApproveModalOpen: (value: boolean) => void
    setApproveNotes: (value: string) => void
    setEditingField: (value: string) => void
    setFilesOpen: (value: boolean) => void
    setIsEditMode: (value: boolean) => void
    setRejectModalOpen: (value: boolean) => void
    setRejectReason: (value: string) => void
    setSectionOpen: React.Dispatch<React.SetStateAction<Record<number, boolean>>>
    setUploadFieldKeyOverride: (value: string) => void
}

function SurrogateApplicationSubmittedRenderer({
    fileInputRef,
    input,
}: {
    fileInputRef: React.RefObject<HTMLInputElement | null>
    input: SurrogateApplicationSubmittedRenderInput
}) {
    return (
        <SurrogateApplicationSubmittedView
            actions={{
                cancelEditing: input.cancelEditing,
                handleApprove: () => {
                    void input.handleApprove()
                },
                handleCancelEdits: input.handleCancelEdits,
                handleDeleteFile: (fileId, filename) => {
                    void input.handleDeleteFile(fileId, filename)
                },
                handleDownloadFile: (fileId) => {
                    void input.handleDownloadFile(fileId)
                },
                handleExport: () => {
                    void input.handleExport()
                },
                handleFieldChange: input.handleFieldChange,
                handleFileUpload: (event) => {
                    void input.handleFileUpload(event)
                },
                handleReject: () => {
                    void input.handleReject()
                },
                handleSaveEdits: () => {
                    void input.handleSaveEdits()
                },
                openFilePicker: input.openFilePicker,
                setApproveModalOpen: input.setApproveModalOpen,
                setApproveNotes: input.setApproveNotes,
                setEditingField: input.setEditingField,
                setFilesOpen: input.setFilesOpen,
                setIsEditMode: input.setIsEditMode,
                setRejectModalOpen: input.setRejectModalOpen,
                setRejectReason: input.setRejectReason,
                setSectionOpen: (index, open) =>
                    input.setSectionOpen((prev) => ({ ...prev, [index]: open })),
                setUploadFieldKeyOverride: input.setUploadFieldKeyOverride,
            }}
            fileInputRef={fileInputRef}
            state={{
                approveModalOpen: input.approveModalOpen,
                approveNotes: input.approveNotes,
                deletingFileId: input.deletingFileId,
                editedValues: input.editedValues,
                editingField: input.editingField,
                fileFieldLabels: input.fileFieldLabels,
                fileFields: input.fileFields,
                fileInputId: input.fileInputId,
                filesOpen: input.filesOpen,
                hasEdits: input.hasEdits,
                isApproving: input.isApproving,
                isEditMode: input.isEditMode,
                isExporting: input.isExporting,
                isPending: input.isPending,
                isRejecting: input.isRejecting,
                pages: input.pages,
                previewFields: input.previewFields,
                rejectModalOpen: input.rejectModalOpen,
                rejectReason: input.rejectReason,
                sectionOpen: input.sectionOpen,
                submission: input.submission,
                updateAnswersPending: input.updateAnswersPending,
                uploadFieldKey: input.uploadFieldKey,
                uploadFilePending: input.uploadFilePending,
            }}
        />
    )
}

type SurrogateApplicationLinkHandlersInput = {
    baseUrl: string
    confirmOverride: boolean
    effectiveFormId: string
    formLink: string
    selectedIntakeLink: FormIntakeLinkRead | null
    selectedTemplateId: string
    sendIntakeLinkMutation: ReturnType<typeof useSendFormIntakeLink>
    setFormLink: (value: string) => void
    setFormLinkCopied: (value: boolean) => void
    setIsSendingLink: (value: boolean) => void
    setSendFormModalOpen: (value: boolean) => void
    surrogateId: string
    useAdvancedOverride: boolean
}

function createSurrogateApplicationLinkHandlers(input: SurrogateApplicationLinkHandlersInput) {
    const copyFormLink = async () => {
        if (!input.formLink) {
            toast.error("Generate a form link first")
            return
        }
        await navigator.clipboard.writeText(input.formLink)
        input.setFormLinkCopied(true)
        toast.success("Form link copied to clipboard")
        setTimeout(() => input.setFormLinkCopied(false), 2000)
    }

    const handleGenerateFormLink = async () => {
        if (!input.effectiveFormId) {
            toast.error("No default application form is configured")
            return
        }
        if (input.useAdvancedOverride && !input.confirmOverride) {
            toast.error("Confirm advanced override before sending")
            return
        }
        if (!input.selectedIntakeLink) {
            toast.error("No shared intake link is available for this form")
            return
        }
        input.setFormLink(resolveIntakeLink(input.baseUrl, input.selectedIntakeLink))
        input.setFormLinkCopied(false)
        input.setSendFormModalOpen(true)
    }

    const handleSendEmailLink = async () => {
        if (!input.effectiveFormId || !input.selectedIntakeLink) {
            toast.error("Select a shared intake link first")
            return
        }
        if (!input.selectedTemplateId) {
            toast.error("Select an email template")
            return
        }
        input.setIsSendingLink(true)
        const finishSending = () => input.setIsSendingLink(false)
        try {
            const response = await input.sendIntakeLinkMutation.mutateAsync({
                formId: input.effectiveFormId,
                linkId: input.selectedIntakeLink.id,
                surrogateId: input.surrogateId,
                templateId: input.selectedTemplateId,
            })
            input.setFormLink(
                response.intake_url || resolveIntakeLink(input.baseUrl, input.selectedIntakeLink),
            )
            toast.success("Application link sent")
            finishSending()
        } catch {
            toast.error("Failed to send application link")
            finishSending()
        }
    }

    return { copyFormLink, handleGenerateFormLink, handleSendEmailLink }
}

type SurrogateApplicationFileHandlersInput = {
    deleteFileMutation: ReturnType<typeof useDeleteSubmissionFile>
    setDeletingFileId: (value: string | null) => void
    submission: FormSubmissionRead | null | undefined
    submissionFileFields: ApplicationField[]
    uploadFieldKey: string
    uploadFileMutation: ReturnType<typeof useUploadSubmissionFile>
}

function createSurrogateApplicationFileHandlers(input: SurrogateApplicationFileHandlersInput) {
    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const target = event.currentTarget
        const file = target.files?.[0]
        if (!file || !input.submission) return
        const clearInput = () => {
            target.value = ""
        }
        if (!input.submission.surrogate_id) {
            toast.error("Resolve submission match before uploading files.")
            clearInput()
            return
        }

        if (input.submissionFileFields.length > 1 && !input.uploadFieldKey) {
            toast.error("Select a file field first")
            clearInput()
            return
        }

        try {
            await input.uploadFileMutation.mutateAsync({
                submissionId: input.submission.id,
                file,
                formId: input.submission.form_id,
                surrogateId: input.submission.surrogate_id,
                fieldKey: input.uploadFieldKey || null,
            })
            toast.success(`Uploaded: ${file.name}`)
            clearInput()
        } catch {
            toast.error("Failed to upload file")
            clearInput()
        }
    }

    const handleDeleteFile = async (fileId: string, filename: string) => {
        if (!input.submission) return
        if (!input.submission.surrogate_id) {
            toast.error("Resolve submission match before deleting files.")
            return
        }

        input.setDeletingFileId(fileId)
        const finishDeleting = () => input.setDeletingFileId(null)
        try {
            await input.deleteFileMutation.mutateAsync({
                submissionId: input.submission.id,
                fileId,
                formId: input.submission.form_id,
                surrogateId: input.submission.surrogate_id,
            })
            toast.success(`Deleted: ${filename}`)
            finishDeleting()
        } catch {
            toast.error("Failed to delete file")
            finishDeleting()
        }
    }

    const handleDownloadFile = async (fileId: string) => {
        if (!input.submission) return
        try {
            const response = await getSubmissionFileDownloadUrl(input.submission.id, fileId)
            const opened = openDownloadUrlWithSpreadsheetWarning(
                response.download_url,
                response.filename,
            )
            if (!opened) {
                toast.info(`Download cancelled for ${response.filename}`)
            }
        } catch {
            toast.error("Failed to download file")
        }
    }

    return { handleDeleteFile, handleDownloadFile, handleFileUpload }
}

type SurrogateApplicationReviewHandlersInput = {
    approveMutation: ReturnType<typeof useApproveFormSubmission>
    approveNotes: string
    rejectMutation: ReturnType<typeof useRejectFormSubmission>
    rejectReason: string
    setApproveModalOpen: (value: boolean) => void
    setApproveNotes: (value: string) => void
    setIsApproving: (value: boolean) => void
    setIsExporting: (value: boolean) => void
    setIsRejecting: (value: boolean) => void
    setRejectModalOpen: (value: boolean) => void
    setRejectReason: (value: string) => void
    submission: FormSubmissionRead | null | undefined
}

function createSurrogateApplicationReviewHandlers(input: SurrogateApplicationReviewHandlersInput) {
    const handleApprove = async () => {
        if (!input.submission) return
        input.setIsApproving(true)
        const finishApproving = () => input.setIsApproving(false)
        try {
            await input.approveMutation.mutateAsync({
                submissionId: input.submission.id,
                reviewNotes: input.approveNotes.trim() || null,
            })
            toast.success("Application approved and surrogate updated")
            input.setApproveModalOpen(false)
            input.setApproveNotes("")
            finishApproving()
        } catch {
            toast.error("Failed to approve application")
            finishApproving()
        }
    }

    const handleReject = async () => {
        if (!input.rejectReason.trim() || !input.submission) return
        input.setIsRejecting(true)
        const finishRejecting = () => input.setIsRejecting(false)
        try {
            await input.rejectMutation.mutateAsync({
                submissionId: input.submission.id,
                reviewNotes: input.rejectReason.trim(),
            })
            toast.success("Application rejected")
            input.setRejectModalOpen(false)
            input.setRejectReason("")
            finishRejecting()
        } catch {
            toast.error("Failed to reject application")
            finishRejecting()
        }
    }

    const handleExport = async () => {
        if (!input.submission) return
        input.setIsExporting(true)
        const finishExporting = () => input.setIsExporting(false)
        try {
            await exportSubmissionPdf(input.submission.id)
            toast.success("Application exported as PDF")
            finishExporting()
        } catch {
            toast.error("Failed to export application")
            finishExporting()
        }
    }

    return { handleApprove, handleExport, handleReject }
}

export function SurrogateApplicationTab({
    surrogateId,
    formId,
    publishedForms = EMPTY_PUBLISHED_FORMS,
}: SurrogateApplicationTabProps) {
    const { user } = useAuth()
    const baseUrl =
        user?.org_portal_base_url ||
        (typeof window !== "undefined" ? window.location.origin : "")

    const [selectedFormIdOverride, setSelectedFormIdOverride] = React.useState<string>("")
    const [useAdvancedOverride, setUseAdvancedOverride] = React.useState(false)
    const [confirmOverride, setConfirmOverride] = React.useState(false)
    const fallbackOverrideFormId =
        publishedForms.find((form) => form.id !== formId)?.id ||
        publishedForms[0]?.id ||
        ""
    const selectedFormId =
        useAdvancedOverride
            ? publishedForms.some((form) => form.id === selectedFormIdOverride)
                ? selectedFormIdOverride
                : fallbackOverrideFormId
            : ""

    const effectiveFormId = useAdvancedOverride ? selectedFormId : formId || ""
    const selectedFormMeta =
        publishedForms.find((form) => form.id === effectiveFormId) || null
    const requiresPurposeOverride =
        selectedFormMeta !== null &&
        (selectedFormMeta.purpose ?? "surrogate_application") !== "surrogate_application"

    const {
        data: submission,
        isLoading,
        error: submissionError,
    } = useSurrogateFormSubmission(effectiveFormId || null, surrogateId)
    const { data: draftStatus } = useSurrogateFormDraftStatus(effectiveFormId || null, surrogateId)
    const { data: intakeLinks = [] } = useFormIntakeLinks(effectiveFormId || null, true)
    const sendIntakeLinkMutation = useSendFormIntakeLink()
    const { data: emailTemplates = [] } = useEmailTemplates({ activeOnly: true, usageContext: "manual" })
    const approveMutation = useApproveFormSubmission()
    const rejectMutation = useRejectFormSubmission()
    const updateAnswersMutation = useUpdateSubmissionAnswers()
    const uploadFileMutation = useUploadSubmissionFile()
    const deleteFileMutation = useDeleteSubmissionFile()
    const fileInputRef = React.useRef<HTMLInputElement>(null)
    const fileInputId = React.useId()
    const [deletingFileId, setDeletingFileId] = React.useState<string | null>(null)
    const [isEditMode, setIsEditMode] = React.useState(false)
    const [isExporting, setIsExporting] = React.useState(false)
    const [uploadFieldKeyOverride, setUploadFieldKeyOverride] = React.useState("")

    const [sectionOpen, setSectionOpen] = React.useState<Record<number, boolean>>({})
    const [filesOpen, setFilesOpen] = React.useState(true)

    const [editingField, setEditingField] = React.useState<string | null>(null)
    const [editedValues, setEditedValues] = React.useState<Record<string, unknown>>({})

    const [rejectModalOpen, setRejectModalOpen] = React.useState(false)
    const [approveModalOpen, setApproveModalOpen] = React.useState(false)
    const [sendFormModalOpen, setSendFormModalOpen] = React.useState(false)

    const [rejectReason, setRejectReason] = React.useState("")
    const [approveNotes, setApproveNotes] = React.useState("")
    const [formLinkCopied, setFormLinkCopied] = React.useState(false)
    const [formLink, setFormLink] = React.useState("")
    const [selectedIntakeLinkIdOverride, setSelectedIntakeLinkIdOverride] = React.useState("")
    const [selectedTemplateIdOverride, setSelectedTemplateIdOverride] = React.useState("")

    const [isApproving, setIsApproving] = React.useState(false)
    const [isRejecting, setIsRejecting] = React.useState(false)
    const [isSendingLink, setIsSendingLink] = React.useState(false)

    const activeIntakeLinks = intakeLinks.filter((link) => link.is_active)
    const sendableIntakeLinks = activeIntakeLinks.length > 0 ? activeIntakeLinks : intakeLinks
    const selectedIntakeLinkId =
        sendableIntakeLinks.some((link) => link.id === selectedIntakeLinkIdOverride)
            ? selectedIntakeLinkIdOverride
            : sendableIntakeLinks[0]?.id || ""
    const selectedIntakeLink =
        sendableIntakeLinks.find((link) => link.id === selectedIntakeLinkId) || null
    const selectedTemplateId =
        emailTemplates.some((template) => template.id === selectedTemplateIdOverride)
            ? selectedTemplateIdOverride
            : emailTemplates[0]?.id || ""
    const submissionPages = submission?.schema_snapshot?.pages || []
    const submissionFileFields = submissionPages.flatMap((page) =>
        page.fields.filter((field) => field.type === "file"),
    )
    const uploadFieldKey =
        submissionFileFields.some((field) => field.key === uploadFieldKeyOverride)
            ? uploadFieldKeyOverride
            : submissionFileFields.length === 1
              ? submissionFileFields[0]?.key || ""
              : ""
    const { handleDeleteFile, handleDownloadFile, handleFileUpload } =
        createSurrogateApplicationFileHandlers({
            deleteFileMutation,
            setDeletingFileId,
            submission,
            submissionFileFields,
            uploadFieldKey,
            uploadFileMutation,
        })

    const { copyFormLink, handleGenerateFormLink, handleSendEmailLink } =
        createSurrogateApplicationLinkHandlers({
            baseUrl,
            confirmOverride,
            effectiveFormId,
            formLink,
            selectedIntakeLink,
            selectedTemplateId,
            sendIntakeLinkMutation,
            setFormLink,
            setFormLinkCopied,
            setIsSendingLink,
            setSendFormModalOpen,
            surrogateId,
            useAdvancedOverride,
        })

    const { handleApprove, handleExport, handleReject } =
        createSurrogateApplicationReviewHandlers({
            approveMutation,
            approveNotes,
            rejectMutation,
            rejectReason,
            setApproveModalOpen,
            setApproveNotes,
            setIsApproving,
            setIsExporting,
            setIsRejecting,
            setRejectModalOpen,
            setRejectReason,
            submission,
        })

    const hasEdits = Object.keys(editedValues).length > 0

    const handleSaveEdits = async () => {
        if (!submission || !hasEdits) return
        try {
            const updates = Object.entries(editedValues).map(([field_key, value]) => ({
                field_key,
                value,
            }))
            const result = await updateAnswersMutation.mutateAsync({
                submissionId: submission.id,
                updates,
            })
            toast.success(
                result.surrogate_updates.length > 0
                    ? `Saved changes (updated ${result.surrogate_updates.length} surrogate fields)`
                    : "Saved changes"
            )
            setEditedValues({})
            setEditingField(null)
        } catch {
            toast.error("Failed to save changes")
        }
    }

    const handleCancelEdits = () => {
        setEditedValues({})
        setEditingField(null)
        setIsEditMode(false)
    }

    const handleFieldChange = (fieldKey: string, value: unknown) => {
        setEditedValues(prev => ({ ...prev, [fieldKey]: value }))
    }

    const cancelEditing = () => {
        setEditingField(null)
        // Remove the edited value for this field
        if (editingField) {
            setEditedValues(prev => {
                const next = { ...prev }
                delete next[editingField]
                return next
            })
        }
    }

    if (isLoading) {
        return <SurrogateApplicationLoadingCard />
    }

    if (submissionError) {
        return <SurrogateApplicationErrorCard />
    }

    if (!submission) {
        return renderSurrogateApplicationEmptyState({
            baseUrl,
            confirmOverride,
            copyFormLink,
            draftStatus,
            effectiveFormId,
            emailTemplates,
            formId,
            formLink,
            formLinkCopied,
            handleGenerateFormLink,
            handleSendEmailLink,
            isSendingLink,
            publishedForms,
            requiresPurposeOverride,
            selectedFormId,
            selectedIntakeLink,
            selectedIntakeLinkId,
            selectedTemplateId,
            sendableIntakeLinks,
            sendFormModalOpen,
            setConfirmOverride,
            setSelectedFormIdOverride,
            setSelectedIntakeLinkIdOverride,
            setSelectedTemplateIdOverride,
            setSendFormModalOpen,
            setUseAdvancedOverride,
            useAdvancedOverride,
        })
    }

    const status = submission.status
    const isPending = status === "pending_review"
    const pages = submissionPages
    const fileFields = submissionFileFields
    const fileFieldLabels = new Map(
        fileFields.map((field) => [field.key, field.label]),
    )
    const previewFields = pages
        .flatMap((page) =>
            page.fields.flatMap((field) => (field.type === "file" ? [] : [field])),
        )
        .slice(0, 3)

    const openFilePicker = () => {
        fileInputRef.current?.click()
    }

    return (
        <SurrogateApplicationSubmittedRenderer
            fileInputRef={fileInputRef}
            input={{
                approveModalOpen,
                approveNotes,
                cancelEditing,
                deletingFileId,
                editedValues,
                editingField,
                fileFieldLabels,
                fileFields,
                fileInputId,
                filesOpen,
                handleApprove,
                handleCancelEdits,
                handleDeleteFile,
                handleDownloadFile,
                handleExport,
                handleFieldChange,
                handleFileUpload,
                handleReject,
                handleSaveEdits,
                hasEdits,
                isApproving,
                isEditMode,
                isExporting,
                isPending,
                isRejecting,
                openFilePicker,
                pages,
                previewFields,
                rejectModalOpen,
                rejectReason,
                sectionOpen,
                setApproveModalOpen,
                setApproveNotes,
                setEditingField,
                setFilesOpen,
                setIsEditMode,
                setRejectModalOpen,
                setRejectReason,
                setSectionOpen,
                setUploadFieldKeyOverride,
                submission,
                updateAnswersPending: updateAnswersMutation.isPending,
                uploadFieldKey,
                uploadFilePending: uploadFileMutation.isPending,
            }}
        />
    )
}
