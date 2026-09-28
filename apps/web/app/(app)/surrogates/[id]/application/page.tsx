"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import {
    SurrogateApplicationTab,
    type ApplicationFormsAccess,
} from "@/components/surrogates/SurrogateApplicationTab"
import { useForms, useSurrogateApplicationForms } from "@/lib/hooks/use-forms"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout/context"
import { PermissionDeniedState } from "@/components/error-state"
import { Skeleton } from "@/components/ui/skeleton"
import { isPermissionError } from "@/lib/error-utils"

export default function SurrogateApplicationPage() {
    const params = useParams<{ id?: string }>()
    const id = params?.id
    const { effectivePermissions, canEditSurrogate } = useSurrogateDetailData()
    const scoped = (effectivePermissions?.policy_version ?? 1) >= 2
    const permissions = effectivePermissions?.permissions ?? []
    const canView = !scoped || permissions.includes("view_form_submissions")
    const canEdit = !scoped || (canEditSurrogate && permissions.includes("review_form_submissions"))
    const canSend = !scoped || (canEditSurrogate && permissions.includes("send_email"))
    const legacyForms = useForms({ enabled: !scoped })
    const scopedForms = useSurrogateApplicationForms(scoped && canView ? id ?? null : null)
    const formsQuery = scoped ? scopedForms : legacyForms
    const forms = formsQuery.data
    // A failed forms list does not hide the tab. Under policy v1 only roles with manage_forms can
    // list forms, so other roles get a 403 here; the tab shows that state in place of the send-link form.
    const formsAccess: ApplicationFormsAccess = !formsQuery.isError
        ? "ready"
        : isPermissionError(formsQuery.error)
            ? "forbidden"
            : "error"
    const publishedForms = (forms || []).filter((form) => form.status === "published")
    const defaultApplicationForm =
        publishedForms.find(
            (form) =>
                form.is_default_surrogate_application &&
                (form.purpose ?? "surrogate_application") === "surrogate_application",
        ) ??
        publishedForms.find((form) => (form.purpose ?? "surrogate_application") === "surrogate_application") ??
        null
    const defaultFormId = defaultApplicationForm?.id ?? null

    if (!id) {
        return null
    }

    if (!canView) {
        return (
            <TabsContent value="application">
                <PermissionDeniedState
                    title="No access to application"
                    description="Ask an admin to update your role."
                    secondaryHref={`/surrogates/${id}`}
                    secondaryLabel="Back to Overview"
                    headingLevel={2}
                />
            </TabsContent>
        )
    }

    if (formsQuery.isLoading) {
        return (
            <TabsContent value="application">
                <Skeleton className="h-48" />
            </TabsContent>
        )
    }

    return (
        <TabsContent value="application" className="space-y-4">
            <SurrogateApplicationTab
                surrogateId={id}
                formId={defaultFormId}
                publishedForms={publishedForms}
                formsAccess={formsAccess}
                onRetryForms={() => void formsQuery.refetch()}
                access={{ scoped, canEdit, canSend }}
            />
        </TabsContent>
    )
}
