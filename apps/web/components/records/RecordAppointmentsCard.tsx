"use client"

import { getAppointmentStatusLabel } from "@/lib/appointment-status-labels"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AppointmentDetailDialog } from "@/components/appointments/AppointmentsList"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "@/components/ui/toast"
import { listMatches, listMatchAttempts } from "@/lib/api/matches"
import { getMatchAttemptLabel } from "@/components/matches/MatchAttemptDialog"
import { SchedulingSyncBadge } from "@/components/appointments/SchedulingSyncState"
import { SchedulingTimePicker } from "@/components/appointments/SchedulingTimePicker"
import { formatSchedulingDate, formatSchedulingTime, localDateTimeToIso } from "@/lib/scheduling-time"
import { createSchedulingRequestId, createStaffAppointment } from "@/lib/api/appointments"
import { appointmentKeys, useAppointments, useAppointmentTypes, useBookingPreviewSlots } from "@/lib/hooks/use-appointments"

export type RecordContact = { kind: "donor" | "intended_parent"; id: string; name: string; email: string; phone: string | null }

export function RecordAppointmentsCard({ record, canView, canCreate, archived, canViewMatches = false }: {
    record: RecordContact; canView: boolean; canCreate: boolean; archived: boolean; canViewMatches?: boolean
}) {
    const [page, setPage] = useState(1)
    const [createOpen, setCreateOpen] = useState(false)
    const [appointmentId, setAppointmentId] = useState<string | null>(null)
    const query = useAppointments({ [`${record.kind}_id`]: record.id, page, per_page: 10 }, { enabled: canView })
    if (!canView) return null
    return <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2">
            <CardTitle>Appointments</CardTitle>
            {canCreate && !archived && <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>Schedule</Button>}
        </CardHeader>
        <CardContent className="space-y-3">
            {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading appointments…</p>
                : query.isError ? <div role="alert">Unable to load appointments. <Button variant="outline" size="sm" onClick={() => void query.refetch()}>Retry</Button></div>
                    : !query.data?.items.length ? <p className="text-sm text-muted-foreground">No appointments</p>
                        : query.data.items.map(item => <Button key={item.id} variant="ghost" className="h-auto w-full min-w-0 flex-wrap justify-between gap-2 rounded-lg border p-3 text-left sm:flex-nowrap" onClick={() => setAppointmentId(item.id)}>
                            <span className="min-w-0 flex-1"><span className="block truncate">{item.appointment_type_name ?? "Appointment"}</span><span className="block text-xs text-muted-foreground">{formatSchedulingDate(item.scheduled_start, Intl.DateTimeFormat().resolvedOptions().timeZone)} · {formatSchedulingTime(item.scheduled_start, Intl.DateTimeFormat().resolvedOptions().timeZone)}</span></span>
                            <span className="flex max-w-full flex-wrap items-center gap-2 sm:justify-end"><Badge variant="outline">{getAppointmentStatusLabel(item.status)}</Badge><SchedulingSyncBadge scheduling={item.scheduling} /></span>
                        </Button>)}
            {(query.data?.pages ?? 0) > 1 && <div className="flex items-center justify-between"><Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button><span className="text-sm">{page} / {query.data?.pages}</span><Button variant="outline" size="sm" disabled={page >= (query.data?.pages ?? 0)} onClick={() => setPage(page + 1)}>Next</Button></div>}
        </CardContent>
        <AppointmentDetailDialog appointmentId={appointmentId} open={!!appointmentId} onOpenChange={open => { if (!open) setAppointmentId(null) }} />
        <Dialog open={createOpen} onOpenChange={setCreateOpen}><DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] flex-col gap-0 overflow-hidden rounded-2xl p-0 sm:max-w-2xl"><DialogHeader className="shrink-0 border-b px-5 py-4"><DialogTitle>Schedule appointment</DialogTitle></DialogHeader>{createOpen && <ScheduleForm record={record} canViewMatches={canViewMatches} onDone={() => setCreateOpen(false)} />}</DialogContent></Dialog>
    </Card>
}

function ScheduleForm({ record, onDone, canViewMatches }: { record: RecordContact; onDone: () => void; canViewMatches: boolean }) {
    const types = useAppointmentTypes()
    const queryClient = useQueryClient()
    const [matchId, setMatchId] = useState("")
    const [attemptId, setAttemptId] = useState("")
    const matches = useQuery({ queryKey: ["appointment-record-matches", record.kind, record.id], queryFn: () => listMatches({ [`${record.kind}_id`]: record.id, per_page: 100 }), enabled: canViewMatches })
    const attempts = useQuery({ queryKey: ["match-attempts", matchId], queryFn: () => listMatchAttempts(matchId), enabled: !!matchId && canViewMatches })
    const matchLabel = (id: string | null) => { const item = matches.data?.items.find(item => item.id === id); return item ? `${item.match_number} · ${record.kind === "donor" ? item.ip_name : item.donor_name ?? item.surrogate_name}` : "Record only" }
    const attemptLabel = (id: string | null) => { const item = attempts.data?.find(item => item.id === id); return item ? getMatchAttemptLabel(item) : "No attempt" }
    const [typeId, setTypeId] = useState("")
    const [date, setDate] = useState("")
    const [slot, setSlot] = useState<string | null>(null)
    const [phone, setPhone] = useState(record.phone ?? "")
    const [overrideAvailability, setOverrideAvailability] = useState(false)
    const [overrideReason, setOverrideReason] = useState("")
    const [overrideStart, setOverrideStart] = useState("")
    const [idempotencyKey] = useState(() => crypto.randomUUID())
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    const slots = useBookingPreviewSlots(typeId, date, date, timezone, !!typeId && !!date && !overrideAvailability)
    const create = useMutation({ mutationFn: createStaffAppointment, onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: appointmentKeys.all })
        toast.success("Appointment scheduled")
        onDone()
    } })
    const selectedType = types.data?.find(type => type.id === typeId)
    const selectedStart = overrideAvailability ? localDateTimeToIso(overrideStart) : slot
    return <form className="flex min-h-0 flex-1 flex-col" onSubmit={event => {
        event.preventDefault()
        if (!typeId || !selectedStart) return
        if (overrideAvailability && !overrideReason.trim()) return
        create.mutate({ appointment_type_id: typeId, client_name: record.name, client_email: record.email, client_phone: phone, client_timezone: timezone, scheduled_start: selectedStart, idempotency_key: idempotencyKey, request_id: createSchedulingRequestId(), [`${record.kind}_id`]: record.id, ...(overrideAvailability ? { override_availability: true, override_reason: overrideReason.trim() } : {}), ...(matchId ? { match_id: matchId } : {}), ...(attemptId ? { attempt_id: attemptId } : {}) })
    }}>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <div className="text-sm text-muted-foreground">{record.name} · {record.email}</div>
        {types.isError ? <div role="alert">Unable to load appointment types. <Button type="button" variant="outline" onClick={() => void types.refetch()}>Retry</Button></div> : types.isLoading ? <p role="status">Loading appointment types…</p> : !types.data?.length ? <p>No appointment types configured.</p> : <><div className="space-y-2"><Label htmlFor="record-appointment-type">Appointment Type</Label><Select value={typeId} onValueChange={value => { setTypeId(value ?? ""); setSlot(null) }}><SelectTrigger id="record-appointment-type"><SelectValue>{() => selectedType?.name ?? "Select type"}</SelectValue></SelectTrigger><SelectContent>{types.data.map(type => <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-2"><Label htmlFor="record-appointment-phone">Phone</Label><Input id="record-appointment-phone" value={phone} onValueChange={setPhone} minLength={5} maxLength={20} required /></div>
        <SchedulingTimePicker
            idPrefix="record-appointment"
            date={date}
            onDateChange={(value: string) => { setDate(value); setSlot(null) }}
            timezone={timezone}
            slots={slots.data?.slots}
            selectedStart={slot}
            onSelectStart={setSlot}
            loading={!!typeId && !!date && slots.isLoading}
            error={!!typeId && !!date && slots.isError ? "Calendar availability is unavailable." : null}
            onRetry={() => void slots.refetch()}
            disabled={!typeId}
            override={{
                enabled: overrideAvailability,
                onEnabledChange: setOverrideAvailability,
                dateTime: overrideStart,
                onDateTimeChange: setOverrideStart,
                reason: overrideReason,
                onReasonChange: setOverrideReason,
            }}
        />
        {canViewMatches && <details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm font-medium">Match and attempt</summary><div className="mt-3 space-y-4"><div className="space-y-2"><Label htmlFor="record-appointment-case">Match Case</Label><Select value={matchId || "none"} onValueChange={value => { setMatchId(value === "none" ? "" : value ?? ""); setAttemptId("") }}><SelectTrigger id="record-appointment-case"><SelectValue>{(value: string | null) => matchLabel(value)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="none">Record only</SelectItem>{matches.data?.items.map(item => <SelectItem key={item.id} value={item.id}>{matchLabel(item.id)}</SelectItem>)}</SelectContent></Select>{matches.isError && <p role="alert" className="text-sm text-destructive">Unable to load match cases. <Button type="button" variant="ghost" size="sm" onClick={() => void matches.refetch()}>Retry</Button></p>}</div>
        {matchId && <div className="space-y-2"><Label htmlFor="record-appointment-attempt">Attempt</Label><Select value={attemptId || "none"} onValueChange={value => setAttemptId(value === "none" ? "" : value ?? "")}><SelectTrigger id="record-appointment-attempt"><SelectValue>{(value: string | null) => attemptLabel(value)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="none">No attempt</SelectItem>{attempts.data?.map(item => <SelectItem key={item.id} value={item.id}>{getMatchAttemptLabel(item)}</SelectItem>)}</SelectContent></Select>{attempts.isError && <p role="alert" className="text-sm text-destructive">Unable to load attempts. <Button type="button" variant="ghost" size="sm" onClick={() => void attempts.refetch()}>Retry</Button></p>}</div>}
        </div></details>}
        {create.isError && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
        </>}
        </div><div className="flex shrink-0 justify-end gap-2 border-t px-5 py-4"><Button type="button" variant="outline" onClick={onDone}>Back</Button><Button type="submit" disabled={!typeId || !selectedStart || create.isPending || (overrideAvailability && !overrideReason.trim())}>{create.isPending ? "Scheduling…" : "Schedule"}</Button></div>
    </form>
}
