import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { describe, expect, it } from "vitest"

import TermsPage, { metadata } from "../app/terms/page"

describe("TermsPage", () => {
    it("publishes public terms of service", () => {
        render(<TermsPage />)

        expect(screen.getByRole("heading", { name: "Terms of Service" })).toBeInTheDocument()
        expect(screen.getByText("Last updated: May 22, 2026")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Use of the service" })).toBeInTheDocument()
        expect(
            screen.getByRole("heading", { name: "Third-party integrations" })
        ).toBeInTheDocument()
        expect(screen.getByRole("link", { name: /privacy policy/i })).toHaveAttribute(
            "href",
            "/privacy"
        )
    })

    it("allows indexing for OAuth review", () => {
        expect(metadata).toMatchObject({
            title: "Terms of Service | Surrogacy Force",
            robots: {
                index: true,
                follow: true,
            },
        })
    })
})
