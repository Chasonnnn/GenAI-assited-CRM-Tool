import type { Metadata } from "next"
import { notFound } from "next/navigation"
import DonorIntakePreview from "./preview"

export const dynamic = "force-dynamic"
export const metadata: Metadata = {
    title: "EWI donor form — local preview",
    robots: { index: false, follow: false },
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
    if (process.env.NODE_ENV !== "development"
        || process.env.NEXT_PUBLIC_API_BASE_URL !== "http://127.0.0.1:8027") notFound()
    const { slug } = await params
    return <DonorIntakePreview slug={slug} />
}
