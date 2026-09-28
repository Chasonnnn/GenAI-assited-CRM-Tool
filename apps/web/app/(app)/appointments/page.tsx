"use client"

import { useRef, useState } from "react"
import { LinkIcon, Loader2Icon, SettingsIcon } from "lucide-react"

import Link from "@/components/app-link"
import { AppointmentsList } from "@/components/appointments/AppointmentsList"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { CopyField } from "@/components/ui/copy-field"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { useBookingLink } from "@/lib/hooks/use-appointments"

function BookingLinkButton() {
    const { data: link, isLoading, isError, refetch } = useBookingLink()
    const [open, setOpen] = useState(false)
    const fieldRef = useRef<HTMLDivElement>(null)

    if (isLoading) {
        return (
            <Button variant="outline" disabled>
                <Loader2Icon className="size-4 mr-2 animate-spin" />
                Loading&hellip;
            </Button>
        )
    }

    if (isError) {
        return (
            <div className="flex items-center gap-3">
                <span className="text-sm text-destructive">Unable to load booking link</span>
                <Button variant="outline" size="sm" onClick={() => refetch()}>
                    Retry
                </Button>
            </div>
        )
    }

    return (
        <>
            <Button variant="outline" onClick={() => setOpen(true)}>
                <LinkIcon className="size-4 mr-2" aria-hidden="true" />
                Share booking link
            </Button>
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent
                    size="lg"
                    // Focus the copy button, not the URL field, so opening the dialog does not
                    // select or scroll the link.
                    initialFocus={() => fieldRef.current?.querySelector<HTMLElement>("button:not(:disabled)") ?? true}
                >
                    <DialogHeader>
                        <DialogTitle>Your Booking Link</DialogTitle>
                    </DialogHeader>
                    <div ref={fieldRef}>
                        <CopyField
                            aria-label="Booking link"
                            value={link?.full_url ?? ""}
                            copyLabel="Copy booking link"
                        />
                    </div>
                    <DialogFooter className="sm:justify-start">
                        <Button variant="ghost" render={<Link href="/settings/appointments" />}>
                            <SettingsIcon className="size-4" aria-hidden="true" />
                            Scheduling settings
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}

export default function AppointmentsPage() {
    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader title="Appointments" actions={<BookingLinkButton />} />
            <AppointmentsList />
        </div>
    )
}
