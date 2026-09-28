"use client"

import { useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { SaveBar } from "@/components/ui/save-bar"
import { toast } from "@/components/ui/toast"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { PaginationJump } from "@/components/ui/pagination-jump"
import { Loader2Icon, ShieldCheck, Trash2 } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
    useCreateLegalHold,
    useExecutePurge,
    useLegalHolds,
    usePurgePreview,
    useReleaseLegalHold,
    useRetentionPolicies,
    useUpsertRetentionPolicy,
} from "@/lib/hooks/use-compliance"
import type { LegalHoldListResponse, PurgePreviewItem } from "@/lib/api/compliance"
import { globalSearch } from "@/lib/api/search"
import { isPermissionError } from "@/lib/error-utils"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { focusFirstInvalid } from "@/lib/forms/use-form-validation"
import { validateIntegerRange } from "@/lib/forms/validators"
import { createSelectLabelGetter } from "@/lib/select-labels"
import { SettingsPageGate } from "../settings-page-gate"

const RETENTION_OPTIONS = [
    { value: "donors", label: "Donors (archived only)" },
    { value: "donor_leads", label: "Donor applications (unconverted only)" },
    { value: "surrogates", label: "Surrogates (archived only)" },
    { value: "matches", label: "Matches" },
    { value: "tasks", label: "Tasks (completed only)" },
    { value: "entity_notes", label: "Notes" },
    { value: "surrogate_activity", label: "Surrogate Activity" },
]

const LEGAL_HOLD_TYPES = [
    { value: "org", label: "Organization (all records)" },
    { value: "donor", label: "Donor" },
    { value: "form_submission", label: "Form Submission" },
    { value: "form_submission_file", label: "Form Submission File" },
    { value: "intake_lead", label: "Intake Lead" },
    { value: "meta_lead", label: "Meta Lead" },
    { value: "surrogate", label: "Surrogate" },
    { value: "match", label: "Match" },
    { value: "task", label: "Task" },
    { value: "entity_notes", label: "Note" },
    { value: "surrogate_activity", label: "Surrogate Activity" },
]

// retention_days 0 is the API's "never purge" value (compliance_service), shown as Keep forever.
type RetentionMode = "forever" | "purge"

type PolicyEdit = {
    mode: RetentionMode
    /** Text while editing, so an empty or partial value can show a field error. */
    days: string
    is_active: boolean
}

type PolicyEdits = Record<string, PolicyEdit>
type PolicyEditOverrides = Record<string, Partial<PolicyEdit>>

const RETENTION_MODE_LABELS: Record<RetentionMode, string> = {
    forever: "Keep forever",
    purge: "Purge after",
}
const getRetentionModeLabel = createSelectLabelGetter(RETENTION_MODE_LABELS, {
    emptyLabel: "Select retention",
    unknownLabel: "Unknown retention",
})
const RETENTION_DAYS_MESSAGE = "Enter 1 or more days."
const getRetentionEntityLabel = createSelectLabelGetter(RETENTION_OPTIONS, {
    emptyLabel: "Unknown record type",
    unknownLabel: "Unknown record type",
})

function toPolicyEdit(retentionDays: number | undefined, isActive: boolean | undefined): PolicyEdit {
    const days = retentionDays ?? 0
    return {
        mode: days > 0 ? "purge" : "forever",
        days: days > 0 ? String(days) : "",
        is_active: isActive ?? true,
    }
}

function getPolicyEditError(edit: PolicyEdit): string | undefined {
    if (edit.mode === "forever") return undefined
    return validateIntegerRange(edit.days, { min: 1, message: RETENTION_DAYS_MESSAGE })
}

function isSamePolicyEdit(left: PolicyEdit, right: PolicyEdit): boolean {
    if (left.mode !== right.mode || left.is_active !== right.is_active) return false
    return left.mode === "forever" || left.days.trim() === right.days.trim()
}

function getComplianceActionError(error: unknown, fallback: string): string | null {
    if (isPermissionError(error)) return "You don't have permission to change compliance settings."
    // Server detail is not shown here; only rate limits (already toasted) return null.
    return getActionErrorMessage(error, fallback) === null ? null : fallback
}

type RetentionPoliciesCardProps = {
    policyEdits: PolicyEdits
    policyErrors: Record<string, string | undefined>
    state: {
        policiesLoading: boolean
        policiesError: unknown
        policiesRetrying: boolean
        saving: boolean
    }
    onPolicyEditChange: (entityType: string, patch: Partial<PolicyEdit>) => void
    onRetry: () => void
}

type LegalHoldFormState = {
    holdType: string
    holdEntityId: string
    holdReason: string
}

// Scopes the global search can look up by name; other scopes take a record ID.
const SEARCHABLE_HOLD_TYPES = new Set(["surrogate", "donor"])
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type LegalHoldsCardProps = {
    form: LegalHoldFormState
    legalHolds: LegalHoldListResponse | undefined
    listState: {
        holdsLoading: boolean
        holdsError: unknown
        holdsRetrying: boolean
        onRetry: () => void
        releaseHoldPending: boolean
    }
    formState: {
        createHoldPending: boolean
    }
    pagination: {
        holdsPage: number
        perPage: number
    }
    onHoldTypeChange: (value: string) => void
    onHoldEntityIdChange: (value: string) => void
    onHoldReasonChange: (value: string) => void
    onCreateHold: () => Promise<void>
    onReleaseHold: (holdId: string) => Promise<unknown>
    onHoldsPageChange: (page: number) => void
}

type RetentionPurgeCardProps = {
    purgeItems: PurgePreviewItem[]
    purgeJobId: string | null
    onPreviewPurge: () => Promise<void>
    onExecutePurge: () => Promise<void>
}

function getLegalHoldTypeLabel(value: string | null) {
    const type = LEGAL_HOLD_TYPES.find((option) => option.value === value)
    return type?.label ?? "Select scope"
}

function RetentionPoliciesCard({
    policyEdits,
    policyErrors,
    state,
    onPolicyEditChange,
    onRetry,
}: RetentionPoliciesCardProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Data Retention Policies</CardTitle>
            </CardHeader>
            <CardContent>
                {state.policiesLoading ? (
                    <div className="flex items-center justify-center py-8" role="status" aria-label="Loading">
                        <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : state.policiesError ? (
                    <QueryErrorState
                        error={state.policiesError}
                        onRetry={onRetry}
                        isRetrying={state.policiesRetrying}
                        title="Couldn't load retention policies"
                        className="min-h-0 py-10"
                    />
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Record type</TableHead>
                                <TableHead>Retention</TableHead>
                                <TableHead>Active</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {RETENTION_OPTIONS.map((entity) => {
                                const edit = policyEdits[entity.value] ?? toPolicyEdit(undefined, undefined)
                                const error = policyErrors[entity.value]
                                const daysId = `retention-days-${entity.value}`
                                const errorId = error ? `${daysId}-error` : undefined
                                return (
                                    <TableRow key={entity.value}>
                                        <TableCell className="font-medium">{entity.label}</TableCell>
                                        <TableCell>
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Select
                                                    value={edit.mode}
                                                    onValueChange={(value) => {
                                                        if (value === "forever" || value === "purge") {
                                                            onPolicyEditChange(entity.value, { mode: value })
                                                        }
                                                    }}
                                                    disabled={state.saving}
                                                >
                                                    <SelectTrigger
                                                        className="w-36"
                                                        aria-label={`${entity.label} retention`}
                                                    >
                                                        <SelectValue>{getRetentionModeLabel}</SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {Object.entries(RETENTION_MODE_LABELS).map(([value, label]) => (
                                                            <SelectItem key={value} value={value}>
                                                                {label}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                                {edit.mode === "purge" ? (
                                                    <div className="flex items-center gap-2">
                                                        <Input
                                                            id={daysId}
                                                            type="number"
                                                            inputMode="numeric"
                                                            min={1}
                                                            step={1}
                                                            value={edit.days}
                                                            onChange={(e) =>
                                                                onPolicyEditChange(entity.value, { days: e.target.value })
                                                            }
                                                            disabled={state.saving}
                                                            className="w-24"
                                                            name={`retention-${entity.value}`}
                                                            autoComplete="off"
                                                            aria-label={`${entity.label} retention days`}
                                                            aria-invalid={error ? true : undefined}
                                                            aria-describedby={errorId}
                                                        />
                                                        <span className="text-sm text-muted-foreground">days</span>
                                                    </div>
                                                ) : null}
                                            </div>
                                            {error ? (
                                                <p id={errorId} className="mt-1 text-sm text-destructive">
                                                    {error}
                                                </p>
                                            ) : null}
                                        </TableCell>
                                        <TableCell>
                                            <Switch
                                                checked={edit.is_active}
                                                onCheckedChange={(checked) =>
                                                    onPolicyEditChange(entity.value, { is_active: checked })
                                                }
                                                disabled={state.saving}
                                                aria-label={`${entity.label} retention active`}
                                            />
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                            <TableRow>
                                <TableCell className="font-medium">Audit Logs</TableCell>
                                <TableCell className="text-muted-foreground">Archive only</TableCell>
                                <TableCell>
                                    <Badge variant="secondary">Always On</Badge>
                                </TableCell>
                            </TableRow>
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function LegalHoldForm({
    form,
    formState,
    onHoldTypeChange,
    onHoldEntityIdChange,
    onHoldReasonChange,
    onCreateHold,
}: Pick<
    LegalHoldsCardProps,
    | "form"
    | "formState"
    | "onHoldTypeChange"
    | "onHoldEntityIdChange"
    | "onHoldReasonChange"
    | "onCreateHold"
>) {
    return (
        <>
            <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                    <Label htmlFor="hold-scope">Hold Scope</Label>
                    <Select value={form.holdType} onValueChange={(value) => onHoldTypeChange(value || "org")}>
                        <SelectTrigger id="hold-scope">
                            <SelectValue>
                                {(value: string | null) => getLegalHoldTypeLabel(value)}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {LEGAL_HOLD_TYPES.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <LegalHoldEntityField
                    key={form.holdType}
                    holdType={form.holdType}
                    entityId={form.holdEntityId}
                    onEntityIdChange={onHoldEntityIdChange}
                />

                <div className="space-y-2">
                    <Label htmlFor="hold-reason">Reason</Label>
                    <Input
                        id="hold-reason"
                        placeholder="Reason for hold"
                        value={form.holdReason}
                        onChange={(e) => onHoldReasonChange(e.target.value)}
                        name="hold-reason"
                        autoComplete="off"
                    />
                </div>
            </div>
            <Button
                onClick={onCreateHold}
                disabled={
                    !form.holdReason.trim() ||
                    formState.createHoldPending ||
                    getHoldEntityIdError(form.holdType, form.holdEntityId) !== undefined
                }
            >
                <ShieldCheck className="size-4 mr-2" aria-hidden="true" />
                Create Hold
            </Button>
        </>
    )
}

function getHoldEntityIdError(holdType: string, entityId: string): string | undefined {
    const trimmed = entityId.trim()
    if (holdType === "org" || SEARCHABLE_HOLD_TYPES.has(holdType) || !trimmed) return undefined
    return UUID_PATTERN.test(trimmed) ? undefined : "Enter a record ID in UUID format."
}

/** Surrogates and donors are found by name or number; other scopes take an optional record ID. */
function LegalHoldEntityField({
    holdType,
    entityId,
    onEntityIdChange,
}: {
    holdType: string
    entityId: string
    onEntityIdChange: (value: string) => void
}) {
    const [search, setSearch] = useState("")
    const [selectedLabel, setSelectedLabel] = useState<string | null>(null)
    const searchable = SEARCHABLE_HOLD_TYPES.has(holdType)
    const trimmedSearch = search.trim()
    const searchQuery = useQuery({
        queryKey: ["compliance", "legal-hold-entity-search", holdType, trimmedSearch],
        queryFn: () => globalSearch({ q: trimmedSearch, types: holdType, limit: 8 }),
        enabled: searchable && !entityId && trimmedSearch.length >= 2,
        staleTime: 30_000,
    })
    const scopeLabel = getLegalHoldTypeLabel(holdType)

    if (holdType === "org") {
        return (
            <div className="space-y-2">
                <Label htmlFor="hold-entity-id">Record</Label>
                <Input id="hold-entity-id" value="All records" disabled name="hold-entity-id" />
            </div>
        )
    }

    if (!searchable) {
        const error = getHoldEntityIdError(holdType, entityId)
        return (
            <div className="space-y-2">
                <Label htmlFor="hold-entity-id">Record ID</Label>
                <Input
                    id="hold-entity-id"
                    placeholder={`All ${scopeLabel.toLowerCase()} records`}
                    value={entityId}
                    onChange={(e) => onEntityIdChange(e.target.value)}
                    name="hold-entity-id"
                    autoComplete="off"
                    spellCheck={false}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? "hold-entity-id-error" : undefined}
                />
                {error ? (
                    <p id="hold-entity-id-error" className="text-sm text-destructive">
                        {error}
                    </p>
                ) : null}
            </div>
        )
    }

    if (entityId) {
        return (
            <div className="space-y-2">
                <Label htmlFor="hold-entity-selected">Record</Label>
                <div className="flex items-center gap-2">
                    <Input
                        id="hold-entity-selected"
                        value={selectedLabel ?? entityId}
                        readOnly
                        name="hold-entity-selected"
                    />
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                            onEntityIdChange("")
                            setSelectedLabel(null)
                        }}
                    >
                        Change
                    </Button>
                </div>
            </div>
        )
    }

    const results = searchQuery.data?.results.filter((result) => result.entity_type === holdType) ?? []
    return (
        <div className="space-y-2">
            <Label htmlFor="hold-entity-search">Record</Label>
            <Input
                id="hold-entity-search"
                type="search"
                placeholder={`Search ${scopeLabel.toLowerCase()}s, or leave empty for all`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                name="hold-entity-search"
                autoComplete="off"
            />
            {trimmedSearch.length >= 2 ? (
                searchQuery.isFetching && !searchQuery.data ? (
                    <p className="text-sm text-muted-foreground" role="status">Searching…</p>
                ) : searchQuery.isError ? (
                    <p className="text-sm text-destructive">Couldn&apos;t search records. Try again.</p>
                ) : results.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No matching records</p>
                ) : (
                    <ul className="max-h-48 overflow-y-auto rounded-md border" aria-label="Matching records">
                        {results.map((result) => (
                            <li key={result.entity_id}>
                                <Button
                                    unstyled
                                    type="button"
                                    className="w-full px-3 py-2 text-left text-sm hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
                                    onClick={() => {
                                        onEntityIdChange(result.entity_id)
                                        setSelectedLabel(result.title)
                                        setSearch("")
                                    }}
                                >
                                    {result.title}
                                </Button>
                            </li>
                        ))}
                    </ul>
                )
            ) : null}
        </div>
    )
}

function LegalHoldsTable({
    legalHolds,
    listState,
    onReleaseHold,
}: Pick<LegalHoldsCardProps, "legalHolds" | "listState" | "onReleaseHold">) {
    if (listState.holdsLoading) {
        return (
            <div className="flex items-center justify-center py-8" role="status" aria-label="Loading">
                <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    if (listState.holdsError) {
        return (
            <QueryErrorState
                error={listState.holdsError}
                onRetry={listState.onRetry}
                isRetrying={listState.holdsRetrying}
                title="Couldn't load legal holds"
                className="min-h-0 py-10"
            />
        )
    }

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Scope</TableHead>
                    <TableHead>Entity ID</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {legalHolds?.items?.length ? (
                    legalHolds.items.map((hold) => (
                        <TableRow key={hold.id}>
                            <TableCell>{getLegalHoldTypeLabel(hold.entity_type ?? "org")}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                                {hold.entity_id ?? "—"}
                            </TableCell>
                            <TableCell className="max-w-xs truncate">{hold.reason}</TableCell>
                            <TableCell>
                                {hold.released_at ? (
                                    <Badge variant="outline">Released</Badge>
                                ) : (
                                    <Badge>Active</Badge>
                                )}
                            </TableCell>
                            <TableCell className="text-right">
                                {!hold.released_at && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => onReleaseHold(hold.id)}
                                        disabled={listState.releaseHoldPending}
                                    >
                                        Release
                                    </Button>
                                )}
                            </TableCell>
                        </TableRow>
                    ))
                ) : (
                    <TableRow>
                        <TableCell colSpan={5} className="text-center text-muted-foreground">
                            No legal holds in place.
                        </TableCell>
                    </TableRow>
                )}
            </TableBody>
        </Table>
    )
}

function LegalHoldsPagination({
    legalHolds,
    pagination,
    onHoldsPageChange,
}: Pick<LegalHoldsCardProps, "legalHolds" | "pagination" | "onHoldsPageChange">) {
    if (!legalHolds?.pages || legalHolds.pages <= 1) return null

    const { holdsPage, perPage } = pagination

    return (
        <div className="flex items-center justify-between border-t border-border px-6 py-4">
            <div className="text-sm text-muted-foreground">
                Showing {((holdsPage - 1) * perPage) + 1}-{Math.min(holdsPage * perPage, legalHolds.total)} of {legalHolds.total} legal holds
            </div>
            <div className="flex items-center gap-2 flex-wrap">
                <Button
                    variant="outline"
                    size="sm"
                    disabled={holdsPage === 1}
                    onClick={() => onHoldsPageChange(Math.max(1, holdsPage - 1))}
                >
                    Previous
                </Button>
                {[...Array(Math.min(5, legalHolds.pages))].map((_, i) => {
                    const pageNum = i + 1
                    return (
                        <Button
                            key={pageNum}
                            variant={holdsPage === pageNum ? "default" : "outline"}
                            size="sm"
                            onClick={() => onHoldsPageChange(pageNum)}
                        >
                            {pageNum}
                        </Button>
                    )
                })}
                {legalHolds.pages > 5 && <span className="text-muted-foreground">...</span>}
                <Button
                    variant="outline"
                    size="sm"
                    disabled={holdsPage >= legalHolds.pages}
                    onClick={() => onHoldsPageChange(Math.min(legalHolds.pages, holdsPage + 1))}
                >
                    Next
                </Button>
                <PaginationJump
                    page={holdsPage}
                    totalPages={legalHolds.pages}
                    onPageChange={onHoldsPageChange}
                />
            </div>
        </div>
    )
}

function LegalHoldsCard({
    form,
    legalHolds,
    listState,
    formState,
    pagination,
    onHoldTypeChange,
    onHoldEntityIdChange,
    onHoldReasonChange,
    onCreateHold,
    onReleaseHold,
    onHoldsPageChange,
}: LegalHoldsCardProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Legal Holds</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <LegalHoldForm
                    form={form}
                    formState={formState}
                    onHoldTypeChange={onHoldTypeChange}
                    onHoldEntityIdChange={onHoldEntityIdChange}
                    onHoldReasonChange={onHoldReasonChange}
                    onCreateHold={onCreateHold}
                />
                <LegalHoldsTable
                    legalHolds={legalHolds}
                    listState={listState}
                    onReleaseHold={onReleaseHold}
                />
                {!listState.holdsLoading && !listState.holdsError && (
                    <LegalHoldsPagination
                        legalHolds={legalHolds}
                        pagination={pagination}
                        onHoldsPageChange={onHoldsPageChange}
                    />
                )}
            </CardContent>
        </Card>
    )
}

function RetentionPurgeCard({
    purgeItems,
    purgeJobId,
    onPreviewPurge,
    onExecutePurge,
}: RetentionPurgeCardProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Retention Purge (Developer)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={onPreviewPurge}>
                        Preview Purge
                    </Button>
                    <ConfirmDialog
                        trigger={
                            <Button variant="destructive">
                                <Trash2 className="size-4 mr-2" aria-hidden="true" />
                                Execute Purge
                            </Button>
                        }
                        title="Purge records past their retention window?"
                        description="Matching records are permanently deleted. Records under a legal hold are kept. This cannot be undone."
                        confirmLabel="Execute purge"
                        onConfirm={onExecutePurge}
                    />
                </div>

                {purgeItems.length ? (
                    <div className="space-y-2">
                        {purgeItems.map((item) => (
                            <div key={item.entity_type} className="flex items-center justify-between border rounded-md px-3 py-2">
                                <span className="text-sm">{getRetentionEntityLabel(item.entity_type)}</span>
                                <Badge variant="outline">{item.count}</Badge>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">No purge preview data yet.</p>
                )}

                {purgeJobId && (
                    <p className="text-sm text-muted-foreground">
                        Purge job scheduled: <span className="font-mono">{purgeJobId}</span>
                    </p>
                )}
            </CardContent>
        </Card>
    )
}

export default function ComplianceSettingsPage() {
    return (
        <SettingsPageGate
            title="Compliance"
            permission="manage_compliance"
            deniedDescription="Compliance settings need the Manage compliance permission. Ask an admin to update your role."
        >
            <ComplianceSettingsContent />
        </SettingsPageGate>
    )
}

function ComplianceSettingsContent() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const policiesQuery = useRetentionPolicies()
    const policies = policiesQuery.data
    const upsertPolicy = useUpsertRetentionPolicy()

    const perPage = 20
    const [holdsPage, setHoldsPage] = useState(1)
    const holdsQuery = useLegalHolds({
        page: holdsPage,
        per_page: perPage,
    })
    const legalHolds = holdsQuery.data
    const availableHoldsPages = Math.max(1, legalHolds?.pages ?? 1)
    if (holdsPage > availableHoldsPages) {
        setHoldsPage(availableHoldsPages)
    }
    const createHold = useCreateLegalHold()
    const releaseHold = useReleaseLegalHold()

    const purgePreview = usePurgePreview()
    const executePurge = useExecutePurge()

    const [policyEditOverrides, setPolicyEditOverrides] = useState<PolicyEditOverrides>({})
    const [savingPolicies, setSavingPolicies] = useState(false)
    const contentRef = useRef<HTMLDivElement>(null)
    const [holdType, setHoldType] = useState("org")
    const [holdEntityId, setHoldEntityId] = useState("")
    const [holdReason, setHoldReason] = useState("")
    const [purgeJobId, setPurgeJobId] = useState<string | null>(null)

    const policyByEntityType = new Map(
        (policies ?? []).map((policy) => [policy.entity_type, policy] as const)
    )
    const policyEdits: PolicyEdits = {}
    const policyErrors: Record<string, string | undefined> = {}
    const changedEntityTypes: string[] = []
    for (const entity of RETENTION_OPTIONS) {
        const policy = policyByEntityType.get(entity.value)
        const saved = toPolicyEdit(policy?.retention_days, policy?.is_active)
        const edit = { ...saved, ...policyEditOverrides[entity.value] }
        policyEdits[entity.value] = edit
        policyErrors[entity.value] = getPolicyEditError(edit)
        if (!isSamePolicyEdit(saved, edit)) changedEntityTypes.push(entity.value)
    }
    const policyErrorCount = Object.values(policyErrors).filter(Boolean).length
    // Rows only become editable after policies load, so no default row is ever saved over a failed load.
    const policiesReady = policies !== undefined && !policiesQuery.isError

    const updatePolicyEdit = (entityType: string, patch: Partial<PolicyEdit>) => {
        setPolicyEditOverrides((prev) => ({ ...prev, [entityType]: { ...prev[entityType], ...patch } }))
    }

    const handleSavePolicies = async () => {
        if (!policiesReady || policyErrorCount > 0 || changedEntityTypes.length === 0) return
        setSavingPolicies(true)
        const savedTypes: string[] = []
        let failure: unknown = null
        // One request per record type (the API upserts a single policy); stop at the first failure.
        for (const entityType of changedEntityTypes) {
            const edit = policyEdits[entityType]
            if (!edit) continue
            try {
                await upsertPolicy.mutateAsync({
                    entity_type: entityType,
                    retention_days: edit.mode === "forever" ? 0 : Number(edit.days.trim()),
                    is_active: edit.is_active,
                })
                savedTypes.push(entityType)
            } catch (error) {
                failure = error
                break
            }
        }
        setPolicyEditOverrides((prev) => {
            const next = { ...prev }
            for (const entityType of savedTypes) delete next[entityType]
            return next
        })
        setSavingPolicies(false)
        if (failure) {
            const message = getComplianceActionError(failure, "Couldn't save retention policy.")
            if (message) toast.error(message)
            return
        }
        toast.success(savedTypes.length === 1 ? "Retention policy saved" : "Retention policies saved")
    }

    const handleCreateHold = async () => {
        try {
            await createHold.mutateAsync({
                entity_type: holdType === "org" ? null : holdType,
                entity_id: holdType === "org" ? null : holdEntityId.trim() || null,
                reason: holdReason.trim(),
            })
            setHoldReason("")
            setHoldEntityId("")
            setHoldsPage(1)
            toast.success("Legal hold created")
        } catch (error) {
            const message = getComplianceActionError(error, "Couldn't create the legal hold.")
            if (message) toast.error(message)
        }
    }

    const handleReleaseHold = async (holdId: string) => {
        try {
            await releaseHold.mutateAsync(holdId)
            toast.success("Legal hold released")
        } catch (error) {
            const message = getComplianceActionError(error, "Couldn't release the legal hold.")
            if (message) toast.error(message)
        }
    }

    const handlePreviewPurge = async () => {
        await purgePreview.refetch()
    }

    // Errors are toasted here (sanitized), so the confirm dialog closes either way.
    const handleExecutePurge = async () => {
        try {
            const response = await executePurge.mutateAsync()
            setPurgeJobId(response.job_id)
            toast.success("Purge job scheduled")
        } catch (error) {
            const message = getComplianceActionError(error, "Couldn't start the purge.")
            if (message) toast.error(message)
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader title="Compliance" />

            <div ref={contentRef} className="flex-1 p-6 space-y-6">
                <RetentionPoliciesCard
                    policyEdits={policyEdits}
                    policyErrors={policyErrors}
                    state={{
                        policiesLoading: policiesQuery.isLoading,
                        policiesError: policiesQuery.isError ? policiesQuery.error : null,
                        policiesRetrying: policiesQuery.isFetching,
                        saving: savingPolicies,
                    }}
                    onPolicyEditChange={updatePolicyEdit}
                    onRetry={() => void policiesQuery.refetch()}
                />

                <LegalHoldsCard
                    form={{ holdType, holdEntityId, holdReason }}
                    legalHolds={legalHolds}
                    listState={{
                        holdsLoading: holdsQuery.isLoading,
                        holdsError: holdsQuery.isError ? holdsQuery.error : null,
                        holdsRetrying: holdsQuery.isFetching,
                        onRetry: () => void holdsQuery.refetch(),
                        releaseHoldPending: releaseHold.isPending,
                    }}
                    formState={{ createHoldPending: createHold.isPending }}
                    pagination={{ holdsPage, perPage }}
                    onHoldTypeChange={(value) => {
                        setHoldType(value)
                        setHoldEntityId("")
                    }}
                    onHoldEntityIdChange={setHoldEntityId}
                    onHoldReasonChange={setHoldReason}
                    onCreateHold={handleCreateHold}
                    onReleaseHold={handleReleaseHold}
                    onHoldsPageChange={setHoldsPage}
                />

                {isDeveloper && (
                    <RetentionPurgeCard
                        purgeItems={purgePreview.data?.items ?? []}
                        purgeJobId={purgeJobId}
                        onPreviewPurge={handlePreviewPurge}
                        onExecutePurge={handleExecutePurge}
                    />
                )}
            </div>

            {policiesReady ? (
                <SaveBar
                    dirty={changedEntityTypes.length > 0}
                    changeCount={changedEntityTypes.length}
                    errorCount={policyErrorCount}
                    onErrorsClick={() => focusFirstInvalid(contentRef.current)}
                    saving={savingPolicies}
                    onSave={() => void handleSavePolicies()}
                    onDiscard={() => setPolicyEditOverrides({})}
                />
            ) : null}
        </div>
    )
}
