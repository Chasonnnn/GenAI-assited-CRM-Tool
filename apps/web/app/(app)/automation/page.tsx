import AutomationPageClient from "./page.client"

type AutomationTab = "workflows" | "email-templates" | "campaigns"
type AutomationWorkflowScopeTab = "personal" | "org" | "templates"

type PageProps = {
    searchParams: Promise<Record<string, string | string[] | undefined>>
}

function firstSearchParam(value: string | string[] | undefined): string | undefined {
    return Array.isArray(value) ? value[0] : value
}

function normalizeAutomationTab(value: string | undefined): AutomationTab {
    return value === "email-templates" || value === "campaigns" ? value : "workflows"
}

function normalizeWorkflowScopeTab(value: string | undefined): AutomationWorkflowScopeTab {
    return value === "org" || value === "templates" ? value : "personal"
}

export default async function AutomationPage({ searchParams }: PageProps) {
    const resolvedSearchParams = await searchParams
    const tabParam = firstSearchParam(resolvedSearchParams.tab)
    const scopeParam = firstSearchParam(resolvedSearchParams.scope)
    const createParam = firstSearchParam(resolvedSearchParams.create)

    return (
        <AutomationPageClient
            initialTab={normalizeAutomationTab(tabParam)}
            initialWorkflowScopeTab={normalizeWorkflowScopeTab(scopeParam)}
            initialCreateOpen={createParam === "true"}
        />
    )
}
