"use client"

import { LoadErrorState } from "@/components/error-state"
import { AutomationFormBuilderScreen } from "@/components/forms/builder/AutomationFormBuilderScreen"
import {
    FormBuilderBlockedScreen,
    FormBuilderDeniedScreen,
    FormBuilderLoadingState,
} from "@/components/forms/builder/FormBuilderAccessStates"
import { useAutomationFormBuilderPage } from "@/lib/forms/use-automation-form-builder-page"
import type { WorkspaceTab } from "@/lib/forms/form-builder-workspace-tab"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"

function AutomationFormBuilder({ initialTab }: { initialTab?: WorkspaceTab | undefined }) {
    const controller = useAutomationFormBuilderPage(initialTab ? { initialTab } : {})
    return <AutomationFormBuilderScreen controller={controller} />
}

type FormBuilderPageProps = {
    /** Workspace tab from the `tab` query parameter. */
    initialTab?: WorkspaceTab | undefined
}

export default function FormBuilderPage({ initialTab }: FormBuilderPageProps = {}) {
    const permissionCheck = usePermissionCheck()

    if (permissionCheck.isLoading) {
        return <FormBuilderLoadingState label="Loading form…" />
    }
    if (permissionCheck.isError) {
        return (
            <FormBuilderBlockedScreen>
                <LoadErrorState
                    title="Couldn't load form"
                    onRetry={permissionCheck.retry}
                    isRetrying={permissionCheck.isRetrying}
                    headingLevel={2}
                />
            </FormBuilderBlockedScreen>
        )
    }
    // Every /forms route requires manage_forms. The builder mounts only when allowed,
    // so denied roles send no form, mapping, intake-link or submission requests.
    if (!permissionCheck.can("manage_forms")) {
        return <FormBuilderDeniedScreen />
    }

    return <AutomationFormBuilder initialTab={initialTab} />
}
