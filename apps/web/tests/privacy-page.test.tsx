import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { describe, expect, it } from "vitest"

import PrivacyPage, { metadata } from "../app/privacy/page"

describe("PrivacyPage", () => {
    it("publishes the Google-ready privacy disclosures", () => {
        render(<PrivacyPage />)

        expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument()
        expect(screen.getByText("Last updated: May 22, 2026")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Google user data" })).toBeInTheDocument()
        expect(
            screen.getByText(/Surrogacy Force does not sell Google user data/i)
        ).toBeInTheDocument()
        expect(
            screen.getByText(/does not use Google Workspace API data to train/i)
        ).toBeInTheDocument()
        expect(screen.getByText(/including the Limited Use requirements/i)).toBeInTheDocument()
        expect(
            screen.getByText(/disconnect Google integrations in Surrogacy Force/i)
        ).toBeInTheDocument()
        expect(screen.getByRole("link", { name: /terms of service/i })).toHaveAttribute(
            "href",
            "/terms"
        )
    })

    it("allows indexing for OAuth review", () => {
        expect(metadata).toMatchObject({
            title: "Privacy Policy | Surrogacy Force",
            robots: {
                index: true,
                follow: true,
            },
        })
    })
})
