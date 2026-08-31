import { CheckCircle2Icon } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import type { FormSubmissionSharedResponse } from "@/lib/api/forms"
import { cn } from "@/lib/utils"
import { publicFormCardClassName, publicFormPageClassName } from "./public-form-styles"

export function PublicFormSuccessState({
    outcome,
}: {
    outcome: FormSubmissionSharedResponse["outcome"] | null
}) {
    const outcomeMessage =
        outcome === "linked"
            ? "Your application is in review. A coordinator will follow up shortly."
            : outcome === "ambiguous_review"
                ? "Your application is received and queued for verification. Our intake team will contact you soon."
                : "Your application has been received and added to intake review. A coordinator will reach out soon."

    return (
        <div className={cn(publicFormPageClassName, "flex items-center justify-center p-4")}>
            <Card className={cn(publicFormCardClassName, "w-full max-w-md")}>
                <CardContent className="px-6 py-10 text-center">
                    <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-full bg-emerald-50">
                        <CheckCircle2Icon className="size-10 text-emerald-600" />
                    </div>
                    <h1 className="text-2xl font-semibold text-stone-900 mb-3">Application Submitted!</h1>
                    <p className="text-stone-600 leading-relaxed">{outcomeMessage}</p>
                </CardContent>
            </Card>
        </div>
    )
}
