"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"
import { useForms, useSurrogateApplicationForms } from "@/lib/hooks/use-forms"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout/context"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"

export default function SurrogateApplicationPage() {
    const params = useParams<{ id?: string }>()
    const id = params?.id
    const { effectivePermissions, canEditSurrogate } = useSurrogateDetailData()
    const scoped = (effectivePermissions?.policy_version ?? 1) >= 2
    const permissions = effectivePermissions?.permissions ?? []
    const canView = !scoped || permissions.includes("view_form_submissions")
    const canEdit = !scoped || (canEditSurrogate && permissions.includes("review_form_submissions"))
    const canSend = !scoped || (canEditSurrogate && permissions.includes("send_email"))
    const legacyForms = useForms(!scoped)
    const scopedForms = useSurrogateApplicationForms(scoped && canView ? id ?? null : null)
    const formsQuery = scoped ? scopedForms : legacyForms
    const forms = formsQuery.data
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

    if (!canView) return <TabsContent value="application">Application unavailable</TabsContent>
    if (formsQuery.isLoading) return <TabsContent value="application"><Skeleton className="h-48" /></TabsContent>
    if (formsQuery.isError) return <TabsContent value="application"><div role="alert"><p>Unable to load application forms.</p><Button variant="outline" onClick={() => { void formsQuery.refetch() }}>Retry</Button></div></TabsContent>

    return (
        <TabsContent value="application" className="space-y-4">
            <SurrogateApplicationTab
                surrogateId={id}
                formId={defaultFormId}
                publishedForms={publishedForms}
                access={{ scoped, canEdit, canSend }}
            />
        </TabsContent>
    )
}
