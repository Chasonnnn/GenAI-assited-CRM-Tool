"use client"

import { useState, type ReactNode } from "react"
import { ArrowRightIcon, Loader2Icon, RefreshCwIcon, VideoIcon } from "lucide-react"
import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DialogBody, DialogClose, DialogFooter, DialogStatusBar } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { toast } from "@/components/ui/toast"
import type {
    GoogleCalendarBinding,
    GoogleCalendarBindingInput,
    GoogleCalendarDiscoveryItem,
} from "@/lib/api/integrations"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import {
    useGoogleCalendarBindings,
    useGoogleCalendarDiscovery,
    useSaveGoogleCalendarBindings,
    useSyncGoogleCalendarBindings,
} from "@/lib/hooks/use-user-integrations"

type Draft = GoogleCalendarBindingInput

function accessRoleLabel(role: string | undefined) {
    if (role === "owner") return "Owner"
    if (role === "writer") return "Can edit"
    if (role === "reader") return "View only"
    if (role === "freeBusyReader") return "Availability only"
    return null
}

function canWriteBookings(role: string | undefined) {
    return role === "owner" || role === "writer"
}

/**
 * Status bar, body and footer of the Google Calendar & Meet dialog. Render it inside a
 * DialogContent with layout="sectioned" after the DialogHeader.
 */
export function GoogleCalendarBindingSettings({
    enabled,
    lastSyncLabel,
    lastSyncTitle,
    notice,
    footerStart,
    onSaved,
    onLegacySync,
    legacySyncPending = false,
}: {
    enabled: boolean
    lastSyncLabel: string
    lastSyncTitle?: string | undefined
    /** Warning shown last in the body, for example the Google Tasks alert. */
    notice?: ReactNode
    /** Footer actions on the left, for example the Disconnect confirm trigger. */
    footerStart?: ReactNode
    onSaved?: () => void
    onLegacySync?: () => void
    legacySyncPending?: boolean
}) {
    const bindings = useGoogleCalendarBindings(enabled)
    const schedulingV2 = bindings.data?.enabled === true
    const discovery = useGoogleCalendarDiscovery(enabled && schedulingV2)
    const save = useSaveGoogleCalendarBindings()
    const sync = useSyncGoogleCalendarBindings()
    const [edits, setEdits] = useState<Record<string, Draft>>({})

    if (!enabled) return null

    const canSync = schedulingV2 || (!bindings.isLoading && !bindings.isError && Boolean(onLegacySync))
    const syncPending = schedulingV2 ? sync.isPending : legacySyncPending
    const handleSync = () => {
        if (!schedulingV2) {
            onLegacySync?.()
            return
        }
        sync.mutate(undefined, {
            onSuccess: () => toast.success("Sync queued"),
            onError: (error) => {
                // null means a rate-limit error, which the API client already reports.
                const message = getActionErrorMessage(error, "Couldn't queue calendar sync")
                if (message) toast.error(message)
            },
        })
    }

    return <>
        <DialogStatusBar>
            <span className="text-muted-foreground">Last sync</span>
            <span className="font-medium" title={lastSyncTitle}>{lastSyncLabel}</span>
            {canSync ? <Button variant="ghost" size="sm" disabled={syncPending} onClick={handleSync}>
                {syncPending
                    ? <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                    : <RefreshCwIcon aria-hidden="true" />}
                Sync now
            </Button> : null}
        </DialogStatusBar>
        <DialogBody>
            {bindings.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading calendar settings…</p> : null}
            {bindings.isError ? <div className="flex items-center gap-2">
                <p role="alert" className="text-sm text-destructive">Unable to load calendar settings.</p>
                <Button size="sm" variant="outline" onClick={() => void bindings.refetch?.()}>Retry</Button>
            </div> : null}
            {schedulingV2 && bindings.data ? <CalendarBindingSections
                bindings={bindings.data.items}
                discovery={discovery}
                edits={edits}
                setEdits={setEdits}
                saveFailed={save.isError}
            /> : null}
            <section className="space-y-2">
                <h3 className="text-sm font-medium">Google Meet</h3>
                <div className="flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2">
                    <VideoIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                    <span className="min-w-0 flex-1 text-sm">Meet links</span>
                    <Badge variant="secondary">Available</Badge>
                    <Button variant="ghost" size="sm" render={<Link href="/settings/appointments" />}>
                        Appointment types
                        <ArrowRightIcon aria-hidden="true" />
                    </Button>
                </div>
            </section>
            {notice}
        </DialogBody>
        <DialogFooter start={footerStart}>
            <DialogClose render={<Button variant="outline" />}>{schedulingV2 ? "Cancel" : "Close"}</DialogClose>
            {schedulingV2 ? <CalendarBindingSaveButton
                bindings={bindings.data?.items ?? []}
                discoveryItems={discovery.data?.items ?? []}
                edits={edits}
                pending={save.isPending}
                onSave={(items) => save.mutate(items, {
                    onSuccess: () => {
                        setEdits({})
                        toast.success("Calendar settings saved")
                        onSaved?.()
                    },
                })}
            /> : null}
        </DialogFooter>
    </>
}

type BindingRow = { current: Draft; initial: Draft; accessRole: string | undefined; syncError: boolean }

function buildBindingRows(
    bindings: GoogleCalendarBinding[],
    available: GoogleCalendarDiscoveryItem[],
    edits: Record<string, Draft>,
): BindingRow[] {
    const boundByCalendar = new Map(bindings.map((item) => [item.calendar_id, toDraft(item)]))
    const calendarIds = new Set([...boundByCalendar.keys(), ...available.map((item) => item.calendar_id)])
    return [...calendarIds].map((calendarId) => {
        const discovered = available.find((item) => item.calendar_id === calendarId)
        const binding = bindings.find((item) => item.calendar_id === calendarId)
        const initial = boundByCalendar.get(calendarId) ?? {
            calendar_id: calendarId,
            display_name: discovered?.display_name ?? calendarId,
            check_busy: false,
            show_events: false,
            write_bookings: false,
            is_active: false,
        }
        return {
            current: edits[calendarId] ?? initial,
            initial,
            accessRole: discovered?.access_role ?? binding?.access_role,
            syncError: Boolean(binding?.sync_error),
        }
    })
}

function toDraft(binding: GoogleCalendarBinding): Draft {
    return {
        calendar_id: binding.calendar_id,
        display_name: binding.display_name,
        check_busy: binding.check_busy,
        show_events: binding.show_events,
        write_bookings: binding.write_bookings,
        is_active: binding.is_active,
    }
}

function isRowDirty({ current, initial }: BindingRow) {
    return current.check_busy !== initial.check_busy
        || current.show_events !== initial.show_events
        || current.write_bookings !== initial.write_bookings
        || current.is_active !== initial.is_active
}

function CalendarBindingSaveButton({
    bindings,
    discoveryItems,
    edits,
    pending,
    onSave,
}: {
    bindings: GoogleCalendarBinding[]
    discoveryItems: GoogleCalendarDiscoveryItem[]
    edits: Record<string, Draft>
    pending: boolean
    onSave: (items: Draft[]) => void
}) {
    const rows = buildBindingRows(bindings, discoveryItems, edits)
    const dirty = rows.some(isRowDirty)
    const saveItems = rows.map(({ current }) => current).filter((item) => item.is_active)
    return <Button disabled={!dirty || pending} onClick={() => onSave(saveItems)}>
        {pending ? <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : null}
        Save changes
    </Button>
}

function CalendarBindingSections({
    bindings,
    discovery,
    edits,
    setEdits,
    saveFailed,
}: {
    bindings: GoogleCalendarBinding[]
    discovery: ReturnType<typeof useGoogleCalendarDiscovery>
    edits: Record<string, Draft>
    setEdits: (updater: (current: Record<string, Draft>) => Record<string, Draft>) => void
    saveFailed: boolean
}) {
    const rows = buildBindingRows(bindings, discovery.data?.items ?? [], edits)
    const destination = rows.find(({ current }) => current.write_bookings)?.current.calendar_id ?? ""
    const update = (next: Draft) => setEdits((current) => ({ ...current, [next.calendar_id]: next }))
    const setDestination = (calendarId: string) => setEdits(() => Object.fromEntries(rows.map(({ current }) => [
        current.calendar_id,
        {
            ...current,
            is_active: current.calendar_id === calendarId ? true : current.is_active,
            write_bookings: current.calendar_id === calendarId,
        },
    ])))

    return <>
        {discovery.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading calendars…</p> : null}
        {discovery.isError ? <div className="flex items-center gap-2"><p role="alert" className="text-sm text-destructive">Unable to load Google calendars.</p><Button size="sm" variant="outline" onClick={() => void discovery.refetch?.()}>Retry</Button></div> : null}
        {!discovery.isLoading && !discovery.isError && rows.length === 0 ? <p className="text-sm text-muted-foreground">No calendars available.</p> : null}
        {rows.length > 0 ? <>
            <section className="space-y-2">
                <Label htmlFor="booking-calendar">Add bookings to</Label>
                <Select value={destination || NO_BOOKING_CALENDAR} onValueChange={(value) => setDestination(value === NO_BOOKING_CALENDAR || !value ? "" : value)}>
                    <SelectTrigger id="booking-calendar" className="w-full sm:w-80">
                        <SelectValue>{(value: string | null) => getBookingCalendarLabel(rows, value)}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value={NO_BOOKING_CALENDAR}>{getBookingCalendarLabel(rows, NO_BOOKING_CALENDAR)}</SelectItem>
                        {rows.map(({ current, accessRole }) => <SelectItem key={current.calendar_id} value={current.calendar_id} disabled={!canWriteBookings(accessRole)}>{current.display_name}{!canWriteBookings(accessRole) ? " — view only" : ""}</SelectItem>)}
                    </SelectContent>
                </Select>
                {!rows.some(({ accessRole }) => canWriteBookings(accessRole)) ? <p role="alert" className="text-sm text-destructive">No writable calendar is available for bookings.</p> : null}
            </section>
            <section className="space-y-2">
                <h3 className="text-sm font-medium">Calendars</h3>
                <div className="rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Calendar</TableHead>
                                {/* The checkbox headers wrap at phone width so both columns fit without clipping. */}
                                <TableHead className="w-24 whitespace-normal text-center sm:w-32">Check conflicts</TableHead>
                                <TableHead className="w-24 whitespace-normal text-center sm:w-32">Show events</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {rows.map(({ current, accessRole, syncError }) => <TableRow key={current.calendar_id}>
                                <TableCell className="whitespace-normal">
                                    <span className="font-medium">{current.display_name}</span>
                                    {accessRoleLabel(accessRole) ? <span className="text-muted-foreground"> · {accessRoleLabel(accessRole)}</span> : null}
                                    {!current.is_active ? <span className="text-muted-foreground"> · Inactive</span> : null}
                                    {syncError ? <p role="alert" className="text-xs text-destructive">Calendar sync needs attention.</p> : null}
                                </TableCell>
                                <TableCell>
                                    <div className="flex justify-center">
                                        <Checkbox
                                            aria-label={`Check conflicts on ${current.display_name}`}
                                            checked={current.check_busy}
                                            onCheckedChange={(checked) => update({ ...current, check_busy: checked === true, is_active: checked === true || current.show_events || current.write_bookings })}
                                        />
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <div className="flex justify-center">
                                        <Checkbox
                                            aria-label={`Show events from ${current.display_name}`}
                                            checked={current.show_events}
                                            onCheckedChange={(checked) => update({ ...current, show_events: checked === true, is_active: checked === true || current.check_busy || current.write_bookings })}
                                        />
                                    </div>
                                </TableCell>
                            </TableRow>)}
                        </TableBody>
                    </Table>
                </div>
            </section>
        </> : null}
        {saveFailed ? <p role="alert" className="text-sm text-destructive">Calendar settings could not be saved.</p> : null}
    </>
}

const NO_BOOKING_CALENDAR = "none"

function getBookingCalendarLabel(rows: BindingRow[], value: string | null) {
    if (value === NO_BOOKING_CALENDAR || !value) return "No booking calendar"
    return rows.find(({ current }) => current.calendar_id === value)?.current.display_name ?? "No booking calendar"
}
