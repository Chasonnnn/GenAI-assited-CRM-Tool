/**
 * Scheduling Settings Page - /settings/appointments
 *
 * Staff-facing settings for:
 * - Availability configuration
 * - Appointment types
 * - Booking link management
 */

import { Suspense } from "react"

import { AppointmentSettings } from "@/components/appointments/AppointmentSettings"
import { PageHeader } from "@/components/page-header"

export const metadata = {
    title: "Scheduling Settings | Surrogacy Force",
    description: "Configure your availability and appointment types",
}

export default function AppointmentSettingsPage() {
    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader title="Scheduling Settings" />
            <div className="flex-1 p-6 space-y-6">
                {/* The settings tabs read the URL through useSearchParams. */}
                <Suspense fallback={null}>
                    <AppointmentSettings />
                </Suspense>
            </div>
        </div>
    )
}
