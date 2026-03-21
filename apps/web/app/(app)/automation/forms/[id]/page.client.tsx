"use client"

import { AutomationFormBuilderScreen } from "@/components/forms/builder/AutomationFormBuilderScreen"
import { useAutomationFormBuilderPage } from "@/lib/forms/use-automation-form-builder-page"

export default function FormBuilderPage() {
    const controller = useAutomationFormBuilderPage()
    return <AutomationFormBuilderScreen controller={controller} />
}
