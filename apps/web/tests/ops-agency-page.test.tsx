import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { AgencyTemplatesTab } from "../components/ops/agencies/AgencyTemplatesTab"

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: () => <div data-testid="rich-text-editor" />,
}))

describe("AgencyTemplatesTab", () => {
    it("renders the invite email HTML editor", () => {
        render(
            <AgencyTemplatesTab
                orgName="Test Org"
                orgSlug="test-org"
                portalBaseUrl="https://app.example.com"
                platformEmailStatus={null}
                platformEmailLoading={false}
                inviteTemplate={null}
                inviteTemplateLoading={false}
                templateFromEmail=""
                templateSubject="Invitation to join {{org_name}}"
                templateBody="<p>Hello</p>"
                templateActive={true}
                templateVersion={1}
                onTemplateFromEmailChange={() => {}}
                onTemplateSubjectChange={() => {}}
                onTemplateBodyChange={() => {}}
                onTemplateActiveChange={() => {}}
                onSaveTemplate={() => {}}
                inviteTemplateSaving={false}
                testEmail=""
                onTestEmailChange={() => {}}
                onSendTestEmail={() => {}}
                testSending={false}
            />
        )

        expect(screen.getByText("Email Body")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /use apple-style layout/i })).toBeInTheDocument()
    })
})
