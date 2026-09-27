"use client"

import { useState, type FormEvent } from "react"
import type { Route } from "next"
import Link from "@/components/app-link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { PaginationJump } from "@/components/ui/pagination-jump"
import { useDebouncedSearchCommit } from "@/lib/hooks/use-debounced-search-commit"
import {
    Table,
    TableBody,
    TableCell,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    PlusIcon,
    Loader2Icon,
    UsersIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
} from "lucide-react"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import {
    IntendedParentFormFields,
    type IntendedParentFieldValidation,
} from "@/components/intended-parents/IntendedParentFormFields"
import {
    EMPTY_INTENDED_PARENT_FORM_VALUES,
    buildIntendedParentCreatePayload,
    type IntendedParentFormValues,
} from "@/components/intended-parents/intended-parent-form-values"
import {
    useIntendedParents,
    useIntendedParentStats,
    useIntendedParentCreatedDates,
    useCreateIntendedParent,
} from "@/lib/hooks/use-intended-parents"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import {
    getIntendedParentStageOptions,
    getIntendedParentStatusLabel,
    getIntendedParentStatusStyle,
} from "@/lib/intended-parent-stage-utils"
import type { IntendedParentListItem } from "@/lib/types/intended-parent"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { parseDateInput } from "@/lib/utils/date"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { ListToolbar, ListToolbarSearch } from "@/components/list-toolbar"
import { PageHeader } from "@/components/page-header"
import { StageSelect } from "@/components/stage-select"
import { toast } from "@/components/ui/toast"
import { useFormValidation } from "@/lib/forms/use-form-validation"
import { EMAIL_INVALID_MESSAGE, validateEmail, validateRequired } from "@/lib/forms/validators"
import {
    EMPTY_DATE_RANGE,
    getDateRangeBounds,
    getDateRangeFilterLabel,
    readDateRangeParams,
    writeDateRangeParams,
    type DateRangeSelection,
} from "@/lib/date-range-filter"
import { getStageOptionLabel, pipelineStageOptions, type StageOption } from "@/lib/stage-options"
import { ListPageGate } from "./list-page-gate"

type RouterReplace = ReturnType<typeof useRouter>["replace"]
type SearchParamsSnapshot = {
    get: (key: string) => string | null
    toString: () => string
}
type QueryDraft<T> = {
    query: string
    value: T
}
type IntendedParentListUrlState = {
    statusFilter: string
    search: string
    page: number
    dateRange: DateRangePreset
    customRange: DateRangeSelection
}

const DEFAULT_INTENDED_PARENT_LIST_STATE: IntendedParentListUrlState = {
    statusFilter: "all",
    search: "",
    page: 1,
    dateRange: "all",
    customRange: EMPTY_DATE_RANGE,
}

const INTENDED_PARENTS_DENIED_DESCRIPTION =
    "Intended Parents need the View Intended Parents permission. Ask an admin to update your role."

const parsePageParam = (value: string | null): number => {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

function resolveQueryDraft<T>(
    draft: QueryDraft<T> | null,
    currentQuery: string,
    fallback: T,
): T {
    return draft?.query === currentQuery ? draft.value : fallback
}

function readIntendedParentListUrlState(searchParams: SearchParamsSnapshot): IntendedParentListUrlState {
    const { preset, customRange } = readDateRangeParams(searchParams)
    return {
        statusFilter: searchParams.get("status") || "all",
        search: searchParams.get("q") || "",
        page: parsePageParam(searchParams.get("page")),
        dateRange: preset,
        customRange,
    }
}

function updateIntendedParentListUrl(
    replace: RouterReplace,
    searchParams: SearchParamsSnapshot,
    state: IntendedParentListUrlState,
) {
    const newParams = new URLSearchParams(searchParams.toString())
    if (state.statusFilter !== "all") {
        newParams.set("status", state.statusFilter)
    } else {
        newParams.delete("status")
    }
    if (state.search) {
        newParams.set("q", state.search)
    } else {
        newParams.delete("q")
    }
    if (state.page > 1) {
        newParams.set("page", String(state.page))
    } else {
        newParams.delete("page")
    }
    writeDateRangeParams(newParams, state.dateRange, state.customRange)
    const nextQuery = newParams.toString()
    const currentQuery = searchParams.toString()
    if (nextQuery === currentQuery) return
    const newUrl = nextQuery ? `/intended-parents?${nextQuery}` : "/intended-parents"
    const currentUrl = currentQuery ? `/intended-parents?${currentQuery}` : "/intended-parents"
    if (newUrl === currentUrl) return
    replace(newUrl as Route, { scroll: false })
}

function formatIntendedParentCreatedDate(dateStr: string) {
    const parsed = parseDateInput(dateStr)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    })
}

type IntendedParentStatusMetadata = Parameters<typeof getIntendedParentStatusLabel>[0]
type IntendedParentListData = {
    items: IntendedParentListItem[]
    total: number
    per_page: number
}
type IntendedParentSortOrder = "asc" | "desc"

/** IP stages as StageSelect options keyed by stage_key, with counts from the stats endpoint. */
function getIntendedParentStageSelectOptions(
    statusMetadata: IntendedParentStatusMetadata,
    counts: Record<string, number> | undefined,
): StageOption[] {
    return pipelineStageOptions(getIntendedParentStageOptions(statusMetadata), { valueKey: "stage_key" }).map(
        (option) => {
            const count = counts?.[option.value]
            return count === undefined ? option : { ...option, count }
        },
    )
}

function IntendedParentsTableCard({
    data,
    isLoading,
    isError,
    isFetching,
    error,
    hasActiveFilters,
    canCreate,
    sortBy,
    sortOrder,
    statusMetadata,
    onSort,
    onRetry,
    onClearFilters,
    onCreateClick,
}: {
    data: IntendedParentListData | undefined
    isLoading: boolean
    isError: boolean
    isFetching: boolean
    error: unknown
    hasActiveFilters: boolean
    canCreate: boolean
    sortBy: string | null
    sortOrder: IntendedParentSortOrder
    statusMetadata: IntendedParentStatusMetadata
    onSort: (column: string) => void
    onRetry: () => void
    onClearFilters: () => void
    onCreateClick: () => void
}) {
    return (
        <Card className="py-0">
            <CardContent className="p-0">
                {isLoading ? (
                    <div className="flex items-center justify-center py-12" role="status">
                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
                        <span className="ml-2 text-muted-foreground">Loading…</span>
                    </div>
                ) : isError ? (
                    <QueryErrorState
                        error={error}
                        onRetry={onRetry}
                        isRetrying={isFetching}
                        title="Couldn't load intended parents"
                        forbidden={{ description: INTENDED_PARENTS_DENIED_DESCRIPTION, secondaryHref: "/dashboard" }}
                        headingLevel={2}
                    />
                ) : !data?.items.length ? (
                    hasActiveFilters ? (
                        <EmptyState
                            icon={UsersIcon}
                            title="No intended parents found"
                            headingLevel={2}
                            onClearFilters={onClearFilters}
                        />
                    ) : (
                        <EmptyState
                            icon={UsersIcon}
                            title="No intended parents yet"
                            headingLevel={2}
                            action={
                                canCreate ? (
                                    <Button size="sm" onClick={onCreateClick}>
                                        New Intended Parent
                                    </Button>
                                ) : undefined
                            }
                        />
                    )
                ) : (
                    <Table className="[&_th]:!text-center [&_td]:!text-center [&_th>div]:justify-center">
                        <TableHeader>
                            <TableRow>
                                <SortableTableHead column="intended_parent_number" label="IP#" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="email" label="Email" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="phone" label="Phone" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="partner_name" label="Partner" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="status" label="Stage" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.items.map((ip) => (
                                <TableRow key={ip.id} className="cursor-pointer hover:bg-muted/50">
                                    <TableCell>
                                        <Link
                                            href={`/intended-parents/${ip.id}`}
                                            className="font-medium text-primary hover:underline"
                                        >
                                            {ip.intended_parent_number}
                                        </Link>
                                    </TableCell>
                                    <TableCell className="font-medium">
                                        {ip.full_name}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">{ip.email}</TableCell>
                                    <TableCell className="text-muted-foreground">{ip.phone || "—"}</TableCell>
                                    <TableCell className="text-muted-foreground">{ip.state || "—"}</TableCell>
                                    <TableCell className="text-muted-foreground">{ip.partner_name || "—"}</TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            style={getIntendedParentStatusStyle(
                                                statusMetadata,
                                                ip.stage_key ?? ip.status,
                                            )}
                                        >
                                            {getIntendedParentStatusLabel(
                                                statusMetadata,
                                                ip.stage_key ?? ip.status,
                                                ip.status_label,
                                            )}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {formatIntendedParentCreatedDate(ip.created_at)}
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

function IntendedParentsPagination({
    data,
    page,
    totalPages,
    onPageChange,
}: {
    data: IntendedParentListData | undefined
    page: number
    totalPages: number
    onPageChange: (page: number) => void
}) {
    if (!data || data.total <= data.per_page) return null

    return (
        <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * data.per_page + 1} to{" "}
                {Math.min(page * data.per_page, data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-2 flex-wrap">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange(Math.max(1, page - 1))}
                    disabled={page === 1}
                >
                    <ChevronLeftIcon className="size-4" />
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                >
                    <ChevronRightIcon className="size-4" />
                </Button>
                <PaginationJump page={page} totalPages={totalPages} onPageChange={onPageChange} />
            </div>
        </div>
    )
}

function CreateIntendedParentDialog({
    open,
    formData,
    isPending,
    onOpenChange,
    onFieldChange,
    onCancel,
    onCreate,
    validation,
}: {
    open: boolean
    formData: IntendedParentFormValues
    isPending: boolean
    onOpenChange: (open: boolean) => void
    onFieldChange: <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => void
    onCancel: () => void
    onCreate: (event: FormEvent<HTMLFormElement>) => void
    validation: IntendedParentFieldValidation
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent size="lg">
                <DialogHeader>
                    <DialogTitle>New Intended Parent</DialogTitle>
                </DialogHeader>
                <form id="create-intended-parent-form" noValidate onSubmit={onCreate}>
                    <IntendedParentFormFields
                        values={formData}
                        onChange={onFieldChange}
                        idPrefix="create_"
                        showAddressSection={false}
                        showClinicSection={false}
                        validation={validation}
                    />
                </form>
                <DialogFooter>
                    <Button variant="outline" onClick={onCancel}>
                        Cancel
                    </Button>
                    <Button type="submit" form="create-intended-parent-form" disabled={isPending}>
                        {isPending && <Loader2Icon className="mr-2 size-4 animate-spin" aria-hidden="true" />}
                        Create
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default function IntendedParentsPage() {
    return (
        <ListPageGate
            title="Intended Parents"
            permission="view_intended_parents"
            deniedDescription={INTENDED_PARENTS_DENIED_DESCRIPTION}
        >
            <IntendedParentsList />
        </ListPageGate>
    )
}

function IntendedParentsList() {
    const searchParams = useSearchParams()
    const { replace } = useRouter()
    const { can } = usePermissionCheck()
    // Creating an intended parent requires the edit permission (POST /intended-parents).
    const canCreate = can("edit_intended_parents")
    const currentQuery = searchParams.toString()
    const urlState = readIntendedParentListUrlState(searchParams)
    const [stateDraft, setStateDraft] = useState<QueryDraft<IntendedParentListUrlState> | null>(null)
    const listState = resolveQueryDraft(stateDraft, currentQuery, urlState)
    const { statusFilter, search, page, dateRange, customRange } = listState
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [sortBy, setSortBy] = useState<string | null>("intended_parent_number")
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
    const {
        cancel: clearPendingSearchUpdate,
        schedule: scheduleSearchCommit,
    } = useDebouncedSearchCommit(currentQuery)

    /** Applies a filter change right away: the draft shows it until the URL catches up. */
    const applyListState = (patch: Partial<IntendedParentListUrlState>) => {
        const next = { ...listState, page: 1, ...patch }
        clearPendingSearchUpdate()
        setStateDraft({ query: currentQuery, value: next })
        updateIntendedParentListUrl(replace, searchParams, next)
    }

    const handleStatusChange = (status: string) => {
        applyListState({ statusFilter: status || "all" })
    }

    const handlePageChange = (nextPage: number) => {
        applyListState({ page: nextPage })
    }

    const handlePresetChange = (preset: DateRangePreset) => {
        applyListState({ dateRange: preset, customRange: preset === "custom" ? customRange : EMPTY_DATE_RANGE })
    }

    const handleCustomRangeChange = (range: DateRangeSelection) => {
        applyListState({ dateRange: "custom", customRange: range })
    }

    const handleSearchChange = (nextSearch: string) => {
        const next = { ...listState, search: nextSearch, page: 1 }
        setStateDraft({ query: currentQuery, value: next })
        clearPendingSearchUpdate()
        const scheduledQuery = currentQuery
        scheduleSearchCommit(() => {
            if (searchParams.toString() !== scheduledQuery) return
            updateIntendedParentListUrl(replace, searchParams, next)
        }, 300)
    }

    const resetFilters = () => {
        applyListState(DEFAULT_INTENDED_PARENT_LIST_STATE)
    }

    // Form state
    const [formData, setFormData] = useState<IntendedParentFormValues>(EMPTY_INTENDED_PARENT_FORM_VALUES)
    const createValidation = useFormValidation({
        values: formData,
        validate: (values) => ({
            full_name: validateRequired(values.full_name, "Enter a name."),
            email: validateEmail(values.email, { requiredMessage: "Enter an email address." }),
            partner_email: validateEmail(values.partner_email),
        }),
    })

    // Queries
    const dateBounds = getDateRangeBounds(dateRange, customRange)
    const filters = {
        page,
        per_page: 20,
        sort_order: sortOrder,
        ...(dateBounds.from ? { created_after: dateBounds.from } : {}),
        ...(dateBounds.to ? { created_before: dateBounds.to } : {}),
        ...(urlState.search ? { q: urlState.search } : {}),
        ...(statusFilter !== "all" ? { status: [statusFilter] } : {}),
        ...(sortBy ? { sort_by: sortBy } : {}),
    }
    const { data, isLoading, isError, error, refetch, isFetching } = useIntendedParents(filters)
    const { data: availableCreatedDateKeys } = useIntendedParentCreatedDates({
        ...(urlState.search ? { q: urlState.search } : {}),
        ...(statusFilter !== "all" ? { status: [statusFilter] } : {}),
    })
    const { data: stats } = useIntendedParentStats()
    const { data: stageOptionsResponse } = useIntendedParentStatuses()
    const createMutation = useCreateIntendedParent()

    const handleSort = (column: string) => {
        if (sortBy === column) {
            setSortOrder(sortOrder === "asc" ? "desc" : "asc")
        } else {
            setSortBy(column)
            setSortOrder("desc")
        }
    }

    const resetForm = () => {
        setFormData(EMPTY_INTENDED_PARENT_FORM_VALUES)
        createValidation.reset()
    }

    const handleCreate = createValidation.handleSubmit(async (values) => {
        try {
            await createMutation.mutateAsync(buildIntendedParentCreatePayload(values))
            setIsCreateOpen(false)
            resetForm()
            toast.success("Intended parent created")
        } catch (error) {
            const formError = createValidation.applyApiError(error, {
                fields: ["full_name", "email", "partner_email"],
                messages: { email: EMAIL_INVALID_MESSAGE, partner_email: EMAIL_INVALID_MESSAGE },
                fallback: "Couldn't create intended parent. Try again.",
            })
            if (formError) toast.error(formError)
        }
    })

    const updateFormField = <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => {
        setFormData((previous) => ({ ...previous, [field]: value }))
    }

    const totalPages = data ? Math.ceil(data.total / data.per_page) : 1
    const stageOptions = getIntendedParentStageSelectOptions(stageOptionsResponse?.statuses, stats?.by_status)
    const hasActiveFilters = statusFilter !== "all" || dateRange !== "all" || Boolean(urlState.search)

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <PageHeader
                title="Intended Parents"
                count={data?.total}
                countTotal={hasActiveFilters ? stats?.total : undefined}
                countLabel="intended parents"
                actions={
                    canCreate ? (
                        <Button onClick={() => setIsCreateOpen(true)}>
                            <PlusIcon className="mr-2 size-4" aria-hidden="true" />
                            New Intended Parent
                        </Button>
                    ) : null
                }
            />

            <ListToolbar
                filters={
                    <>
                        <StageSelect
                            value={statusFilter}
                            onValueChange={handleStatusChange}
                            options={stageOptions}
                            allLabel="All Stages"
                            className="w-[180px]"
                            aria-label="Filter by stage"
                        />
                        <DateRangePicker
                            preset={dateRange}
                            onPresetChange={handlePresetChange}
                            customRange={customRange}
                            onCustomRangeChange={handleCustomRangeChange}
                            availableDateKeys={availableCreatedDateKeys ?? []}
                            ariaLabel="Created date range"
                        />
                    </>
                }
                search={
                    <ListToolbarSearch
                        placeholder="Search intended parents"
                        value={search}
                        onValueChange={handleSearchChange}
                        aria-label="Search intended parents"
                    />
                }
                chips={[
                    statusFilter !== "all" && {
                        key: "stage",
                        label: `Stage: ${getStageOptionLabel(statusFilter, stageOptions)}`,
                        onRemove: () => applyListState({ statusFilter: "all" }),
                    },
                    dateRange !== "all" && {
                        key: "date",
                        label: `Date: ${getDateRangeFilterLabel(dateRange, customRange)}`,
                        onRemove: () => applyListState({ dateRange: "all", customRange: EMPTY_DATE_RANGE }),
                    },
                    search !== "" && {
                        key: "search",
                        label: `Search: ${search}`,
                        onRemove: () => applyListState({ search: "" }),
                    },
                ]}
                onReset={resetFilters}
            />

            <div className="flex-1 overflow-auto p-6 space-y-6">
                <IntendedParentsTableCard
                    data={data}
                    isLoading={isLoading}
                    isError={isError}
                    isFetching={isFetching}
                    error={error}
                    hasActiveFilters={hasActiveFilters}
                    canCreate={canCreate}
                    sortBy={sortBy}
                    sortOrder={sortOrder}
                    statusMetadata={stageOptionsResponse?.statuses}
                    onSort={handleSort}
                    onRetry={() => { void refetch() }}
                    onClearFilters={resetFilters}
                    onCreateClick={() => setIsCreateOpen(true)}
                />
                <IntendedParentsPagination
                    data={data}
                    page={page}
                    totalPages={totalPages}
                    onPageChange={handlePageChange}
                />
            </div>

            <CreateIntendedParentDialog
                open={isCreateOpen}
                formData={formData}
                isPending={createMutation.isPending}
                onOpenChange={(open) => { setIsCreateOpen(open); if (!open) resetForm() }}
                onFieldChange={updateFormField}
                onCancel={() => { setIsCreateOpen(false); resetForm() }}
                onCreate={(event) => { void handleCreate(event) }}
                validation={createValidation}
            />
        </div>
    )
}
