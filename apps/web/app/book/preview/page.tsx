/**
 * Booking Page Preview - /book/preview
 *
 * Authenticated preview of the public booking page.
 */

import { Metadata } from "next"
import { PublicBookingPage } from "@/components/appointments/PublicBookingPage"

export const metadata: Metadata = {
    title: "Booking Page Preview",
    description: "Preview the booking page before sharing",
    robots: {
        index: false,
        follow: false,
    },
}

export default function BookingPreviewPage() {
    return <PublicBookingPage publicSlug="preview" preview />
}
