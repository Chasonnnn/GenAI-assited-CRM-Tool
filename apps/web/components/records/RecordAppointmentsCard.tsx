"use client"

import { getAppointmentStatusLabel } from "@/lib/appointment-status-labels"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format, parseISO } from "date-fns"
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
import { createStaffAppointment } from "@/lib/api/appointments"
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
                        : query.data.items.map(item => <Button key={item.id} variant="ghost" className="h-auto w-full justify-between gap-3 border p-3 text-left" onClick={() => setAppointmentId(item.id)}>
                            <span className="min-w-0"><span className="block truncate">{item.appointment_type_name ?? "Appointment"}</span><span className="block text-xs text-muted-foreground">{format(parseISO(item.scheduled_start), "MMM d, yyyy · h:mm a")}</span></span>
                            <Badge variant="outline">{getAppointmentStatusLabel(item.status)}</Badge>
                        </Button>)}
            {(query.data?.pages ?? 0) > 1 && <div className="flex items-center justify-between"><Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button><span className="text-sm">{page} / {query.data?.pages}</span><Button variant="outline" size="sm" disabled={page >= (query.data?.pages ?? 0)} onClick={() => setPage(page + 1)}>Next</Button></div>}
        </CardContent>
        <AppointmentDetailDialog appointmentId={appointmentId} open={!!appointmentId} onOpenChange={open => { if (!open) setAppointmentId(null) }} />
        <Dialog open={createOpen} onOpenChange={setCreateOpen}><DialogContent><DialogHeader><DialogTitle>Schedule Appointment</DialogTitle></DialogHeader>{createOpen && <ScheduleForm record={record} canViewMatches={canViewMatches} onDone={() => setCreateOpen(false)} />}</DialogContent></Dialog>
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
    const [slot, setSlot] = useState("")
    const [phone, setPhone] = useState(record.phone ?? "")
    const [idempotencyKey] = useState(() => crypto.randomUUID())
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    const slots = useBookingPreviewSlots(typeId, date, date, timezone, !!typeId && !!date)
    const create = useMutation({ mutationFn: createStaffAppointment, onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: appointmentKeys.all })
        toast.success("Appointment scheduled")
        onDone()
    } })
    const selectedType = types.data?.find(type => type.id === typeId)
    return <form className="space-y-4" onSubmit={event => {
        event.preventDefault()
        if (!slot) return
        create.mutate({ appointment_type_id: typeId, client_name: record.name, client_email: record.email, client_phone: phone, client_timezone: timezone, scheduled_start: slot, idempotency_key: idempotencyKey, [`${record.kind}_id`]: record.id, ...(matchId ? { match_id: matchId } : {}), ...(attemptId ? { attempt_id: attemptId } : {}) })
    }}>
        {types.isError ? <div role="alert">Unable to load appointment types. <Button type="button" variant="outline" onClick={() => void types.refetch()}>Retry</Button></div> : types.isLoading ? <p role="status">Loading appointment types…</p> : !types.data?.length ? <p>No appointment types configured.</p> : <><div className="space-y-2"><Label htmlFor="record-appointment-type">Appointment Type</Label><Select value={typeId} onValueChange={value => { setTypeId(value ?? ""); setSlot("") }}><SelectTrigger id="record-appointment-type"><SelectValue>{() => selectedType?.name ?? "Select type"}</SelectValue></SelectTrigger><SelectContent>{types.data.map(type => <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>)}</SelectContent></Select></div>
        {canViewMatches && <div className="space-y-2"><Label htmlFor="record-appointment-case">Match Case</Label><Select value={matchId || "none"} onValueChange={value => { setMatchId(value === "none" ? "" : value ?? ""); setAttemptId("") }}><SelectTrigger id="record-appointment-case"><SelectValue>{(value: string | null) => matchLabel(value)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="none">Record only</SelectItem>{matches.data?.items.map(item => <SelectItem key={item.id} value={item.id}>{matchLabel(item.id)}</SelectItem>)}</SelectContent></Select>{matches.isError && <p role="alert" className="text-sm text-destructive">Unable to load match cases. <Button type="button" variant="ghost" size="sm" onClick={() => void matches.refetch()}>Retry</Button></p>}</div>}
        {matchId && <div className="space-y-2"><Label htmlFor="record-appointment-attempt">Attempt</Label><Select value={attemptId || "none"} onValueChange={value => setAttemptId(value === "none" ? "" : value ?? "")}><SelectTrigger id="record-appointment-attempt"><SelectValue>{(value: string | null) => attemptLabel(value)}</SelectValue></SelectTrigger><SelectContent><SelectItem value="none">No attempt</SelectItem>{attempts.data?.map(item => <SelectItem key={item.id} value={item.id}>{getMatchAttemptLabel(item)}</SelectItem>)}</SelectContent></Select>{attempts.isError && <p role="alert" className="text-sm text-destructive">Unable to load attempts. <Button type="button" variant="ghost" size="sm" onClick={() => void attempts.refetch()}>Retry</Button></p>}</div>}
        <div className="space-y-2"><Label htmlFor="record-appointment-phone">Phone</Label><Input id="record-appointment-phone" value={phone} onChange={event => setPhone(event.target.value)} minLength={5} maxLength={20} required /></div>
        <div className="space-y-2"><Label htmlFor="record-appointment-date">Date · {timezone}</Label><Input id="record-appointment-date" type="date" value={date} min={format(new Date(), "yyyy-MM-dd")} onChange={event => { setDate(event.target.value); setSlot("") }} required /></div>
        {typeId && date && (slots.isLoading ? <p role="status">Loading times…</p> : slots.isError ? <div role="alert">Unable to load available times. <Button type="button" variant="outline" onClick={() => void slots.refetch()}>Retry</Button></div> : !slots.data?.slots.length ? <p>No available times</p> : <div className="flex flex-wrap gap-2" aria-label="Available times">{slots.data.slots.map(time => <Button type="button" key={time.start} variant={slot === time.start ? "default" : "outline"} onClick={() => setSlot(time.start)} aria-pressed={slot === time.start}>{format(parseISO(time.start), "h:mm a")}</Button>)}</div>)}
        {create.isError && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
        <div className="flex justify-end"><Button type="submit" disabled={!slot || create.isPending}>{create.isPending ? "Scheduling…" : "Schedule"}</Button></div></>}
    </form>
}
