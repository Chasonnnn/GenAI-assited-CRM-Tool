import { Suspense } from "react"

import MessageTemplateEditorPageClient from "./page.client"

export default function MessageTemplateEditorPage() {
    return (
        <Suspense fallback={<div className="p-6"><div className="h-96 rounded-lg border bg-card" /></div>}>
            <MessageTemplateEditorPageClient />
        </Suspense>
    )
}
