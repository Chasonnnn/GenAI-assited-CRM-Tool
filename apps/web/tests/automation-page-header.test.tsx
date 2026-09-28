import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AutomationPageHeader } from "../app/(app)/automation/components/automation-page-header"

describe("AutomationPageHeader", () => {
    it("hides Execution History for viewers who cannot view executions", () => {
        render(
            <AutomationPageHeader
                activeTab="workflows"
                onOpenExecutions={vi.fn()}
                onCreateTemplate={vi.fn()}
                canViewExecutions={false}
            />,
        )

        expect(screen.queryByRole("button", { name: "Execution History" })).not.toBeInTheDocument()
        expect(document.querySelector('[data-slot="page-header-actions"]')).toBeNull()
    })

    it("puts the Workflow Templates tab's Create Workflow action in the page header", () => {
        const onCreateWorkflow = vi.fn()
        render(
            <AutomationPageHeader
                activeTab="workflows"
                onOpenExecutions={vi.fn()}
                onCreateTemplate={vi.fn()}
                canViewExecutions={false}
                onCreateWorkflow={onCreateWorkflow}
            />,
        )

        fireEvent.click(screen.getByRole("button", { name: "Create Workflow" }))
        expect(onCreateWorkflow).toHaveBeenCalledOnce()
        expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1)
    })
})
