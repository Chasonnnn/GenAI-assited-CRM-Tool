"use client"

import { useState } from "react"
import type { Route } from "next"
import Link from "@/components/app-link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { PaginationJump } from "@/components/ui/pagination-jump"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { ListToolbar, ListToolbarSearch, MoreFiltersPopover } from "@/components/list-toolbar"
import { NewMatchDialog } from "@/components/matches/NewMatchDialog"
import { PageHeader } from "@/components/page-header"
import { StageSelect } from "@/components/stage-select"
import { useDebouncedSearchCommit } from "@/lib/hooks/use-debounced-search-commit"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import {
    HeartHandshakeIcon,
    Loader2Icon,
    ChevronLeftIcon,
    ChevronRightIcon,
    PlusIcon,
} from "lucide-react"
import { useMatches, useMatchStats, type MatchStatus, type ListMatchesParams } from "@/lib/hooks/use-matches"
import { parseDateInput } from "@/lib/utils/date"
import {
    getMatchStatusBadgeClassName,
    getMatchStatusLabel,
    getMatchKindLabel,
    isMatchStatus,
} from "@/lib/match-status-definitions"
import { getMatchStatusFilterLabel, matchStatusStageOptions } from "@/lib/stage-options"
import {
    EMPTY_DATE_RANGE,
    getDateRangeBounds,
    getDateRangeFilterLabel,
    readDateRangeParams,
    writeDateRangeParams,
    type DateRangeSelection,
} from "@/lib/date-range-filter"
import { ListPageGate } from "../list-page-gate"

type MatchKindFilter = "all" | "surrogate" | "donor"
type MatchStatusFilter = MatchStatus | "all"
type RouterReplace = ReturnType<typeof useRouter>["replace"]
type SearchParamsSnapshot = {
    get: (key: string) => string | null
    toString: () => string
}
type QueryDraft<T> = {
    query: string
    value: T
}
type MatchListUrlState = {
    statusFilter: MatchStatusFilter
    kindFilter: MatchKindFilter
    search: string
    page: number
    datePreset: DateRangePreset
    customRange: DateRangeSelection
}

const DEFAULT_MATCH_LIST_STATE: MatchListUrlState = {
    statusFilter: "all",
    kindFilter: "all",
    search: "",
    page: 1,
    datePreset: "all",
    customRange: EMPTY_DATE_RANGE,
}

const MATCHES_DENIED_DESCRIPTION = "Matches need the View Matches permission. Ask an admin to update your role."

const parsePageParam = (value: string | null): number => {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

function parseMatchKindFilter(value: string | null): MatchKindFilter {
    return value === "donor" || value === "surrogate" ? value : "all"
}

/** The one label helper for the Kind filter: trigger and chip. */
function getMatchKindFilterLabel(value: string | null | undefined): string {
    if (!value || value === "all") return "All Kinds"
    return getMatchKindLabel(value)
}

function resolveQueryDraft<T>(
    draft: QueryDraft<T> | null,
    currentQuery: string,
    fallback: T,
): T {
    return draft?.query === currentQuery ? draft.value : fallback
}

function readMatchListUrlState(searchParams: SearchParamsSnapshot): MatchListUrlState {
    const rawStatus = searchParams.get("status")
    const { preset, customRange } = readDateRangeParams(searchParams)
    return {
        statusFilter: rawStatus && (rawStatus === "all" || isMatchStatus(rawStatus))
            ? rawStatus
            : "all",
        kindFilter: parseMatchKindFilter(searchParams.get("match_kind")),
        search: searchParams.get("q") || "",
        page: parsePageParam(searchParams.get("page")),
        datePreset: preset,
        customRange,
    }
}

function updateMatchListUrl(
    replace: RouterReplace,
    searchParams: SearchParamsSnapshot,
    state: MatchListUrlState,
) {
    const newParams = new URLSearchParams(searchParams.toString())
    if (state.kindFilter !== "all") newParams.set("match_kind", state.kindFilter)
    else newParams.delete("match_kind")
    if (state.statusFilter !== "all") {
        newParams.set("status", state.statusFilter)
    } else {
        newParams.delete("status")
    }
    writeDateRangeParams(newParams, state.datePreset, state.customRange)
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
    const nextQuery = newParams.toString()
    const currentQuery = searchParams.toString()
    if (nextQuery === currentQuery) return
    const newUrl = nextQuery ? `/intended-parents/matches?${nextQuery}` : "/intended-parents/matches"
    const currentUrl = currentQuery ? `/intended-parents/matches?${currentQuery}` : "/intended-parents/matches"
    if (newUrl === currentUrl) return
    replace(newUrl as Route, { scroll: false })
}

function formatMatchProposedDate(dateStr: string) {
    const parsed = parseDateInput(dateStr)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    })
}

export default function MatchesPage() {
    return (
        <ListPageGate title="Matches" permission="view_matches" deniedDescription={MATCHES_DENIED_DESCRIPTION}>
            <MatchesList />
        </ListPageGate>
    )
}

function MatchesList() {
    const searchParams = useSearchParams()
    const { replace } = useRouter()
    const { can } = usePermissionCheck()
    const canProposeMatches = can("propose_matches")
    const [isNewMatchOpen, setIsNewMatchOpen] = useState(false)
    const [isMoreFiltersOpen, setIsMoreFiltersOpen] = useState(false)
    const currentQuery = searchParams.toString()
    const urlState = readMatchListUrlState(searchParams)
    const [stateDraft, setStateDraft] = useState<QueryDraft<MatchListUrlState> | null>(null)
    const listState = resolveQueryDraft(stateDraft, currentQuery, urlState)
    const { statusFilter, kindFilter, search, page, datePreset, customRange } = listState
    const {
        cancel: clearPendingSearchUpdate,
        schedule: scheduleSearchCommit,
    } = useDebouncedSearchCommit(currentQuery)

    /** Applies a filter change right away: the draft shows it until the URL catches up. */
    const applyListState = (patch: Partial<MatchListUrlState>) => {
        const next = { ...listState, page: 1, ...patch }
        clearPendingSearchUpdate()
        setStateDraft({ query: currentQuery, value: next })
        updateMatchListUrl(replace, searchParams, next)
    }

    const handleStatusChange = (value: string) => {
        applyListState({ statusFilter: value === "all" || isMatchStatus(value) ? value : "all" })
    }

    const handleDatePresetChange = (preset: DateRangePreset) => {
        applyListState({ datePreset: preset, customRange: preset === "custom" ? customRange : EMPTY_DATE_RANGE })
    }

    const handleCustomRangeChange = (range: DateRangeSelection) => {
        applyListState({ datePreset: "custom", customRange: range })
    }

    const handlePageChange = (nextPage: number) => {
        applyListState({ page: nextPage })
    }

    const handleSearchChange = (nextSearch: string) => {
        const next = { ...listState, search: nextSearch, page: 1 }
        setStateDraft({ query: currentQuery, value: next })
        clearPendingSearchUpdate()
        const scheduledQuery = currentQuery
        scheduleSearchCommit(() => {
            if (searchParams.toString() !== scheduledQuery) return
            updateMatchListUrl(replace, searchParams, next)
        }, 300)
    }

    const resetFilters = () => {
        applyListState(DEFAULT_MATCH_LIST_STATE)
    }

    const dateBounds = getDateRangeBounds(datePreset, customRange)
    const filters = {
        page,
        per_page: 20,
        sort_by: "match_number",
        sort_order: "desc",
        ...(statusFilter !== "all" && isMatchStatus(statusFilter)
            ? { status: statusFilter }
            : {}),
        ...(kindFilter !== "all" ? { match_kind: kindFilter } : {}),
        ...(urlState.search ? { q: urlState.search } : {}),
        ...(dateBounds.from ? { proposed_from: dateBounds.from } : {}),
        ...(dateBounds.to ? { proposed_to: dateBounds.to } : {}),
    } satisfies ListMatchesParams
    const { data, isLoading, isError, error, refetch, isFetching } = useMatches(filters)
    const { data: stats } = useMatchStats()

    const stageOptions = matchStatusStageOptions(stats?.by_status)
    const hasActiveFilters =
        statusFilter !== "all" || kindFilter !== "all" || datePreset !== "all" || Boolean(urlState.search)
    const totalPages = data ? Math.ceil(data.total / data.per_page) : 1

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <PageHeader
                title="Matches"
                count={data?.total}
                countTotal={hasActiveFilters ? stats?.total : undefined}
                countLabel="matches"
                actions={
                    canProposeMatches ? (
                        <Button onClick={() => setIsNewMatchOpen(true)}>
                            <PlusIcon className="mr-2 size-4" aria-hidden="true" />
                            New Match
                        </Button>
                    ) : null
                }
            />

            {isNewMatchOpen ? (
                <NewMatchDialog open={isNewMatchOpen} onOpenChange={setIsNewMatchOpen} />
            ) : null}

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
                            preset={datePreset}
                            onPresetChange={handleDatePresetChange}
                            customRange={customRange}
                            onCustomRangeChange={handleCustomRangeChange}
                            ariaLabel="Proposed date range"
                        />
                        <MoreFiltersPopover
                            open={isMoreFiltersOpen}
                            onOpenChange={setIsMoreFiltersOpen}
                            active={kindFilter !== "all"}
                        >
                            <div className="grid gap-2">
                                <Label>Kind</Label>
                                <Select
                                    value={kindFilter}
                                    onValueChange={(value) => applyListState({ kindFilter: parseMatchKindFilter(value) })}
                                >
                                    <SelectTrigger aria-label="Filter by kind">
                                        <SelectValue placeholder="All Kinds">
                                            {(value: string | null) => getMatchKindFilterLabel(value)}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All Kinds</SelectItem>
                                        <SelectItem value="surrogate">Surrogate</SelectItem>
                                        <SelectItem value="donor">Donor</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </MoreFiltersPopover>
                    </>
                }
                search={
                    <ListToolbarSearch
                        placeholder="Search matches"
                        value={search}
                        onValueChange={handleSearchChange}
                        aria-label="Search matches"
                    />
                }
                chips={[
                    statusFilter !== "all" && {
                        key: "stage",
                        label: `Stage: ${getMatchStatusFilterLabel(statusFilter)}`,
                        onRemove: () => applyListState({ statusFilter: "all" }),
                    },
                    datePreset !== "all" && {
                        key: "date",
                        label: `Proposed: ${getDateRangeFilterLabel(datePreset, customRange)}`,
                        onRemove: () => applyListState({ datePreset: "all", customRange: EMPTY_DATE_RANGE }),
                    },
                    kindFilter !== "all" && {
                        key: "kind",
                        label: `Kind: ${getMatchKindFilterLabel(kindFilter)}`,
                        onRemove: () => applyListState({ kindFilter: "all" }),
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
                                onRetry={() => { void refetch() }}
                                isRetrying={isFetching}
                                title="Couldn't load matches"
                                forbidden={{ description: MATCHES_DENIED_DESCRIPTION, secondaryHref: "/dashboard" }}
                                headingLevel={2}
                            />
                        ) : !data?.items.length ? (
                            hasActiveFilters ? (
                                <EmptyState
                                    icon={HeartHandshakeIcon}
                                    title="No matches found"
                                    headingLevel={2}
                                    onClearFilters={resetFilters}
                                />
                            ) : (
                                <EmptyState
                                    icon={HeartHandshakeIcon}
                                    title="No matches yet"
                                    headingLevel={2}
                                    action={
                                        canProposeMatches ? (
                                            <Button size="sm" onClick={() => setIsNewMatchOpen(true)}>
                                                New Match
                                            </Button>
                                        ) : undefined
                                    }
                                />
                            )
                        ) : (
                            <Table className="[&_th]:!text-center [&_td]:!text-center [&_th>div]:justify-center">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Match #</TableHead>
                                        <TableHead>Participant</TableHead>
                                        <TableHead>Participant #</TableHead>
                                        <TableHead>Intended Parents</TableHead>
                                        <TableHead>Match Stage</TableHead>
                                        <TableHead>Participant Stage</TableHead>
                                        <TableHead>Proposed</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((match) => (
                                        <TableRow key={match.id} className="cursor-pointer hover:bg-muted/50">
                                            <TableCell>
                                                <Link
                                                    href={`/intended-parents/matches/${match.id}`}
                                                    className="font-medium text-primary hover:underline"
                                                >
                                                    {match.match_number || "—"}
                                                </Link>
                                            </TableCell>
                                            <TableCell className="font-medium">
                                                <Link
                                                    href={`/intended-parents/matches/${match.id}`}
                                                    className="text-primary hover:underline underline-offset-4"
                                                >
                                                    {(match.match_kind === "donor" ? match.donor_name : match.surrogate_name) || "—"}
                                                </Link>
                                                <Badge variant="outline" className="ml-2 text-xs">{getMatchKindLabel(match.match_kind)}</Badge>
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {(match.match_kind === "donor" ? match.donor_number : match.surrogate_number) || "—"}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                <Link
                                                    href={`/intended-parents/matches/${match.id}`}
                                                    className="text-primary hover:underline underline-offset-4"
                                                >
                                                    {match.ip_name || "—"}
                                                </Link>
                                            </TableCell>
                                            <TableCell>
                                                {(() => {
                                                    const status = isMatchStatus(match.status)
                                                        ? match.status
                                                        : "proposed"
                                                    return (
                                                        <Badge className={getMatchStatusBadgeClassName(status)}>
                                                            {getMatchStatusLabel(status)}
                                                        </Badge>
                                                    )
                                                })()}
                                            </TableCell>
                                            <TableCell>
                                                {(match.match_kind === "donor" ? match.donor_stage_label : match.surrogate_stage_label) ? (
                                                    <Badge variant="outline" className="text-xs">
                                                        {match.match_kind === "donor" ? match.donor_stage_label : match.surrogate_stage_label}
                                                    </Badge>
                                                ) : (
                                                    <span className="text-muted-foreground">No stage</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {formatMatchProposedDate(match.proposed_at)}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>

                {/* Pagination */}
                {data && data.total > data.per_page && (
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-muted-foreground">
                            Showing {(page - 1) * data.per_page + 1} to{" "}
                            {Math.min(page * data.per_page, data.total)} of {data.total}
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handlePageChange(Math.max(1, page - 1))}
                                disabled={page === 1}
                            >
                                <ChevronLeftIcon className="size-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
                                disabled={page === totalPages}
                            >
                                <ChevronRightIcon className="size-4" />
                            </Button>
                            <PaginationJump page={page} totalPages={totalPages} onPageChange={handlePageChange} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
