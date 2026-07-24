import * as React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import OrganizationTemplateDetailPage from "@/app/(app)/automation/email-templates/org/[id]/page"
import NewOrganizationTemplatePage from "@/app/(app)/automation/email-templates/org/new/page"

vi.mock("@/components/email/organization-email-template-studio", () => ({
    default: ({ templateId }: { templateId?: string }) => (
        <div data-testid="organization-template-studio">
            {templateId ?? "new-template"}
        </div>
    ),
}))

describe("organization email template Studio routes", () => {
    it("renders the new-template Studio through a server page", () => {
        render(<NewOrganizationTemplatePage />)

        expect(screen.getByTestId("organization-template-studio")).toHaveTextContent(
            "new-template",
        )
    })

    it("awaits the dynamic route id and passes it to the Studio", async () => {
        const page = await OrganizationTemplateDetailPage({
            params: Promise.resolve({ id: "template-42" }),
        })
        render(page)

        expect(screen.getByTestId("organization-template-studio")).toHaveTextContent(
            "template-42",
        )
    })
})
