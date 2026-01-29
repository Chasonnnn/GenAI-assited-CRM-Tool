"use client"

/**
 * Appointments List - Dashboard for viewing and managing appointments
 * 
 * Features:
 * - Tabs for pending/upcoming/past
 * - Approval workflow for pending
 * - Quick actions (approve, cancel)
 * - Detail side panel
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
    CheckIcon,
    XIcon,
    ClockIcon,
    CalendarIcon,
    PhoneIcon,
    MailIcon,
    VideoIcon,
    MapPinIcon,
    Loader2Icon,
    AlertCircleIcon,
    ChevronRightIcon,
} from "lucide-react"
import {
    useAppointments,
    useAppointment,
    useApproveAppointment,
    useCancelAppointment,
} from "@/lib/hooks/use-appointments"
import type { AppointmentListItem } from "@/lib/api/appointments"
import { format, parseISO } from "date-fns"

// Status badge colors
const STATUS_STYLES = {
    pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    confirmed: "bg-green-500/10 text-green-600 border-green-500/20",
    completed: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    cancelled: "bg-red-500/10 text-red-600 border-red-500/20",
    no_show: "bg-gray-500/10 text-gray-600 border-gray-500/20",
    expired: "bg-gray-500/10 text-gray-600 border-gray-500/20",
}

// Meeting mode icons
const MEETING_MODE_ICONS: Record<string, typeof VideoIcon> = {
    zoom: VideoIcon,
    google_meet: VideoIcon,
    phone: PhoneIcon,
    in_person: MapPinIcon,
}

// =============================================================================
// Appointment Card
// =============================================================================

function AppointmentCard({
    appointment,
    onSelect,
    onApprove,
    onCancel,
    isApproving,
    isCancelling,
}: {
    appointment: AppointmentListItem
    onSelect: () => void
    onApprove?: () => void
    onCancel?: () => void
    isApproving?: boolean
    isCancelling?: boolean
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
            className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-colors"
            onClick={onSelect}
        >
            <div className="flex items-center gap-4">
                <Avatar className="size-12">
                    <AvatarFallback className="bg-primary/10 text-primary">
                        {initials}
                    </AvatarFallback>
                </Avatar>
                <div>
                    <div className="flex items-center gap-2">
                        <h4 className="font-medium">{appointment.client_name}</h4>
                        <Badge className={STATUS_STYLES[appointment.status as keyof typeof STATUS_STYLES]}>
                            {appointment.status.replace("_", " ")}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
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
                    </div>
                    {appointment.appointment_type_name && (
                        <p className="text-sm text-muted-foreground">
                            {appointment.appointment_type_name}
                        </p>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                {appointment.status === "pending" && onApprove && onCancel && (
                    <>
                        <Button
                            size="sm"
                            onClick={onApprove}
                            disabled={isApproving}
                            className="bg-green-600 hover:bg-green-700"
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
                            onClick={onCancel}
                            disabled={isCancelling}
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
                )}
                {appointment.status !== "pending" && (
                    <ChevronRightIcon className="size-5 text-muted-foreground" />
                )}
            </div>
        </div>
    )
}

// =============================================================================
// Appointment Detail Dialog
// =============================================================================

function AppointmentDetailDialog({
    appointmentId,
    open,
    onOpenChange,
}: {
    appointmentId: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
}) {
    const { data: appointment, isLoading, isError, refetch } = useAppointment(appointmentId || "")
    const approveMutation = useApproveAppointment()
    const cancelMutation = useCancelAppointment()
    const [cancelReason, setCancelReason] = useState("")
    const [showCancelForm, setShowCancelForm] = useState(false)

    if (!appointmentId) return null

    const handleApprove = () => {
        approveMutation.mutate(appointmentId, {
            onSuccess: () => onOpenChange(false),
        })
    }

    const handleCancel = () => {
        const payload = {
            appointmentId,
            ...(cancelReason.trim() ? { reason: cancelReason.trim() } : {}),
        }
        cancelMutation.mutate(payload, { onSuccess: () => onOpenChange(false) })
    }

    if (isLoading) {
        return (
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent>
                    <div className="py-12 flex items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                </DialogContent>
            </Dialog>
        )
    }

    if (isError) {
        return (
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent>
                    <div className="py-10 text-center space-y-4">
                        <AlertCircleIcon className="size-10 mx-auto text-muted-foreground/60" />
                        <div>
                            <p className="font-medium">Unable to load appointment details</p>
                            <p className="text-sm text-muted-foreground">Please retry in a moment.</p>
                        </div>
                        <Button variant="outline" onClick={() => refetch()}>
                            Retry
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        )
    }

    if (!appointment) return null

    const ModeIcon = MEETING_MODE_ICONS[appointment.meeting_mode as keyof typeof MEETING_MODE_ICONS] || VideoIcon

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>Appointment Details</DialogTitle>
                    <DialogDescription>
                        {appointment.appointment_type_name || "Appointment"} with {appointment.client_name}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                    {/* Status Badge */}
                    <div className="flex items-center gap-2">
                        <Badge className={`${STATUS_STYLES[appointment.status]} text-sm px-3 py-1`}>
                            {appointment.status.replace("_", " ").toUpperCase()}
                        </Badge>
                        {appointment.status === "pending" && appointment.pending_expires_at && (
                            <span className="text-sm text-muted-foreground">
                                Expires {format(parseISO(appointment.pending_expires_at), "h:mm a")}
                            </span>
                        )}
                    </div>

                    {/* Date/Time */}
                    <div className="flex items-start gap-3">
                        <CalendarIcon className="size-5 text-muted-foreground mt-0.5" />
                        <div>
                            <p className="font-medium">
                                {format(parseISO(appointment.scheduled_start), "EEEE, MMMM d, yyyy")}
                            </p>
                            <p className="text-sm text-muted-foreground">
                                {format(parseISO(appointment.scheduled_start), "h:mm a")} –{" "}
                                {format(parseISO(appointment.scheduled_end), "h:mm a")}
                                <span className="ml-2">({appointment.duration_minutes} min)</span>
                            </p>
                        </div>
                    </div>

                    {/* Appointment Format */}
                    <div className="flex items-center gap-3">
                        <ModeIcon className="size-5 text-muted-foreground" />
                        <p className="font-medium capitalize">{appointment.meeting_mode.replace("_", " ")}</p>
                        {appointment.zoom_join_url && (
                            <a
                                href={appointment.zoom_join_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary underline text-sm"
                            >
                                Join Zoom
                            </a>
                        )}
                        {appointment.google_meet_url && (
                            <a
                                href={appointment.google_meet_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary underline text-sm"
                            >
                                Join Google Meet
                            </a>
                        )}
                    </div>

                    {/* Client Info */}
                    <div className="border-t border-border pt-4">
                        <h4 className="text-sm font-medium text-muted-foreground mb-3">Client Information</h4>
                        <div className="space-y-2">
                            <p className="font-medium">{appointment.client_name}</p>
                            <p className="text-sm flex items-center gap-2">
                                <MailIcon className="size-4 text-muted-foreground" />
                                <a href={`mailto:${appointment.client_email}`} className="text-primary hover:underline">
                                    {appointment.client_email}
                                </a>
                            </p>
                            <p className="text-sm flex items-center gap-2">
                                <PhoneIcon className="size-4 text-muted-foreground" />
                                <a href={`tel:${appointment.client_phone}`} className="text-primary hover:underline">
                                    {appointment.client_phone}
                                </a>
                            </p>
                            {appointment.client_notes && (
                                <div className="mt-3 p-3 rounded-lg bg-muted">
                                    <p className="text-sm text-muted-foreground font-medium mb-1">Notes</p>
                                    <p className="text-sm">{appointment.client_notes}</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Cancel Form */}
                    {showCancelForm && (
                        <div className="border-t border-border pt-4">
                            <Label className="mb-2">Cancellation Reason (optional)</Label>
                            <Textarea
                                value={cancelReason}
                                onChange={(e) => setCancelReason(e.target.value)}
                                placeholder="Enter reason for cancellation..."
                                rows={3}
                            />
                        </div>
                    )}
                </div>

                {/* Actions */}
                {appointment.status === "pending" && (
                    <div className="flex justify-end gap-2 pt-4 border-t border-border">
                        {showCancelForm ? (
                            <>
                                <Button variant="outline" onClick={() => setShowCancelForm(false)}>
                                    Back
                                </Button>
                                <Button
                                    variant="destructive"
                                    onClick={handleCancel}
                                    disabled={cancelMutation.isPending}
                                >
                                    {cancelMutation.isPending && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                                    Confirm Cancel
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    variant="outline"
                                    onClick={() => setShowCancelForm(true)}
                                    className="text-destructive"
                                >
                                    Decline
                                </Button>
                                <Button
                                    onClick={handleApprove}
                                    disabled={approveMutation.isPending}
                                    className="bg-green-600 hover:bg-green-700"
                                >
                                    {approveMutation.isPending && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                                    Approve
                                </Button>
                            </>
                        )}
                    </div>
                )}

                {appointment.status === "confirmed" && (
                    <div className="flex justify-end gap-2 pt-4 border-t border-border">
                        <Button
                            variant="outline"
                            onClick={() => setShowCancelForm(true)}
                            className="text-destructive"
                        >
                            Cancel Appointment
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    )
}

// =============================================================================
// Empty State
// =============================================================================

function EmptyState({ message }: { message: string }) {
    return (
        <div className="text-center py-12">
            <AlertCircleIcon className="size-12 mx-auto mb-4 text-muted-foreground/50" />
            <p className="text-muted-foreground">{message}</p>
        </div>
    )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <div className="text-center py-12 space-y-4">
            <AlertCircleIcon className="size-12 mx-auto text-muted-foreground/50" />
            <div className="space-y-1">
                <p className="font-medium">{message}</p>
                <p className="text-sm text-muted-foreground">Please try again.</p>
            </div>
            <Button variant="outline" onClick={onRetry}>
                Retry
            </Button>
        </div>
    )
}

// =============================================================================
// Appointments List Tab Content
// =============================================================================

function AppointmentsTabContent({
    status,
    emptyMessage,
}: {
    status: string
    emptyMessage: string
}) {
    const { data, isLoading, isError, refetch } = useAppointments({ status, per_page: 50 })
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
        return <ErrorState message="Unable to load appointments" onRetry={() => refetch()} />
    }

    if (!data?.items.length) {
        return <EmptyState message={emptyMessage} />
    }

    return (
        <>
            <div className="space-y-3">
                {data.items.map((appt) => {
                    const onApprove = status === "pending"
                        ? () => approveMutation.mutate(appt.id)
                        : undefined
                    const onCancel = status === "pending"
                        ? () => cancelMutation.mutate({ appointmentId: appt.id })
                        : undefined
                    return (
                        <AppointmentCard
                            key={appt.id}
                            appointment={appt}
                            onSelect={() => {
                                setSelectedId(appt.id)
                                setDialogOpen(true)
                            }}
                            isApproving={approveMutation.isPending && approveMutation.variables === appt.id}
                            isCancelling={
                                cancelMutation.isPending &&
                                cancelMutation.variables?.appointmentId === appt.id
                            }
                            {...(onApprove ? { onApprove } : {})}
                            {...(onCancel ? { onCancel } : {})}
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

export function AppointmentsList() {
    return (
        <Tabs defaultValue="pending" className="w-full">
            <TabsList>
                <TabsTrigger value="pending">Pending</TabsTrigger>
                <TabsTrigger value="confirmed">Upcoming</TabsTrigger>
                <TabsTrigger value="completed">Past</TabsTrigger>
                <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
                <TabsTrigger value="expired">Expired</TabsTrigger>
            </TabsList>

            <TabsContent value="pending" className="mt-4">
                <AppointmentsTabContent
                    status="pending"
                    emptyMessage="No pending requests. New booking requests will appear here."
                />
            </TabsContent>

            <TabsContent value="confirmed" className="mt-4">
                <AppointmentsTabContent
                    status="confirmed"
                    emptyMessage="No upcoming appointments."
                />
            </TabsContent>

            <TabsContent value="completed" className="mt-4">
                <AppointmentsTabContent
                    status="completed"
                    emptyMessage="No past appointments."
                />
            </TabsContent>

            <TabsContent value="cancelled" className="mt-4">
                <AppointmentsTabContent
                    status="cancelled"
                    emptyMessage="No cancelled appointments."
                />
            </TabsContent>

            <TabsContent value="expired" className="mt-4">
                <AppointmentsTabContent
                    status="expired"
                    emptyMessage="No expired requests."
                />
            </TabsContent>
        </Tabs>
    )
}
