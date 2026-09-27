"use client"

/**
 * Appointments list: filter toolbar, status tabs with counts, a list/calendar toggle, and
 * approve/decline actions for pending requests.
 */

import { useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { ListToolbar, ListToolbarSearch } from "@/components/list-toolbar"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import {
    AppointmentDetailDialog,
    MEETING_MODE_ICONS,
} from "@/components/appointments/AppointmentDetailDialog"
import { SegmentedToggle } from "@/components/appointments/SegmentedToggle"
import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import {
    CheckIcon,
    XIcon,
    ClockIcon,
    CalendarIcon,
    CalendarDaysIcon,
    ListIcon,
    VideoIcon,
    Loader2Icon,
    ChevronRightIcon,
} from "lucide-react"
import {
    useAppointments,
    useAppointmentStatusCounts,
    useAppointmentTypes,
    useApproveAppointment,
    useCancelAppointment,
} from "@/lib/hooks/use-appointments"
import type { AppointmentFilterParams, AppointmentListItem, MeetingMode } from "@/lib/api/appointments"
import { createSchedulingRequestId } from "@/lib/api/appointments"
import { MEETING_MODE_OPTIONS, getMeetingModeLabel, isMeetingMode } from "@/lib/appointment-meeting-mode-labels"
import { getAppointmentStatusLabel } from "@/lib/appointment-status-labels"
import { getAppointmentStatusTone } from "@/lib/appointment-status-tones"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { formatLocalDate } from "@/lib/utils/date"
import { cn } from "@/lib/utils"
import { SchedulingSyncBadge, schedulingCanCancel } from "@/components/appointments/SchedulingSyncState"
import { endOfMonth, endOfWeek, format, parseISO, startOfMonth, startOfWeek } from "date-fns"

// =============================================================================
// Appointment Card
// =============================================================================

function AppointmentCard({
    appointment,
    onSelect,
    trailingActions,
}: {
    appointment: AppointmentListItem
    onSelect: () => void
    trailingActions?: ReactNode
}) {
    const ModeIcon = MEETING_MODE_ICONS[appointment.meeting_mode as keyof typeof MEETING_MODE_ICONS] || VideoIcon
    const initials = appointment.client_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)

    return (
        <div
            className="flex flex-col rounded-lg border border-border transition-colors hover:bg-muted/50 sm:flex-row sm:items-center sm:justify-between"
        >
            <Button unstyled
                type="button"
                className="flex min-w-0 flex-1 cursor-pointer items-center justify-between gap-4 rounded-lg bg-transparent p-4 text-left outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50"
                onClick={onSelect}
            >
                <span className="flex min-w-0 items-center gap-4">
                    <Avatar className="size-12 shrink-0">
                        <AvatarFallback className="bg-primary/10 text-primary">
                            {initials}
                        </AvatarFallback>
                    </Avatar>
                    <span className="min-w-0">
                        <span className="flex min-w-0 flex-wrap items-center gap-1.5">
                            <span className="mr-0.5 font-medium">{appointment.client_name}</span>
                            <Badge className={getAppointmentStatusTone(appointment.status).tint}>
                                {getAppointmentStatusLabel(appointment.status)}
                            </Badge>
                            <SchedulingSyncBadge scheduling={appointment.scheduling} />
                        </span>
                        <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1">
                                <CalendarIcon className="size-3.5" />
                                {format(parseISO(appointment.scheduled_start), "MMM d, yyyy")}
                            </span>
                            <span className="flex items-center gap-1">
                                <ClockIcon className="size-3.5" />
                                {format(parseISO(appointment.scheduled_start), "h:mm a")}
                            </span>
                            <span className="flex items-center gap-1">
                                <ModeIcon className="size-3.5" />
                                {appointment.duration_minutes} min
                            </span>
                        </span>
                        {appointment.appointment_type_name && (
                            <span className="block text-sm text-muted-foreground">
                                {appointment.appointment_type_name}
                            </span>
                        )}
                    </span>
                </span>
                {!trailingActions && (
                    <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
                )}
            </Button>

            {trailingActions && (
                <div className="flex items-center gap-2 px-4 pb-4 sm:pb-0 sm:pl-0">
                    {trailingActions}
                </div>
            )}
        </div>
    )
}

// =============================================================================
// Appointments List Tab Content
// =============================================================================

function AppointmentsTabContent({
    status,
    emptyTitle,
    filters,
    onClearFilters,
}: {
    status: AppointmentStatusTab
    emptyTitle: string
    filters: AppointmentFilterParams
    /** Set while any filter is active: the empty state offers Clear filters instead. */
    onClearFilters: (() => void) | null
}) {
    const { data, isLoading, isError, error, refetch, isFetching } = useAppointments({ status, per_page: 50, ...filters })
    const approveMutation = useApproveAppointment()
    const cancelMutation = useCancelAppointment()
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const [dialogOpen, setDialogOpen] = useState(false)

    if (isLoading) {
        return (
            <div className="py-12 flex items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (isError) {
        return (
            <QueryErrorState
                error={error}
                onRetry={() => void refetch()}
                isRetrying={isFetching}
                title="Couldn't load appointments"
                headingLevel={2}
                className="min-h-0 py-12"
            />
        )
    }

    if (!data?.items.length) {
        return onClearFilters ? (
            <EmptyState icon={CalendarIcon} title="No matching appointments" onClearFilters={onClearFilters} />
        ) : (
            <EmptyState icon={CalendarIcon} title={emptyTitle} />
        )
    }

    return (
        <>
            <div className="space-y-3">
                {data.items.map((appt) => {
                    const isApproving = approveMutation.isPending && approveMutation.variables?.appointmentId === appt.id
                    const isCancelling =
                        cancelMutation.isPending &&
                        cancelMutation.variables?.appointmentId === appt.id
                    const trailingActions = status === "pending" ? (
                        <>
                            <Button
                                size="sm"
                                variant="success"
                                onClick={() => approveMutation.mutate({
                                    appointmentId: appt.id,
                                    ...(appt.scheduling ? { expectedRevision: appt.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
                                })}
                                disabled={isApproving}
                            >
                                {isApproving ? (
                                    <Loader2Icon className="size-4 animate-spin" />
                                ) : (
                                    <CheckIcon className="size-4" />
                                )}
                                <span className="ml-1.5">Approve</span>
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => cancelMutation.mutate({
                                    appointmentId: appt.id,
                                    ...(appt.scheduling ? { expectedRevision: appt.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
                                })}
                                disabled={isCancelling || !schedulingCanCancel(appt.scheduling)}
                                className="text-destructive border-destructive/30 hover:bg-destructive/10"
                            >
                                {isCancelling ? (
                                    <Loader2Icon className="size-4 animate-spin" />
                                ) : (
                                    <XIcon className="size-4" />
                                )}
                                <span className="ml-1.5">Decline</span>
                            </Button>
                        </>
                    ) : null
                    return (
                        <AppointmentCard
                            appointment={appt}
                            onSelect={() => {
                                setSelectedId(appt.id)
                                setDialogOpen(true)
                            }}
                            {...(trailingActions ? { trailingActions } : {})}
                            key={appt.id}
                        />
                    )
                })}
            </div>

            <AppointmentDetailDialog
                appointmentId={selectedId}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
            />
        </>
    )
}

// =============================================================================
// Main Export
// =============================================================================

type AppointmentStatusTab = "confirmed" | "pending" | "completed" | "cancelled" | "expired"

const STATUS_TABS: ReadonlyArray<{ value: AppointmentStatusTab; label: string; emptyTitle: string }> = [
    { value: "confirmed", label: "Upcoming", emptyTitle: "No upcoming appointments" },
    { value: "pending", label: "Pending", emptyTitle: "No pending appointments" },
    { value: "completed", label: "Past", emptyTitle: "No past appointments" },
    { value: "cancelled", label: "Cancelled", emptyTitle: "No cancelled appointments" },
    { value: "expired", label: "Expired", emptyTitle: "No expired appointments" },
]

const isStatusTab = (value: unknown): value is AppointmentStatusTab =>
    STATUS_TABS.some((tab) => tab.value === value)

type AppointmentsView = "list" | "calendar"

const VIEW_OPTIONS = [
    { value: "list", label: "List", icon: <ListIcon aria-hidden="true" /> },
    { value: "calendar", label: "Calendar", icon: <CalendarDaysIcon aria-hidden="true" /> },
] as const satisfies ReadonlyArray<{ value: AppointmentsView; label: string; icon: ReactNode }>

// Below sm the min width makes filters wrap two per row instead of shrinking until labels clip.
const FILTER_TRIGGER_CLASS = "min-w-[calc(50%-0.375rem)] flex-1 bg-background sm:min-w-0 sm:flex-none"

type DateRange ={ from: Date | undefined; to: Date | undefined }

const DATE_PRESET_LABELS: Record<Exclude<DateRangePreset, "custom">, string> = {
    all: "All Time",
    today: "Today",
    week: "This Week",
    month: "This Month",
}

const chipDateFormatter = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" })

function getDateFilterLabel(preset: DateRangePreset, range: DateRange) {
    if (preset !== "custom") return DATE_PRESET_LABELS[preset]
    if (range.from && range.to) return `${chipDateFormatter.format(range.from)} - ${chipDateFormatter.format(range.to)}`
    if (range.from) return `From ${chipDateFormatter.format(range.from)}`
    return "Custom Range"
}

/** Scheduled-date window for a preset; presets cover the current day, week or month. */
function getAppointmentDateParams(preset: DateRangePreset, range: DateRange): AppointmentFilterParams {
    const now = new Date()
    if (preset === "today") return { date_start: formatLocalDate(now), date_end: formatLocalDate(now) }
    if (preset === "week") {
        return { date_start: formatLocalDate(startOfWeek(now)), date_end: formatLocalDate(endOfWeek(now)) }
    }
    if (preset === "month") {
        return { date_start: formatLocalDate(startOfMonth(now)), date_end: formatLocalDate(endOfMonth(now)) }
    }
    if (preset === "custom" && range.from) {
        return {
            date_start: formatLocalDate(range.from),
            ...(range.to ? { date_end: formatLocalDate(range.to) } : {}),
        }
    }
    return {}
}

export function AppointmentsList() {
    const [status, setStatus] = useState<AppointmentStatusTab>("confirmed")
    const [view, setView] = useState<AppointmentsView>("list")
    const [search, setSearch] = useState("")
    const debouncedSearch = useDebouncedValue(search.trim(), 300)
    const [typeFilter, setTypeFilter] = useState("all")
    const [formatFilter, setFormatFilter] = useState<MeetingMode | "all">("all")
    const [datePreset, setDatePreset] = useState<DateRangePreset>("all")
    const [customRange, setCustomRange] = useState<DateRange>({ from: undefined, to: undefined })

    // Inactive types stay listed so past appointments of a retired type can be filtered.
    const { data: appointmentTypes } = useAppointmentTypes(false)
    const typeOptions = (appointmentTypes ?? []).map((type) => ({ value: type.id, label: type.name }))
    const getTypeLabel = (value: string | null | undefined) => {
        if (!value || value === "all") return "All Types"
        return typeOptions.find((option) => option.value === value)?.label ?? "Unknown type"
    }

    // The calendar has its own date navigation, so the date filter applies to the list only.
    const recordFilters: AppointmentFilterParams = {
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
        ...(typeFilter !== "all" ? { appointment_type_id: typeFilter } : {}),
        ...(formatFilter !== "all" ? { meeting_mode: formatFilter } : {}),
    }
    const listFilters: AppointmentFilterParams = {
        ...recordFilters,
        ...getAppointmentDateParams(datePreset, customRange),
    }
    const countsQuery = useAppointmentStatusCounts(listFilters, { enabled: view === "list" })
    const counts = countsQuery.isError ? undefined : countsQuery.data

    const hasFilters =
        search.trim() !== "" || typeFilter !== "all" || formatFilter !== "all" || (view === "list" && datePreset !== "all")

    const resetFilters = () => {
        setSearch("")
        setTypeFilter("all")
        setFormatFilter("all")
        setDatePreset("all")
        setCustomRange({ from: undefined, to: undefined })
    }

    return (
        <>
            <ListToolbar
                filters={
                    <>
                        <SegmentedToggle
                            aria-label="Appointments view"
                            value={view}
                            onValueChange={setView}
                            options={VIEW_OPTIONS}
                            iconOnlyOnMobile
                        />
                        <Select value={typeFilter} onValueChange={(value) => setTypeFilter(value || "all")}>
                            <SelectTrigger aria-label="Filter by type" className={cn(FILTER_TRIGGER_CLASS, "sm:w-[180px]")}>
                                <SelectValue placeholder="All Types">{getTypeLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Types</SelectItem>
                                {typeOptions.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Select
                            value={formatFilter}
                            onValueChange={(value) => setFormatFilter(isMeetingMode(value) ? value : "all")}
                        >
                            <SelectTrigger aria-label="Filter by format" className={cn(FILTER_TRIGGER_CLASS, "sm:w-[160px]")}>
                                <SelectValue placeholder="All Formats">{getMeetingModeLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Formats</SelectItem>
                                {MEETING_MODE_OPTIONS.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {view === "list" && (
                            <DateRangePicker
                                preset={datePreset}
                                onPresetChange={setDatePreset}
                                customRange={customRange}
                                onCustomRangeChange={setCustomRange}
                                ariaLabel="Filter by date"
                                // Shares a row with Format below sm, like the other filters; keeps its own width from sm.
                                className="min-w-[calc(50%-0.375rem)] flex-1 sm:min-w-[13rem] sm:flex-none"
                            />
                        )}
                    </>
                }
                search={
                    <ListToolbarSearch
                        value={search}
                        onValueChange={setSearch}
                        placeholder="Search clients"
                        aria-label="Search appointments by client"
                    />
                }
                chips={[
                    typeFilter !== "all" && {
                        key: "type",
                        label: `Type: ${getTypeLabel(typeFilter)}`,
                        onRemove: () => setTypeFilter("all"),
                    },
                    formatFilter !== "all" && {
                        key: "format",
                        label: `Format: ${getMeetingModeLabel(formatFilter)}`,
                        onRemove: () => setFormatFilter("all"),
                    },
                    view === "list" && datePreset !== "all" && {
                        key: "date",
                        label: `Date: ${getDateFilterLabel(datePreset, customRange)}`,
                        onRemove: () => {
                            setDatePreset("all")
                            setCustomRange({ from: undefined, to: undefined })
                        },
                    },
                    search.trim() !== "" && {
                        key: "search",
                        label: `Search: ${search.trim()}`,
                        onRemove: () => setSearch(""),
                    },
                ]}
                onReset={resetFilters}
            />

            <div className="flex-1 p-6">
                {view === "calendar" ? (
                    <UnifiedCalendar
                        includeTasks={false}
                        includeGoogleEvents={false}
                        appointmentFilters={recordFilters}
                    />
                ) : (
                    <Tabs
                        value={status}
                        onValueChange={(value) => {
                            if (isStatusTab(value)) setStatus(value)
                        }}
                        className="w-full"
                    >
                        <TabsList className="max-w-full justify-start overflow-x-auto">
                            {STATUS_TABS.map((tab) => (
                                <TabsTrigger key={tab.value} value={tab.value}>
                                    {tab.label}
                                    {counts ? (
                                        <span className="text-xs tabular-nums text-muted-foreground">
                                            {counts[tab.value].toLocaleString()}
                                        </span>
                                    ) : null}
                                </TabsTrigger>
                            ))}
                        </TabsList>

                        {STATUS_TABS.map((tab) => (
                            <TabsContent key={tab.value} value={tab.value} className="mt-4">
                                <AppointmentsTabContent
                                    status={tab.value}
                                    emptyTitle={tab.emptyTitle}
                                    filters={listFilters}
                                    onClearFilters={hasFilters ? resetFilters : null}
                                />
                            </TabsContent>
                        ))}
                    </Tabs>
                )}
            </div>
        </>
    )
}
