/**
 * Appointments Page - /appointments
 * 
 * Staff-facing dashboard for:
 * - Pending approval queue
 * - Upcoming appointments
 * - Past appointments
 */

"use client"

import { useState } from "react"
import { AppointmentsList } from "@/components/appointments"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog"
import { LinkIcon, CopyIcon, CheckIcon, Loader2Icon } from "lucide-react"
import { useBookingLink } from "@/lib/hooks/use-appointments"

function BookingLinkButton() {
    const { data: link, isLoading } = useBookingLink()
    const [open, setOpen] = useState(false)
    const [copied, setCopied] = useState(false)

    const copyLink = () => {
        if (link?.full_url) {
            navigator.clipboard.writeText(link.full_url)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    if (isLoading) {
        return (
            <Button variant="outline" disabled>
                <Loader2Icon className="size-4 mr-2 animate-spin" />
                Loading...
            </Button>
        )
    }

    return (
        <>
            <Button variant="outline" onClick={() => setOpen(true)}>
                <LinkIcon className="size-4 mr-2" />
                Share Booking Link
            </Button>
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Your Booking Link</DialogTitle>
                        <DialogDescription>
                            Share this link with clients so they can book appointments with you.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex gap-2 mt-4">
                        <Input
                            readOnly
                            value={link?.full_url || ""}
                            className="font-mono text-sm"
                        />
                        <Button variant="outline" onClick={copyLink}>
                            {copied ? (
                                <CheckIcon className="size-4 text-green-500" />
                            ) : (
                                <CopyIcon className="size-4" />
                            )}
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                        Tip: Go to Settings → Appointments to manage your availability and appointment types.
                    </p>
                </DialogContent>
            </Dialog>
        </>
    )
}

export default function AppointmentsPage() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Appointments</h1>
                    <BookingLinkButton />
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-4">
                <AppointmentsList />
            </div>
        </div>
    )
}
