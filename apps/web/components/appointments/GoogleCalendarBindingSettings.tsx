"use client"

import { useState } from "react"
import { Loader2Icon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import type { GoogleCalendarBindingInput } from "@/lib/api/integrations"
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

export function GoogleCalendarBindingSettings({
    enabled,
    onLegacySync,
    legacySyncPending = false,
}: {
    enabled: boolean
    onLegacySync?: () => void
    legacySyncPending?: boolean
}) {
    const bindings = useGoogleCalendarBindings(enabled)
    const discovery = useGoogleCalendarDiscovery(enabled && bindings.data?.enabled === true)
    const save = useSaveGoogleCalendarBindings()
    const sync = useSyncGoogleCalendarBindings()
    const [edits, setEdits] = useState<Record<string, Draft>>({})

    if (!enabled) return null
    if (bindings.isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading calendar settings…</p>
    if (bindings.isError) return <div className="flex items-center gap-2">
        <p role="alert" className="text-sm text-destructive">Unable to load calendar settings.</p>
        <Button size="sm" variant="outline" onClick={() => void bindings.refetch?.()}>Retry</Button>
    </div>

    if (!bindings.data?.enabled) return onLegacySync ? <Button size="sm" variant="secondary" className="w-full" disabled={legacySyncPending} onClick={onLegacySync}>
        {legacySyncPending ? <Loader2Icon className="mr-2 size-3 animate-spin" /> : null}
        Sync
    </Button> : null

    const boundByCalendar = new Map(bindings.data.items.map((item) => [item.calendar_id, { ...item } satisfies Draft]))
    const available = discovery.data?.items ?? []
    const calendarIds = new Set([...boundByCalendar.keys(), ...available.map((item) => item.calendar_id)])
    const rows = [...calendarIds].map((calendarId) => {
        const discovered = available.find((item) => item.calendar_id === calendarId)
        const binding = bindings.data.items.find((item) => item.calendar_id === calendarId)
        const initial = boundByCalendar.get(calendarId) ?? {
            calendar_id: calendarId,
            display_name: discovered?.display_name ?? calendarId,
            check_busy: false,
            show_events: false,
            write_bookings: false,
            is_active: false,
        }
        const current = edits[calendarId] ?? initial
        return { current, initial, accessRole: discovered?.access_role ?? binding?.access_role }
    })
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
    const saveItems = rows.map(({ current }) => current).filter((item) => item.is_active)
    const dirty = rows.some(({ current, initial }) => JSON.stringify(current) !== JSON.stringify(initial))

    return <div className="space-y-4 border-t pt-4">
        <div className="flex justify-end">
            <Button size="sm" variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
                {sync.isPending ? <Loader2Icon className="mr-2 size-3 animate-spin" /> : null}
                Sync
            </Button>
        </div>
        {sync.isError ? <div className="flex items-center gap-2"><p role="alert" className="text-sm text-destructive">Calendar sync could not be queued.</p><Button size="sm" variant="outline" onClick={() => { sync.reset?.(); sync.mutate() }}>Retry</Button></div> : null}
        {discovery.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading calendars…</p> : null}
        {discovery.isError ? <div className="flex items-center gap-2"><p role="alert" className="text-sm text-destructive">Unable to load Google calendars.</p><Button size="sm" variant="outline" onClick={() => void discovery.refetch?.()}>Retry</Button></div> : null}
        {!discovery.isLoading && !discovery.isError && rows.length === 0 ? <p className="text-sm text-muted-foreground">No calendars available.</p> : null}
        {rows.length > 0 ? <div className="space-y-3">
            <div className="space-y-2">
                <Label htmlFor="booking-calendar">Add bookings to</Label>
                <Select value={destination || "none"} onValueChange={(value) => setDestination(value === "none" || !value ? "" : value)}>
                    <SelectTrigger id="booking-calendar">
                        <SelectValue>{(value: string | null) => {
                            if (value === "none" || !value) return "No booking calendar"
                            return rows.find(({ current }) => current.calendar_id === value)?.current.display_name ?? "No booking calendar"
                        }}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="none">No booking calendar</SelectItem>
                        {rows.map(({ current, accessRole }) => <SelectItem key={current.calendar_id} value={current.calendar_id} disabled={!canWriteBookings(accessRole)}>{current.display_name}{!canWriteBookings(accessRole) ? " — view only" : ""}</SelectItem>)}
                    </SelectContent>
                </Select>
                {!rows.some(({ accessRole }) => canWriteBookings(accessRole)) ? <p role="alert" className="text-sm text-destructive">No writable calendar is available for bookings.</p> : null}
            </div>
            <div className="grid gap-3 md:grid-cols-2">{rows.map(({ current, accessRole }) => <div key={current.calendar_id} className="space-y-2 rounded-md border p-3"><div className="flex items-center justify-between gap-3"><span className="min-w-0 truncate text-sm font-medium">{current.display_name}</span>{accessRoleLabel(accessRole) ? <span className="text-xs text-muted-foreground">{accessRoleLabel(accessRole)}</span> : null}</div><div className="flex flex-wrap gap-x-4 gap-y-2 text-sm"><Label className="flex items-center gap-2"><Checkbox checked={current.check_busy} onCheckedChange={(checked) => update({ ...current, check_busy: checked === true, is_active: checked === true || current.show_events || current.write_bookings })} />Check for conflicts</Label><Label className="flex items-center gap-2"><Checkbox checked={current.show_events} onCheckedChange={(checked) => update({ ...current, show_events: checked === true, is_active: checked === true || current.check_busy || current.write_bookings })} />Show in calendar</Label></div>{!current.is_active ? <span className="text-xs text-muted-foreground">Inactive</span> : null}{bindings.data.items.find((item) => item.calendar_id === current.calendar_id)?.sync_error ? <p role="alert" className="text-sm text-destructive">Calendar sync needs attention.</p> : null}</div>)}</div>
        </div> : null}
        {save.isError ? <p role="alert" className="text-sm text-destructive">Calendar settings could not be saved.</p> : null}
        <Button size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate(saveItems, { onSuccess: () => setEdits({}) })}>{save.isPending ? <Loader2Icon className="mr-2 size-3 animate-spin" /> : null}Save changes</Button>
    </div>
}
