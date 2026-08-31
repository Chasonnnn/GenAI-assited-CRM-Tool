import { Loader2Icon } from "lucide-react"

import { cn } from "@/lib/utils"
import { publicFormPageClassName } from "./public-form-styles"

export function PublicFormLoadingState() {
    return (
        <div className={cn(publicFormPageClassName, "flex items-center justify-center p-4")}>
            <div className="text-center">
                <Loader2Icon className="size-10 animate-spin text-primary mx-auto mb-4" />
                <p className="text-stone-600">Loading application form…</p>
            </div>
        </div>
    )
}
