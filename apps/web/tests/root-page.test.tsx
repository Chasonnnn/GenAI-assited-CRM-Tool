import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { describe, expect, it } from "vitest"

import RootPage, { metadata } from "../app/page"

describe("RootPage", () => {
    it("renders a public homepage for OAuth review", () => {
        render(<RootPage />)

        expect(
            screen.getByRole("heading", { name: "Surrogacy Force" }),
        ).toBeInTheDocument()
        expect(screen.getByText("Run every journey from one trusted workspace.")).toBeInTheDocument()
        expect(
            screen.getByText(/A private CRM for surrogacy teams to manage intake/i),
        ).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login")
        expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy")
        expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms")
    })

    it("allows indexing for the public homepage", () => {
        expect(metadata).toMatchObject({
            title: "Surrogacy Force | Private CRM for surrogacy teams",
            robots: {
                index: true,
                follow: true,
            },
        })
    })
})
