import type { ReactNode } from "react"

import "@/app/globals.css"

export const metadata = {
    title: "Application Form",
    description: "Submit your application",
}

export default function PublicFormLayout({ children }: { children: ReactNode }) {
    return <div className="min-h-screen bg-gradient-to-b from-white to-stone-50">{children}</div>
}
