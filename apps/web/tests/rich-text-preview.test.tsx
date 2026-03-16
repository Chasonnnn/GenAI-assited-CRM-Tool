import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { RichTextPreview } from "@/components/rich-text-preview"

describe("RichTextPreview", () => {
    it("renders sanitized rich text content without injecting scripts", async () => {
        render(
            <RichTextPreview
                html={`<p>Hello <strong>there</strong> <a href="https://example.com">friend</a></p><script>alert("xss")</script>`}
            />,
        )

        const link = await screen.findByRole("link", { name: "friend" })

        expect(link.closest("p")).toHaveTextContent("Hello there friend")
        expect(link).toHaveAttribute(
            "href",
            "https://example.com",
        )
        expect(screen.queryByText('alert("xss")')).not.toBeInTheDocument()
    })
})
