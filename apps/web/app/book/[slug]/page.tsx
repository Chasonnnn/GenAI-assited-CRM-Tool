/**
 * Public Booking Page - /book/[slug]
 * 
 * Public-facing page for clients to book appointments.
 * This page is NOT behind authentication.
 */

import { Metadata } from "next"
import { PublicBookingPage } from "@/components/appointments/PublicBookingPage"

interface PageProps {
    params: Promise<{ slug?: string | string[] }>
}

export const metadata: Metadata = {
    title: "Book an Appointment",
    description: "Schedule an appointment with us",
    robots: {
        index: false,
        follow: false,
    },
}

export default async function BookingPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawSlug = resolvedParams.slug
    const slug = Array.isArray(rawSlug) ? rawSlug[0] : rawSlug

    // Should not happen, but avoid rendering with an undefined slug.
    if (!slug) {
        return null
    }

    return <PublicBookingPage publicSlug={slug} />
}
