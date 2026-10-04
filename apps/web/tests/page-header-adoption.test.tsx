import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { AutomationPageHeader } from "../app/(app)/automation/components/automation-page-header"
import { EmailTemplatesPageHeader } from "@/components/email/EmailTemplatesPageHeader"

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}))

const PAGE_HEADER_IMPORT = /import \{ PageHeader \} from ["']@\/components\/page-header["']/

function readWebSource(path: string): string {
    return readFileSync(join(process.cwd(), path), "utf8")
}

// Sidebar destinations: no back arrow, title equals the nav label.
const TOP_LEVEL_PAGES = [
    "app/(app)/automation/campaigns/page.tsx",
    "app/(app)/automation/forms/page.tsx",
    "app/(app)/automation/executions/page.tsx",
    "app/(app)/automation/ai-builder/page.client.tsx",
    "app/(app)/ai-studio/page.tsx",
    "app/(app)/ai-assistant/page.tsx",
    "app/(app)/settings/appointments/page.tsx",
    "app/(app)/settings/integrations/page.tsx",
    "app/(app)/dashboard/page.client.tsx",
    "app/(app)/reports/page.tsx",
    "app/(app)/tickets/page.tsx",
    "app/(app)/search/page.tsx",
    "app/(app)/notifications/page.tsx",
]

// Integration subpages: PageHeader with a leading back button.
const INTEGRATION_SUBPAGES = [
    "components/email-operations/EmailOperationsDashboard.tsx",
    "app/(app)/settings/integrations/messaging/page.client.tsx",
    "app/(app)/settings/integrations/meta/page.client.tsx",
    "app/(app)/settings/integrations/meta/forms/page.tsx",
    "app/(app)/settings/integrations/meta/forms/[id]/page.tsx",
    "app/(app)/settings/integrations/zoom/page.tsx",
]

describe("PageHeader adoption", () => {
    it.each(TOP_LEVEL_PAGES)("%s uses PageHeader without a hand-rolled h1 or back arrow", (path) => {
        const source = readWebSource(path)
        expect(source).toMatch(PAGE_HEADER_IMPORT)
        expect(source).not.toMatch(/<h1[\s>]/)
        expect(source).not.toContain("ArrowLeftIcon")
    })

    it.each(INTEGRATION_SUBPAGES)("%s uses PageHeader with a back button", (path) => {
        const source = readWebSource(path)
        expect(source).toMatch(PAGE_HEADER_IMPORT)
        expect(source).toMatch(/back=\{\{ href: "\/settings\/integrations/)
        expect(source).not.toMatch(/<h1[\s>]/)
        expect(source).not.toContain("ArrowLeftIcon")
    })

    it("renders the Workflows header through PageHeader with tab-specific actions", () => {
        const { rerender } = render(
            <AutomationPageHeader activeTab="workflows" onOpenExecutions={vi.fn()} onCreateTemplate={vi.fn()} />
        )
        const heading = screen.getByRole("heading", { level: 1, name: "Workflows" })
        expect(heading.closest('[data-slot="page-header"]')).not.toBeNull()
        expect(screen.getByRole("button", { name: "Execution History" })).toBeInTheDocument()

        rerender(<AutomationPageHeader activeTab="templates" onOpenExecutions={vi.fn()} onCreateTemplate={vi.fn()} />)
        expect(document.querySelector('[data-slot="page-header-actions"]')).toBeNull()
    })

    it("renders the Email Templates header through PageHeader", () => {
        render(
            <EmailTemplatesPageHeader
                activeTab="org"
                canUseAI={false}
                canManageEmailTemplates
                canCreatePersonal
                onCreatePersonal={vi.fn()}
                onCreateOrganization={vi.fn()}
            />
        )
        const heading = screen.getByRole("heading", { level: 1, name: "Email Templates" })
        expect(heading.closest('[data-slot="page-header"]')).not.toBeNull()
        expect(screen.getByRole("button", { name: "Create Org Template" })).toBeInTheDocument()
    })
})
