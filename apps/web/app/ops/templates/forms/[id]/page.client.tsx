"use client"

import { TemplateFormBuilderScreen } from "@/components/forms/builder/TemplateFormBuilderScreen"
import { useTemplateFormBuilderPage } from "@/lib/forms/use-template-form-builder-page"

export default function FormBuilderPage() {
    const controller = useTemplateFormBuilderPage()
    return <TemplateFormBuilderScreen controller={controller} />
}
