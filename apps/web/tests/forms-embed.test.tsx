import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import EmbedFormPageClient from "../app/embed/forms/[slug]/page.client"

const {
    createEmbedFormSession,
    getEmbedPublicForm,
    submitEmbedPublicForm,
} = vi.hoisted(() => ({
    createEmbedFormSession: vi.fn(),
    getEmbedPublicForm: vi.fn(),
    submitEmbedPublicForm: vi.fn(),
}))

vi.mock("@/lib/api/forms", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/forms")>("@/lib/api/forms")
    return {
        ...actual,
        createEmbedFormSession,
        getEmbedPublicForm,
        submitEmbedPublicForm,
    }
})

const embedForm = {
    form_id: "form-1",
    intake_link_id: "link-1",
    published_version_id: "version-1",
    name: "Lead Capture",
    description: "Request a callback",
    form_schema: {
        pages: [
            {
                title: "Contact",
                fields: [
                    {
                        key: "full_name",
                        label: "Full Name",
                        type: "text",
                        required: true,
                        sensitivity: "identity",
                    },
                    {
                        key: "email",
                        label: "Email",
                        type: "email",
                        required: true,
                        sensitivity: "contact",
                    },
                ],
            },
        ],
        public_title: "Become a Surrogate",
        privacy_notice: null,
    },
    max_file_size_bytes: 10 * 1024 * 1024,
    max_file_count: 0,
    allowed_mime_types: [],
    campaign_name: "Spring",
    event_name: null,
    tracking_mode: "enhanced_match_lead",
    consent: {
        text: "I agree to be contacted.",
        privacy_policy_url: "https://www.ewisurrogacy.com/privacy",
    },
    thank_you_config: {},
    embed_theme_json: {},
}

describe("EmbedFormPageClient", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.history.replaceState(null, "", "?parent_origin=https%3A%2F%2Fwww.ewisurrogacy.com")
        getEmbedPublicForm.mockResolvedValue(embedForm)
        createEmbedFormSession.mockResolvedValue({
            session_token: "embed-session-token",
            expires_at: new Date(Date.now() + 60_000).toISOString(),
        })
        submitEmbedPublicForm.mockResolvedValue({
            id: "submission-1",
            status: "pending_review",
            outcome: "lead_created",
            surrogate_id: null,
            intake_lead_id: "lead-1",
        })
    })

    it("loads via parent origin, creates a sanitized embed session, and submits lead answers", async () => {
        render(<EmbedFormPageClient slug="lead-form" initialParentOrigin="https://www.ewisurrogacy.com" />)

        await waitFor(() => {
            expect(getEmbedPublicForm).toHaveBeenCalled()
        })
        expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
        expect(getEmbedPublicForm).toHaveBeenCalledWith("lead-form", "https://www.ewisurrogacy.com")
        expect(screen.getByRole("main")).toHaveClass("max-w-[760px]", "py-4")
        expect(screen.getByLabelText(/full name/i)).toHaveClass("h-10")

        window.dispatchEvent(
            new MessageEvent("message", {
                origin: "https://www.ewisurrogacy.com",
                data: {
                    type: "sf:form:init",
                    attribution: {
                        utm_source: "meta",
                        medical_notes: "should not pass through",
                    },
                },
            }),
        )

        await waitFor(() => {
            expect(createEmbedFormSession).toHaveBeenCalledWith(
                "lead-form",
                "https://www.ewisurrogacy.com",
                { utm_source: "meta" },
            )
        })

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: "Embed Lead" },
        })
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: "embed@example.com" },
        })
        fireEvent.click(screen.getByRole("checkbox"))
        fireEvent.click(screen.getByRole("button", { name: /submit/i }))

        await waitFor(() => {
            expect(submitEmbedPublicForm).toHaveBeenCalledWith(
                "lead-form",
                expect.objectContaining({
                    embed_session_token: "embed-session-token",
                    published_version_id: "version-1",
                    answers: {
                        full_name: "Embed Lead",
                        email: "embed@example.com",
                    },
                    consent: { accepted: true },
                }),
            )
        })
        expect(await screen.findByRole("heading", { name: "Request received" })).toBeInTheDocument()
    })

    it("does not create duplicate embed sessions when the parent sends init more than once", async () => {
        render(<EmbedFormPageClient slug="lead-form" initialParentOrigin="https://www.ewisurrogacy.com" />)

        expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()

        const initMessage = new MessageEvent("message", {
            origin: "https://www.ewisurrogacy.com",
            data: {
                type: "sf:form:init",
                attribution: {
                    utm_source: "meta",
                },
            },
        })

        window.dispatchEvent(initMessage)
        await waitFor(() => {
            expect(createEmbedFormSession).toHaveBeenCalledTimes(1)
        })

        window.dispatchEvent(initMessage)
        await new Promise((resolve) => window.setTimeout(resolve, 0))

        expect(createEmbedFormSession).toHaveBeenCalledTimes(1)
    })
})
