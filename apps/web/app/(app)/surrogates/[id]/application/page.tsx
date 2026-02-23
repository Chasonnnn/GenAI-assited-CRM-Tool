"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"
import { useForms } from "@/lib/hooks/use-forms"

export default function SurrogateApplicationPage() {
    const params = useParams<{ id?: string }>()
    const id = params?.id
    const { data: forms } = useForms()
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

    return (
        <TabsContent value="application" className="space-y-4">
            <SurrogateApplicationTab
                surrogateId={id}
                formId={defaultFormId}
                publishedForms={publishedForms}
            />
        </TabsContent>
    )
}
