import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AssistantRichText } from "@/components/ai/AssistantRichText"

describe("AssistantRichText", () => {
    it("renders common assistant Markdown and keeps unsafe links inert", async () => {
        const { container } = render(
            <AssistantRichText
                content={[
                    "Conversion is **0.5%**.",
                    "",
                    "### Funnel Actions",
                    "* **Data:** 6 contacted leads",
                    "* [Good link](https://example.com)",
                    "* [Bad link](javascript:alert(1))",
                    "<script>alert(1)</script>",
                ].join("\n")}
            />,
        )

        expect(await screen.findByText("0.5%", { selector: "strong" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 3, name: "Funnel Actions" })).toBeInTheDocument()
        expect(screen.getByText("Data:", { selector: "strong" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Good link" })).toHaveAttribute("href", "https://example.com")
        expect(screen.queryByRole("link", { name: "Bad link" })).not.toBeInTheDocument()
        expect(container.querySelector("script")).toBeNull()
    })
})
