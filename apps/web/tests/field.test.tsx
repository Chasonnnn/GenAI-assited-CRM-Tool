import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { FieldError } from "@/components/ui/field"

describe("FieldError", () => {
    it("deduplicates repeated error messages", () => {
        render(
            <FieldError
                errors={[
                    { message: "Email is required" },
                    { message: "Email is required" },
                    { message: "Phone is required" },
                ]}
            />,
        )

        expect(screen.getAllByText("Email is required")).toHaveLength(1)
        expect(screen.getByText("Phone is required")).toBeInTheDocument()
    })

    it("does not render without content or errors", () => {
        const { container } = render(<FieldError />)

        expect(container).toBeEmptyDOMElement()
    })
})
