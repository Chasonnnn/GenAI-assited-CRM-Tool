import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { SafeHtmlContent, TrustedSanitizedHtmlContent } from "@/components/safe-html-content"

describe("safe HTML rendering", () => {
    it("sanitizes untrusted HTML before parsing it into React nodes", async () => {
        const { container } = render(
            <SafeHtmlContent html={'<img src=x onerror="alert(1)"><p>Safe content</p>'} />,
        )

        expect(await screen.findByText("Safe content")).toBeInTheDocument()
        expect(container.querySelector("img")).toBeNull()
        expect(container.querySelector("[onerror]")).toBeNull()
    })

    it("renders already-sanitized rich preview HTML without using a raw HTML sink", async () => {
        render(
            <TrustedSanitizedHtmlContent
                html={'<p style="color: red" data-preview-id="sample">Styled preview</p>'}
            />,
        )

        const preview = await screen.findByText("Styled preview")
        expect(preview).toHaveStyle({ color: "rgb(255, 0, 0)" })
        expect(preview).toHaveAttribute("data-preview-id", "sample")
    })
})
