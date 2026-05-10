import type { Metadata } from "next"
import { redirect } from "next/navigation"

export const metadata: Metadata = {
    title: "SurrogacyForce",
    description: "SurrogacyForce CRM for surrogacy agency operations.",
}

export default function RootPage(): never {
    redirect("/dashboard")
}
