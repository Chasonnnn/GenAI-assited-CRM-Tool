import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { FormBuilderCanvasPreview } from "@/components/forms/builder/FormBuilderCanvasPreview"
import type { BuilderFormField, BuilderFormPage } from "@/lib/forms/form-builder-document"

vi.mock("next/image", () => ({
    default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) =>
        React.createElement("img", { alt, ...props }),
}))

function field(id: string, label: string, overrides: Partial<BuilderFormField> = {}): BuilderFormField {
    return {
        id,
        type: "text",
        label,
        helperText: "",
        required: false,
        surrogateFieldMapping: "",
        ...overrides,
    }
}

function renderPreview(pages: BuilderFormPage[]) {
    return render(
        <FormBuilderCanvasPreview
            pages={pages}
            publicEyebrow=""
            publicTitle="Surrogate application"
            publicSubtitle=""
            resolvedLogoUrl=""
            privacyNotice=""
            previewDevice="desktop"
            desktopWidthClass="max-w-6xl"
            mobileWidthClass="max-w-sm"
        />,
    )
}

describe("FormBuilderCanvasPreview", () => {
    it("stacks every page as a section like the hosted form", () => {
        renderPreview([
            { id: 1, name: "About You", fields: [field("full_name", "Full Name")] },
            { id: 2, name: "", fields: [field("notes", "Notes", { type: "textarea" })] },
        ])

        expect(screen.getByRole("region", { name: "About You" })).toContainElement(screen.getByLabelText("Full Name"))
        expect(screen.getByRole("region", { name: "Section 2" })).toContainElement(screen.getByLabelText("Notes"))
        expect(screen.getByLabelText("Full Name").closest(".min-w-0")).not.toHaveClass("sm:col-span-2")
        expect(screen.getByLabelText("Notes").closest(".min-w-0")).toHaveClass("sm:col-span-2")
        expect(screen.queryByRole("button", { name: "Previous" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /next|final page/i })).not.toBeInTheDocument()
    })

    it("omits pages whose fields are all hidden", () => {
        renderPreview([
            { id: 1, name: "About You", fields: [field("full_name", "Full Name")] },
            {
                id: 2,
                name: "Partner",
                fields: [
                    field("partner_name", "Partner Name", {
                        showIf: { fieldKey: "full_name", operator: "equals", value: "Partnered" },
                    }),
                ],
            },
        ])

        expect(screen.queryByRole("region", { name: "Partner" })).not.toBeInTheDocument()
    })

    it("shows an empty state without fields", () => {
        renderPreview([{ id: 1, name: "Page 1", fields: [] }])

        expect(screen.getByText("Nothing to preview yet")).toBeInTheDocument()
    })
})
