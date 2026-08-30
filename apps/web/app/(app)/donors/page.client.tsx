"use client"

import { useState } from "react"
import type { Route } from "next"
import { useRouter, useSearchParams } from "next/navigation"
import { AlertCircleIcon, Loader2Icon, PlusIcon, SearchIcon, UsersIcon, XIcon } from "lucide-react"

import Link from "@/components/app-link"
import { DonorFormFields } from "@/components/donors/DonorFormFields"
import {
    EMPTY_DONOR_FORM_VALUES,
    type DonorFormValues,
} from "@/components/donors/donor-form-values"
import { PermissionDeniedState } from "@/components/error-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { PaginationJump } from "@/components/ui/pagination-jump"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"
import type { DonorSortBy } from "@/lib/api/donors"
import type { PipelineStage } from "@/lib/api/pipelines"
import { getActiveDonorStages, getDonorStageLabel, getDonorStageStyle } from "@/lib/donor-stage-utils"
import { isPermissionError } from "@/lib/error-utils"
import { useDebouncedSearchCommit } from "@/lib/hooks/use-debounced-search-commit"
import { useCreateDonor, useDonors } from "@/lib/hooks/use-donors"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { formatDate } from "@/lib/formatters"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { toast } from "@/components/ui/toast"
import {
    getDonorPipelineEntityType,
    getDonorTypeLabel,
    getDonorTypePluralLabel,
    type DonorListResponse,
    type DonorType,
} from "@/lib/types/donor"

const DONOR_SORT_FIELDS: DonorSortBy[] = [
    "donor_number",
    "full_name",
    "state",
    "education",
    "stage",
    "created_at",
]
const DATE_RANGE_PRESETS: DateRangePreset[] = ["all", "today", "week", "month", "custom"]
const DATE_RANGE_LABELS: Record<Exclude<DateRangePreset, "custom">, string> = {
    all: "All Time",
    today: "Today",
    week: "This Week",
    month: "This Month",
}
const filterDateFormatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
})

function parseDonorType(value: string | null): DonorType {
    return value === "sperm" ? "sperm" : "egg"
}

function parsePage(value: string | null): number {
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
}

function parseDonorSortBy(value: string | null): DonorSortBy | null {
    return DONOR_SORT_FIELDS.includes(value as DonorSortBy) ? value as DonorSortBy : null
}

function parseSortOrder(value: string | null): "asc" | "desc" {
    return value === "asc" ? "asc" : "desc"
}

function parseDateRange(value: string | null): DateRangePreset {
    return DATE_RANGE_PRESETS.includes(value as DateRangePreset)
        ? value as DateRangePreset
        : "all"
}

function parseDate(value: string | null): Date | undefined {
    if (!value) return undefined
    const parsed = parseDateInput(value)
    return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

function getCreatedDateParams(
    range: DateRangePreset,
    customRange: { from: Date | undefined; to: Date | undefined },
) {
    if (range === "all") return {}
    if (customRange.from || customRange.to) {
        return {
            ...(customRange.from ? { created_from: formatLocalDate(customRange.from) } : {}),
            ...(customRange.to ? { created_to: formatLocalDate(customRange.to) } : {}),
        }
    }
    if (range === "custom") return {}

    const now = new Date()
    let from: Date
    if (range === "today") {
        from = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    } else if (range === "week") {
        from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    } else {
        from = new Date(now.getFullYear(), now.getMonth(), 1)
    }
    return {
        created_from: formatLocalDate(from),
        created_to: formatLocalDate(now),
    }
}

function getDateRangeLabel(
    range: DateRangePreset,
    customRange: { from: Date | undefined; to: Date | undefined },
): string {
    if (range !== "custom") return DATE_RANGE_LABELS[range]
    if (customRange.from && customRange.to) {
        return `${filterDateFormatter.format(customRange.from)} - ${filterDateFormatter.format(customRange.to)}`
    }
    if (customRange.from) return `From ${filterDateFormatter.format(customRange.from)}`
    if (customRange.to) return `Until ${filterDateFormatter.format(customRange.to)}`
    return "Custom Range"
}

function formatCreatedAt(value: string): string {
    return formatDate(value, {
        month: "short",
        day: "numeric",
        year: "numeric",
    }, "—")
}

function buildDonorsHref(
    current: string,
    update: {
        type?: DonorType
        stage?: string
        q?: string
        archived?: boolean
        page?: number
        new?: boolean
        dynamicFilter?: "attention_stuck" | null
        ownerId?: string | null
        range?: DateRangePreset
        rangeDates?: { from: Date | undefined; to: Date | undefined }
        sortBy?: DonorSortBy | null
        sortOrder?: "asc" | "desc"
    },
): Route {
    const params = new URLSearchParams(current)
    if (update.type) {
        params.set("type", update.type)
        params.delete("stage")
        params.delete("page")
    }
    if (update.stage !== undefined) {
        if (update.stage === "all") params.delete("stage")
        else params.set("stage", update.stage)
    }
    if (update.q !== undefined) {
        if (update.q) params.set("q", update.q)
        else params.delete("q")
    }
    if (update.archived !== undefined) {
        if (update.archived) params.set("archive", "archived")
        else params.delete("archive")
    }
    if (update.page !== undefined) {
        if (update.page > 1) params.set("page", String(update.page))
        else params.delete("page")
    }
    if (update.new !== undefined) {
        if (update.new) params.set("new", "true")
        else params.delete("new")
    }
    if (update.dynamicFilter !== undefined) {
        if (update.dynamicFilter) params.set("dynamic_filter", update.dynamicFilter)
        else params.delete("dynamic_filter")
    }
    if (update.ownerId !== undefined) {
        if (update.ownerId) params.set("owner_id", update.ownerId)
        else params.delete("owner_id")
    }
    if (update.range !== undefined) {
        if (update.range === "all") {
            params.delete("range")
            params.delete("from")
            params.delete("to")
        } else {
            params.set("range", update.range)
            if (update.range === "custom") {
                if (update.rangeDates?.from) params.set("from", formatLocalDate(update.rangeDates.from))
                else params.delete("from")
                if (update.rangeDates?.to) params.set("to", formatLocalDate(update.rangeDates.to))
                else params.delete("to")
            } else {
                params.delete("from")
                params.delete("to")
            }
        }
    }
    if (update.sortBy !== undefined) {
        if (update.sortBy) {
            params.set("sort_by", update.sortBy)
            params.set("sort_order", update.sortOrder ?? "desc")
        } else {
            params.delete("sort_by")
            params.delete("sort_order")
        }
    }
    if (params.get("type") === "egg") params.delete("type")
    const query = params.toString()
    return (query ? `/donors?${query}` : "/donors") as Route
}

function DonorListCard({
    view,
    onRetry,
    onClearFilters,
    onSort,
}: {
    view: {
        donorType: DonorType
        stages: PipelineStage[]
        data: DonorListResponse | undefined
        isLoading: boolean
        isError: boolean
        error: unknown
        isFiltered: boolean
        currentListHref: string
        sortBy: DonorSortBy | null
        sortOrder: "asc" | "desc"
    }
    onRetry: () => void
    onClearFilters: () => void
    onSort: (column: string) => void
}) {
    const {
        donorType,
        stages,
        data,
        isLoading,
        isError,
        error,
        isFiltered,
        currentListHref,
        sortBy,
        sortOrder,
    } = view
    return (
        <Card className="py-0">
            <CardContent className="overflow-x-auto p-0">
                {isLoading ? (
                    <div className="flex items-center justify-center py-12" role="status">
                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading…</span>
                    </div>
                ) : isPermissionError(error) ? (
                    <PermissionDeniedState
                        description="Your account does not have permission to view donors. Ask an admin to update your role or permissions."
                        onRetry={onRetry}
                    />
                ) : isError ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <AlertCircleIcon className="mb-4 size-12 text-destructive" />
                        <h2 className="text-lg font-medium">Failed to load donors</h2>
                        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
                            Retry
                        </Button>
                    </div>
                ) : !data?.items.length ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <UsersIcon className="mb-4 size-12 text-muted-foreground" />
                        <h2 className="text-lg font-medium">
                            {isFiltered
                                ? "No donors match these filters"
                                : `No ${getDonorTypePluralLabel(donorType).toLowerCase()} yet`}
                        </h2>
                        {isFiltered ? (
                            <Button variant="outline" size="sm" className="mt-4" onClick={onClearFilters}>
                                Clear filters
                            </Button>
                        ) : null}
                    </div>
                ) : (
                    <Table
                        aria-label={getDonorTypePluralLabel(donorType)}
                        className="[&_td]:!text-center [&_th]:!text-center"
                    >
                        <TableHeader>
                            <TableRow>
                                <SortableTableHead column="donor_number" label="Donor #" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <TableHead>Email</TableHead>
                                <TableHead>Phone</TableHead>
                                <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="education" label="Education" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="stage" label="Stage" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.items.map((donor) => (
                                <TableRow key={donor.id}>
                                    <TableCell>
                                        <Link
                                            href={`/donors/${donor.id}?${new URLSearchParams({ return_to: currentListHref }).toString()}`}
                                            className="font-medium text-primary hover:underline"
                                        >
                                            {donor.donor_number}
                                        </Link>
                                    </TableCell>
                                    <TableCell className="font-medium">{donor.full_name}</TableCell>
                                    <TableCell className="text-muted-foreground">{donor.email}</TableCell>
                                    <TableCell className="text-muted-foreground">{donor.phone || "—"}</TableCell>
                                    <TableCell className="text-muted-foreground">{donor.state || "—"}</TableCell>
                                    <TableCell className="text-muted-foreground">{donor.education || "—"}</TableCell>
                                    <TableCell>
                                        <div className="flex flex-wrap justify-center gap-1">
                                            <Badge variant="outline" style={getDonorStageStyle(stages, donor)}>
                                                {getDonorStageLabel(stages, donor)}
                                            </Badge>
                                            {donor.is_archived ? <Badge variant="secondary">Archived</Badge> : null}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">{formatCreatedAt(donor.created_at)}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function CreateDonorDialog({
    donorType,
    formValues,
    open,
    pending,
    onOpenChange,
    onClose,
    onSubmit,
    onFieldChange,
}: {
    donorType: DonorType
    formValues: DonorFormValues
    open: boolean
    pending: boolean
    onOpenChange: (open: boolean) => void
    onClose: () => void
    onSubmit: () => Promise<void>
    onFieldChange: (field: keyof DonorFormValues, value: string) => void
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <form action={onSubmit}>
                    <DialogHeader>
                        <DialogTitle>New {getDonorTypeLabel(donorType)}</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <DonorFormFields
                            values={formValues}
                            idPrefix="create_donor_"
                            showDonorType={false}
                            onChange={onFieldChange}
                        />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                        <Button
                            type="submit"
                            disabled={pending || !formValues.full_name.trim() || !formValues.email.trim()}
                        >
                            {pending ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                            Create
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}

function DonorFiltersPanel({
    view,
    onArchivedChange,
    onDatePresetChange,
    onCustomDateChange,
    onStageChange,
    onSearchChange,
    onClearAll,
}: {
    view: {
        showArchived: boolean
        dateRange: DateRangePreset
        customRange: { from: Date | undefined; to: Date | undefined }
        stageFilter: string
        stages: PipelineStage[]
        search: string
        isFiltered: boolean
        chips: Array<{ key: string; label: string; clear: () => void }>
    }
    onArchivedChange: (archived: boolean) => void
    onDatePresetChange: (range: DateRangePreset) => void
    onCustomDateChange: (range: { from: Date | undefined; to: Date | undefined }) => void
    onStageChange: (stage: string) => void
    onSearchChange: (value: string) => void
    onClearAll: () => void
}) {
    const { showArchived, dateRange, customRange, stageFilter, stages, search, isFiltered, chips } = view
    return (
        <>
            <div className="flex flex-col gap-4 md:flex-row md:items-center">
                <Select
                    value={showArchived ? "archived" : "active"}
                    onValueChange={(value) => onArchivedChange(value === "archived")}
                >
                    <SelectTrigger aria-label="Record status" className="w-full md:w-[180px]">
                        <SelectValue>
                            {(value: string | null) => value === "archived" ? "Archived Donors" : "Active Donors"}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="active">Active Donors</SelectItem>
                        <SelectItem value="archived">Archived Donors</SelectItem>
                    </SelectContent>
                </Select>
                <DateRangePicker
                    preset={dateRange}
                    customRange={customRange}
                    ariaLabel="Created date range"
                    onPresetChange={onDatePresetChange}
                    onCustomRangeChange={onCustomDateChange}
                    className="w-full md:w-auto"
                />
                <Select value={stageFilter} onValueChange={(value) => value && onStageChange(value)}>
                    <SelectTrigger aria-label="Stage" className="w-full md:w-[180px]">
                        <SelectValue placeholder="All Stages">
                            {(value: string | null) =>
                                value === "all" || !value
                                    ? "All Stages"
                                    : stages.find((stage) => stage.id === value)?.label ?? "Stage unavailable"}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Stages</SelectItem>
                        {stages.map((stage) => (
                            <SelectItem key={stage.id} value={stage.id}>{stage.label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <div className="flex-1" />
                <div className="relative w-full max-w-sm">
                    <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        type="search"
                        aria-label="Search donors"
                        placeholder="Search name, number, email, phone…"
                        className="pl-9"
                        value={search}
                        onChange={(event) => onSearchChange(event.target.value)}
                    />
                </div>
            </div>

            {isFiltered ? (
                <div className="flex flex-wrap items-center gap-2">
                    {chips.map((chip) => (
                        <Button
                            key={chip.key}
                            variant="outline"
                            size="sm"
                            className="gap-2"
                            aria-label={`Remove filter: ${chip.label}`}
                            onClick={chip.clear}
                        >
                            {chip.label}
                            <XIcon className="size-3" aria-hidden="true" />
                        </Button>
                    ))}
                    <Button variant="ghost" size="sm" onClick={onClearAll} aria-label="Reset filters">
                        Reset
                    </Button>
                </div>
            ) : null}
        </>
    )
}

export default function DonorsPageClient() {
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const canEditDonors = user?.role === "developer" ||
        permissionsQuery.data?.permissions.includes("edit_donors") === true
    const searchParams = useSearchParams()
    const { replace } = useRouter()
    const query = searchParams.toString()
    const donorType = parseDonorType(searchParams.get("type"))
    const committedSearch = searchParams.get("q") ?? ""
    const stageFilter = searchParams.get("stage") ?? "all"
    const showArchived = searchParams.get("archive") === "archived"
    const dynamicFilter = searchParams.get("dynamic_filter") === "attention_stuck"
        ? "attention_stuck"
        : null
    const ownerId = searchParams.get("owner_id")
    const dateRange = parseDateRange(searchParams.get("range"))
    const customRange = {
        from: parseDate(searchParams.get("from")),
        to: parseDate(searchParams.get("to")),
    }
    const sortBy = parseDonorSortBy(searchParams.get("sort_by"))
    const sortOrder = parseSortOrder(searchParams.get("sort_order"))
    const page = parsePage(searchParams.get("page"))
    const [searchDraft, setSearchDraft] = useState<{ query: string; value: string } | null>(null)
    const [isCreateOpen, setIsCreateOpen] = useState(searchParams.get("new") === "true")
    const [formValues, setFormValues] = useState<DonorFormValues>({
        ...EMPTY_DONOR_FORM_VALUES,
        donor_type: donorType,
    })
    const search = searchDraft?.query === query ? searchDraft.value : committedSearch
    const { cancel, schedule } = useDebouncedSearchCommit(query)

    const pipelineEntityType = getDonorPipelineEntityType(donorType)
    const pipelineQuery = useDefaultPipeline(pipelineEntityType)
    const stages = getActiveDonorStages(pipelineQuery.data?.stages)
    const donorsQuery = useDonors({
        donor_type: donorType,
        page,
        per_page: 20,
        ...(stageFilter !== "all" ? { stage_id: stageFilter } : {}),
        ...(committedSearch ? { q: committedSearch } : {}),
        ...(showArchived ? { include_archived: true, archived_only: true } : {}),
        ...(dynamicFilter ? { dynamic_filter: dynamicFilter } : {}),
        ...(ownerId ? { owner_id: ownerId } : {}),
        ...getCreatedDateParams(dateRange, customRange),
        ...(sortBy ? { sort_by: sortBy, sort_order: sortOrder } : {}),
    })
    const createDonor = useCreateDonor()
    const data = donorsQuery.data
    const totalPages = data?.pages ?? 1
    const isFiltered = Boolean(
        committedSearch || stageFilter !== "all" || showArchived || dynamicFilter || ownerId ||
        dateRange !== "all",
    )
    const currentListHref = buildDonorsHref(query, { new: false })

    const setUrl = (update: Parameters<typeof buildDonorsHref>[1]) => {
        const href = buildDonorsHref(query, update)
        replace(href, { scroll: false })
    }

    const handleSearchChange = (value: string) => {
        setSearchDraft({ query, value })
        cancel()
        const scheduledQuery = query
        schedule(() => {
            if (searchParams.toString() !== scheduledQuery) return
            replace(buildDonorsHref(scheduledQuery, { q: value, page: 1 }), { scroll: false })
        }, 300)
    }

    const handleSort = (column: string) => {
        const nextSortBy = parseDonorSortBy(column)
        if (!nextSortBy) return
        const nextSortOrder = sortBy === nextSortBy && sortOrder === "asc" ? "desc" :
            sortBy === nextSortBy ? "asc" : "desc"
        setUrl({ sortBy: nextSortBy, sortOrder: nextSortOrder, page: 1 })
    }

    const clearAllFilters = () => {
        setSearchDraft({ query, value: "" })
        cancel()
        setUrl({
            stage: "all",
            q: "",
            archived: false,
            dynamicFilter: null,
            ownerId: null,
            range: "all",
            page: 1,
        })
    }

    const resetCreateForm = () => {
        setFormValues({ ...EMPTY_DONOR_FORM_VALUES, donor_type: donorType })
    }

    const closeCreateDialog = () => {
        setIsCreateOpen(false)
        setUrl({ new: false })
        resetCreateForm()
    }

    const handleCreate = async () => {
        try {
            await createDonor.mutateAsync({
                donor_type: donorType,
                full_name: formValues.full_name.trim(),
                email: formValues.email.trim(),
                ...(formValues.phone.trim() ? { phone: formValues.phone.trim() } : {}),
                ...(formValues.state.trim() ? { state: formValues.state.trim() } : {}),
                ...(formValues.education.trim() ? { education: formValues.education.trim() } : {}),
            })
            closeCreateDialog()
            toast.success("Donor created successfully")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to create donor")
        }
    }

    const filterChips = [
        ...(stageFilter !== "all" ? [{
            key: "stage",
            label: `Stage: ${stages.find((stage) => stage.id === stageFilter)?.label ?? "Stage unavailable"}`,
            clear: () => setUrl({ stage: "all", page: 1 }),
        }] : []),
        ...(dateRange !== "all" ? [{
            key: "date",
            label: `Date: ${getDateRangeLabel(dateRange, customRange)}`,
            clear: () => setUrl({ range: "all", page: 1 }),
        }] : []),
        ...(showArchived ? [{
            key: "archive",
            label: "Archived Donors",
            clear: () => setUrl({ archived: false, page: 1 }),
        }] : []),
        ...(dynamicFilter ? [{
            key: "dynamic",
            label: "Attention Needed: Stuck Donors",
            clear: () => setUrl({ dynamicFilter: null, page: 1 }),
        }] : []),
        ...(ownerId ? [{
            key: "owner",
            label: `Assignee: ${ownerId === user?.user_id && user.display_name ? user.display_name : "Assigned user"}`,
            clear: () => setUrl({ ownerId: null, page: 1 }),
        }] : []),
        ...(committedSearch ? [{
            key: "search",
            label: `Search: ${committedSearch}`,
            clear: () => {
                setSearchDraft({ query, value: "" })
                cancel()
                setUrl({ q: "", page: 1 })
            },
        }] : []),
    ]

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Donors</h1>
                    {canEditDonors ? (
                        <Button
                            onClick={() => {
                                resetCreateForm()
                                setIsCreateOpen(true)
                            }}
                        >
                            <PlusIcon className="mr-2 size-4" />
                            New Donor
                        </Button>
                    ) : null}
                </div>
            </div>

            <div className="flex-1 space-y-6 overflow-auto p-6">
                <Tabs
                    value={donorType}
                    onValueChange={(value) => {
                        if (value === "egg" || value === "sperm") setUrl({ type: value })
                    }}
                >
                    <TabsList aria-label="Donor type">
                        <TabsTrigger value="egg">Egg Donors</TabsTrigger>
                        <TabsTrigger value="sperm">Sperm Donors</TabsTrigger>
                    </TabsList>
                    <TabsContent value={donorType} className="space-y-6">
                <DonorFiltersPanel
                    view={{
                        showArchived,
                        dateRange,
                        customRange,
                        stageFilter,
                        stages,
                        search,
                        isFiltered,
                        chips: filterChips,
                    }}
                    onArchivedChange={(archived) => setUrl({ archived, page: 1 })}
                    onDatePresetChange={(range) => setUrl({
                        range,
                        ...(range === "custom" ? { rangeDates: customRange } : {}),
                        page: 1,
                    })}
                    onCustomDateChange={(rangeDates) => setUrl({
                        range: "custom",
                        rangeDates,
                        page: 1,
                    })}
                    onStageChange={(stage) => setUrl({ stage, page: 1 })}
                    onSearchChange={handleSearchChange}
                    onClearAll={clearAllFilters}
                />

                <DonorListCard
                    view={{
                        donorType,
                        stages,
                        data,
                        isLoading: donorsQuery.isLoading,
                        isError: donorsQuery.isError,
                        error: donorsQuery.error,
                        isFiltered,
                        currentListHref,
                        sortBy,
                        sortOrder,
                    }}
                    onRetry={() => { void donorsQuery.refetch() }}
                    onClearFilters={clearAllFilters}
                    onSort={handleSort}
                />

                {data && data.total > data.per_page ? (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm text-muted-foreground">
                            Showing {(page - 1) * data.per_page + 1} to {Math.min(page * data.per_page, data.total)} of {data.total}
                        </p>
                        <PaginationJump
                            page={page}
                            totalPages={totalPages}
                            onPageChange={(nextPage) => setUrl({ page: nextPage })}
                        />
                    </div>
                ) : null}
                    </TabsContent>
                    <TabsContent value={donorType === "egg" ? "sperm" : "egg"} />
                </Tabs>
            </div>

            <CreateDonorDialog
                donorType={donorType}
                formValues={formValues}
                open={isCreateOpen}
                pending={createDonor.isPending}
                onOpenChange={(open) => {
                    if (open) setIsCreateOpen(true)
                    else closeCreateDialog()
                }}
                onClose={closeCreateDialog}
                onSubmit={handleCreate}
                onFieldChange={(field, value) => {
                    setFormValues((current) => ({ ...current, [field]: value }))
                }}
            />
        </div>
    )
}
