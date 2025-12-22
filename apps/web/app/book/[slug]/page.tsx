/**
 * Public Booking Page - /book/[slug]
 * 
 * Public-facing page for clients to book appointments.
 * This page is NOT behind authentication.
 */

import { Metadata } from "next"
import { PublicBookingPage } from "@/components/appointments"

interface PageProps {
    params: {
        slug: string
    }
}

export const metadata: Metadata = {
    title: "Book an Appointment",
    description: "Schedule an appointment with us",
    robots: {
        index: false,
        follow: false,
    },
}

export default function BookingPage({ params }: PageProps) {
    return <PublicBookingPage publicSlug={params.slug} />
}
