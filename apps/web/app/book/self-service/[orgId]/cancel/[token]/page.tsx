"use client"

/**
 * Self-Service Cancel Page - /book/self-service/[orgId]/cancel/[token]
 *
 * Allows clients to cancel their appointment using a secure token.
 */

import { use, useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    CalendarIcon,
    ClockIcon,
    Loader2Icon,
    CheckCircleIcon,
    AlertCircleIcon,
    AlertTriangleIcon,
} from "lucide-react"
import { format, parseISO } from "date-fns"
import type { PublicAppointmentView } from "@/lib/api/appointments"
import { getAppointmentForCancel, cancelByToken } from "@/lib/api/appointments"

interface PageProps {
    params: Promise<{ orgId?: string | string[]; token?: string | string[] }>
}

export default function CancelPage({ params }: PageProps) {
    const resolvedParams = use(params)
    const rawOrgId = resolvedParams.orgId
    const rawToken = resolvedParams.token
    const orgId = Array.isArray(rawOrgId) ? rawOrgId[0] : rawOrgId
    const token = Array.isArray(rawToken) ? rawToken[0] : rawToken

    const [appointment, setAppointment] = useState<PublicAppointmentView | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [reason, setReason] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isConfirmed, setIsConfirmed] = useState(false)
    const [showConfirmDialog, setShowConfirmDialog] = useState(false)

    // Fetch appointment
    useEffect(() => {
        if (!orgId || !token) {
            setError("Invalid cancellation link")
            setIsLoading(false)
            return
        }

        const orgIdForCall = orgId
        const tokenForCall = token

        async function load() {
            try {
                const data = await getAppointmentForCancel(
                    orgIdForCall,
                    tokenForCall
                )
                setAppointment(data)
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : "Appointment not found")
            } finally {
                setIsLoading(false)
            }
        }
        load()
    }, [orgId, token])

    // Submit cancellation
    const handleSubmit = async () => {
        setIsSubmitting(true)
        try {
            if (!orgId || !token) throw new Error("Invalid cancellation link")
            await cancelByToken(orgId, token, reason || undefined)
            setIsConfirmed(true)
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to cancel")
        } finally {
            setIsSubmitting(false)
        }
    }

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // Error state
    if (error && !appointment) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Card className="max-w-md">
                    <CardContent className="pt-6 text-center">
                        <AlertCircleIcon className="size-12 mx-auto mb-4 text-destructive" />
                        <h2 className="text-xl font-semibold mb-2">Unable to Cancel</h2>
                        <p className="text-muted-foreground">{error}</p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    // Confirmed state
    if (isConfirmed) {
        return (
            <div className="min-h-screen bg-background py-12">
                <div className="max-w-lg mx-auto px-4">
                    <Card>
                        <CardContent className="pt-6 text-center">
                            <div className="size-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center mb-6">
                                <CheckCircleIcon className="size-8 text-green-600" />
                            </div>
                            <h2 className="text-2xl font-semibold mb-2">Appointment Cancelled</h2>
                            <p className="text-muted-foreground">
                                Your appointment has been cancelled. You will receive a confirmation email shortly.
                            </p>
                        </CardContent>
                    </Card>
                </div>
            </div>
        )
    }

    // Already cancelled
    if (appointment?.status === "cancelled") {
        return (
            <div className="min-h-screen bg-background py-12">
                <div className="max-w-lg mx-auto px-4">
                    <Card>
                        <CardContent className="pt-6 text-center">
                            <AlertCircleIcon className="size-12 mx-auto mb-4 text-muted-foreground" />
                            <h2 className="text-xl font-semibold mb-2">Already Cancelled</h2>
                            <p className="text-muted-foreground">This appointment has already been cancelled.</p>
                        </CardContent>
                    </Card>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-lg mx-auto px-4">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <AlertTriangleIcon className="size-5 text-destructive" />
                            Cancel Appointment
                        </CardTitle>
                        <CardDescription>
                            Are you sure you want to cancel this appointment?
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Appointment Details */}
                        {appointment && (
                            <div className="p-4 rounded-lg border border-border">
                                <h3 className="font-medium mb-3">{appointment.appointment_type_name}</h3>
                                {appointment.staff_name && (
                                    <p className="text-sm text-muted-foreground mb-2">
                                        with {appointment.staff_name}
                                    </p>
                                )}
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <CalendarIcon className="size-4" />
                                    {format(parseISO(appointment.scheduled_start), "EEEE, MMMM d, yyyy")}
                                </div>
                                <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                                    <ClockIcon className="size-4" />
                                    {format(parseISO(appointment.scheduled_start), "h:mm a")} ({appointment.duration_minutes} min)
                                </div>
                            </div>
                        )}

                        {/* Reason */}
                        <div className="space-y-2">
                            <Label htmlFor="reason">Reason for cancellation (optional)</Label>
                            <Textarea
                                id="reason"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="Let us know why you're cancelling..."
                                rows={3}
                            />
                        </div>

                        {/* Actions */}
                        <div className="flex gap-3">
                            <Button variant="outline" className="flex-1" onClick={() => window.history.back()}>
                                Go Back
                            </Button>
                            <Button
                                variant="destructive"
                                className="flex-1"
                                onClick={() => setShowConfirmDialog(true)}
                                disabled={isSubmitting}
                            >
                                Cancel Appointment
                            </Button>
                        </div>

                        {error && appointment && (
                            <p className="text-sm text-destructive text-center">{error}</p>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Confirmation Dialog */}
            <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Confirm Cancellation</AlertDialogTitle>
                        <AlertDialogDescription>
                            This action cannot be undone. Your appointment will be cancelled and the time slot will be released.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isSubmitting}>Keep Appointment</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleSubmit}
                            disabled={isSubmitting}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {isSubmitting && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                            Yes, Cancel It
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
