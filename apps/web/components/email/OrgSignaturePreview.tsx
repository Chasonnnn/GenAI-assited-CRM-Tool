import { ImageIcon, Loader2Icon } from "lucide-react"

import { SafeHtmlContent } from "@/components/safe-html-content"
import { useOrgSignaturePreview } from "@/lib/hooks/use-signature"

export function OrgSignaturePreview() {
    const { data: preview, isLoading } = useOrgSignaturePreview({ enabled: true, mode: "org_only" })

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }
    if (!preview?.html) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center">
                <ImageIcon className="size-10 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">No organization signature configured yet</p>
            </div>
        )
    }
    return <SafeHtmlContent html={preview.html} className="prose prose-sm prose-stone max-w-none text-stone-900" />
}
