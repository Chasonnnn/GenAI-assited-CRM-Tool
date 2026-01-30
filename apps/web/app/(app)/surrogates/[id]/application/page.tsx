"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"
import { useForms } from "@/lib/hooks/use-forms"

export default function SurrogateApplicationPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { data: forms } = useForms()
    const defaultFormId = forms?.find((form) => form.status === "published")?.id || ""

    return (
        <TabsContent value="application" className="space-y-4">
            <SurrogateApplicationTab surrogateId={id} formId={defaultFormId} />
        </TabsContent>
    )
}
