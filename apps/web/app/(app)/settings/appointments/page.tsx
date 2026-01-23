/**
 * Appointment Settings Page - /settings/appointments
 * 
 * Staff-facing settings for:
 * - Availability configuration
 * - Appointment types
 * - Booking link management
 */

import { AppointmentSettings } from "@/components/appointments/AppointmentSettings"

export const metadata = {
    title: "Appointment Settings | Surrogacy Force",
    description: "Configure your availability and appointment types",
}

export default function AppointmentSettingsPage() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center px-6">
                    <h1 className="text-2xl font-semibold">Appointment Settings</h1>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6">
                <p className="text-sm text-muted-foreground">
                    Configure your availability, appointment types, and booking link.
                </p>
                <AppointmentSettings />
            </div>
        </div>
    )
}
