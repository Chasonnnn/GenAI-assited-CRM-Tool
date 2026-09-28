import { render, screen } from "@testing-library/react"
import type { ComponentProps } from "react"
import { describe, expect, it, vi } from "vitest"

import { FormBuilderHeader } from "@/components/forms/builder/FormBuilderHeader"

const reason = "To publish, add Full Name, Email."

function renderHeader(props: Partial<ComponentProps<typeof FormBuilderHeader>> = {}) {
    return render(
        <FormBuilderHeader
            backAriaLabel="Back to forms"
            formName="Intake"
            publicationStatus="unpublished_changes"
            isPublishing={false}
            isSaving={false}
            autoSaveLabel={null}
            onBack={vi.fn()}
            onFormNameChange={vi.fn()}
            onSave={vi.fn()}
            onPublish={vi.fn()}
            {...props}
        />,
    )
}

describe("FormBuilderHeader", () => {
    it("keeps the readiness reason on Publish while a save is pending", () => {
        renderHeader({ saveDisabled: true, publishDisabled: true, publishDisabledReason: reason })

        const publish = screen.getByRole("button", { name: /^publish$/i })
        expect(publish).toHaveAttribute("aria-disabled", "true")
        expect(publish).toHaveAccessibleDescription(reason)
        expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled()
    })

    it("disables Publish without a reason when a published form has nothing new", () => {
        renderHeader({ publicationStatus: "published", publishDisabled: true, publishDisabledReason: reason })

        const publish = screen.getByRole("button", { name: /^publish$/i })
        expect(publish).toBeDisabled()
        expect(publish).not.toHaveAccessibleDescription()
    })
})
