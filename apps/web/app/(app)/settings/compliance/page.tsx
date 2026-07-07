"use client"

import { startTransition, useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
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

const RETENTION_OPTIONS = [
    { value: "surrogates", label: "Surrogates (archived only)" },
    { value: "matches", label: "Matches" },
    { value: "tasks", label: "Tasks (completed only)" },
    { value: "entity_notes", label: "Notes" },
    { value: "surrogate_activity", label: "Surrogate Activity" },
]

const LEGAL_HOLD_TYPES = [
    { value: "org", label: "Organization (all records)" },
    { value: "surrogate", label: "Surrogate" },
    { value: "match", label: "Match" },
    { value: "task", label: "Task" },
    { value: "entity_notes", label: "Note" },
    { value: "surrogate_activity", label: "Surrogate Activity" },
]

type PolicyEdit = {
    retention_days: number
    is_active: boolean
}

type PolicyEdits = Record<string, PolicyEdit>
type PolicyEditField = keyof PolicyEdit

type RetentionPoliciesCardProps = {
    policyEdits: PolicyEdits
    state: {
        policiesLoading: boolean
        upsertPending: boolean
    }
    onPolicyEditChange: (
        entityType: string,
        field: PolicyEditField,
        value: number | boolean
    ) => void
    onSavePolicy: (entityType: string) => Promise<void>
}

type LegalHoldFormState = {
    holdType: string
    holdEntityId: string
    holdReason: string
}

type LegalHoldsCardProps = {
    form: LegalHoldFormState
    legalHolds: LegalHoldListResponse | undefined
    listState: {
        holdsLoading: boolean
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

function CompliancePageHeader() {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center px-6">
                <h1 className="text-2xl font-semibold">Compliance & HIPAA</h1>
            </div>
        </div>
    )
}

function RetentionPoliciesCard({
    policyEdits,
    state,
    onPolicyEditChange,
    onSavePolicy,
}: RetentionPoliciesCardProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Data Retention Policies</CardTitle>
                <CardDescription>Configure automatic purge windows per entity type.</CardDescription>
            </CardHeader>
            <CardContent>
                {state.policiesLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Entity</TableHead>
                                <TableHead>Retention (days)</TableHead>
                                <TableHead>Active</TableHead>
                                <TableHead className="text-right">Action</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {RETENTION_OPTIONS.map((entity) => {
                                const edit = policyEdits[entity.value] || {
                                    retention_days: 0,
                                    is_active: true,
                                }
                                return (
                                    <TableRow key={entity.value}>
                                        <TableCell className="font-medium">{entity.label}</TableCell>
                                        <TableCell>
                                            <Input
                                                type="number"
                                                min={0}
                                                value={edit.retention_days}
                                                onChange={(e) => onPolicyEditChange(
                                                    entity.value,
                                                    "retention_days",
                                                    Number(e.target.value)
                                                )}
                                                className="w-32"
                                                name={`retention-${entity.value}`}
                                                autoComplete="off"
                                                aria-label={`${entity.label} retention days`}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Switch
                                                checked={edit.is_active}
                                                onCheckedChange={(checked) => onPolicyEditChange(
                                                    entity.value,
                                                    "is_active",
                                                    checked
                                                )}
                                                aria-label={`${entity.label} retention active`}
                                            />
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                size="sm"
                                                onClick={() => onSavePolicy(entity.value)}
                                                disabled={state.upsertPending}
                                            >
                                                Save
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                            <TableRow>
                                <TableCell className="font-medium">Audit Logs</TableCell>
                                <TableCell>
                                    <Input type="text" value="Archive only" disabled className="w-32" />
                                </TableCell>
                                <TableCell>
                                    <Badge variant="secondary">Always On</Badge>
                                </TableCell>
                                <TableCell className="text-right">
                                    <Badge variant="outline">Not Purgeable</Badge>
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
                <div className="space-y-2">
                    <Label htmlFor="hold-entity-id">Entity ID</Label>
                    <Input
                        id="hold-entity-id"
                        placeholder="Optional entity UUID"
                        value={form.holdEntityId}
                        disabled={form.holdType === "org"}
                        onChange={(e) => onHoldEntityIdChange(e.target.value)}
                        name="hold-entity-id"
                        autoComplete="off"
                    />
                </div>
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
            <Button onClick={onCreateHold} disabled={!form.holdReason || formState.createHoldPending}>
                <ShieldCheck className="size-4 mr-2" aria-hidden="true" />
                Create Hold
            </Button>
        </>
    )
}

function LegalHoldsTable({
    legalHolds,
    listState,
    onReleaseHold,
}: Pick<LegalHoldsCardProps, "legalHolds" | "listState" | "onReleaseHold">) {
    if (listState.holdsLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
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
                            <TableCell>{hold.entity_type ?? "org"}</TableCell>
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
                <CardDescription>Block purges for sensitive matters or investigations.</CardDescription>
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
                {!listState.holdsLoading && (
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
                <CardDescription>Preview and execute purge jobs.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={onPreviewPurge}>
                        Preview Purge
                    </Button>
                    <Button variant="destructive" onClick={onExecutePurge}>
                        <Trash2 className="size-4 mr-2" aria-hidden="true" />
                        Execute Purge
                    </Button>
                </div>

                {purgeItems.length ? (
                    <div className="space-y-2">
                        {purgeItems.map((item) => (
                            <div key={item.entity_type} className="flex items-center justify-between border rounded-md px-3 py-2">
                                <span className="text-sm">{item.entity_type}</span>
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
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const { data: policies, isLoading: policiesLoading } = useRetentionPolicies()
    const upsertPolicy = useUpsertRetentionPolicy()

    const perPage = 20
    const [holdsPage, setHoldsPage] = useState(1)
    const { data: legalHolds, isLoading: holdsLoading } = useLegalHolds({
        page: holdsPage,
        per_page: perPage,
    })
    const createHold = useCreateLegalHold()
    const releaseHold = useReleaseLegalHold()

    const purgePreview = usePurgePreview()
    const executePurge = useExecutePurge()

    const [policyEdits, setPolicyEdits] = useState<PolicyEdits>({})
    const [holdType, setHoldType] = useState("org")
    const [holdEntityId, setHoldEntityId] = useState("")
    const [holdReason, setHoldReason] = useState("")
    const [purgeJobId, setPurgeJobId] = useState<string | null>(null)

    useEffect(() => {
        if (!policies) return
        const policyMap: Record<string, { retention_days: number; is_active: boolean }> = {}
        policies.forEach((policy) => {
            policyMap[policy.entity_type] = {
                retention_days: policy.retention_days,
                is_active: policy.is_active,
            }
        })
        startTransition(() => {
            setPolicyEdits((prev) => (Object.keys(prev).length ? prev : { ...policyMap }))
        })
    }, [policies])

    useEffect(() => {
        if (!legalHolds?.pages) return
        if (holdsPage > legalHolds.pages) {
            startTransition(() => {
                setHoldsPage(legalHolds.pages)
            })
        }
    }, [holdsPage, legalHolds?.pages])

    const updatePolicyEdit = (entityType: string, field: "retention_days" | "is_active", value: number | boolean) => {
        setPolicyEdits((prev) => ({
            ...prev,
            [entityType]: {
                retention_days: prev[entityType]?.retention_days ?? 0,
                is_active: prev[entityType]?.is_active ?? true,
                [field]: value,
            },
        }))
    }

    const handleSavePolicy = async (entityType: string) => {
        const edit = policyEdits[entityType]
        if (!edit) return
        await upsertPolicy.mutateAsync({
            entity_type: entityType,
            retention_days: edit.retention_days,
            is_active: edit.is_active,
        })
    }

    const handleCreateHold = async () => {
        await createHold.mutateAsync({
            entity_type: holdType === "org" ? null : holdType,
            entity_id: holdType === "org" ? null : holdEntityId || null,
            reason: holdReason,
        })
        setHoldReason("")
        setHoldEntityId("")
        setHoldsPage(1)
    }

    const handlePreviewPurge = async () => {
        await purgePreview.refetch()
    }

    const handleExecutePurge = async () => {
        const response = await executePurge.mutateAsync()
        setPurgeJobId(response.job_id)
    }

    return (
        <div className="flex min-h-screen flex-col">
            <CompliancePageHeader />

            <div className="flex-1 p-6 space-y-6">
                <RetentionPoliciesCard
                    policyEdits={policyEdits}
                    state={{ policiesLoading, upsertPending: upsertPolicy.isPending }}
                    onPolicyEditChange={updatePolicyEdit}
                    onSavePolicy={handleSavePolicy}
                />

                <LegalHoldsCard
                    form={{ holdType, holdEntityId, holdReason }}
                    legalHolds={legalHolds}
                    listState={{
                        holdsLoading,
                        releaseHoldPending: releaseHold.isPending,
                    }}
                    formState={{ createHoldPending: createHold.isPending }}
                    pagination={{ holdsPage, perPage }}
                    onHoldTypeChange={setHoldType}
                    onHoldEntityIdChange={setHoldEntityId}
                    onHoldReasonChange={setHoldReason}
                    onCreateHold={handleCreateHold}
                    onReleaseHold={releaseHold.mutateAsync}
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
        </div>
    )
}
