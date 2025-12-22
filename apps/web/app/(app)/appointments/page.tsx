/**
 * Appointments Page - /appointments
 * 
 * Staff-facing dashboard for:
 * - Pending approval queue
 * - Upcoming appointments
 * - Past appointments
 */

import { AppointmentsList } from "@/components/appointments"

export const metadata = {
    title: "Appointments | CRM",
    description: "Manage your appointment requests and schedule",
}

export default function AppointmentsPage() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center px-6">
                    <h1 className="text-2xl font-semibold">Appointments</h1>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6">
                <p className="text-sm text-muted-foreground">
                    Review pending requests and manage your upcoming appointments.
                </p>
                <AppointmentsList />
            </div>
        </div>
    )
}

