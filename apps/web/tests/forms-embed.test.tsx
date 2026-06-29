import React from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
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
        privacy_notice: "By submitting, you agree to be contacted by the intake team.",
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

let addEventListenerSpy: ReturnType<typeof vi.spyOn> | null = null

async function waitForEmbedMessageListener() {
    await waitFor(() => {
        expect(addEventListenerSpy?.mock.calls.some(([eventName]) => eventName === "message")).toBe(true)
    })
}

describe("EmbedFormPageClient", () => {
    beforeEach(() => {
        addEventListenerSpy?.mockRestore()
        addEventListenerSpy = vi.spyOn(window, "addEventListener")
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

    afterEach(() => {
        addEventListenerSpy?.mockRestore()
        addEventListenerSpy = null
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
        await waitForEmbedMessageListener()

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
        expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
        expect(screen.queryByText("I agree to be contacted.")).not.toBeInTheDocument()
        expect(screen.getByText(/By submitting, you agree/i)).toBeInTheDocument()
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
                }),
            )
        })
        expect(await screen.findByRole("heading", { name: "Request received" })).toBeInTheDocument()
    })

    it("blocks invalid public contact values before submitting the embedded form", async () => {
        getEmbedPublicForm.mockResolvedValueOnce({
            ...embedForm,
            form_schema: {
                ...embedForm.form_schema,
                pages: [
                    {
                        title: "Contact",
                        fields: [
                            ...embedForm.form_schema.pages[0].fields,
                            {
                                key: "phone",
                                label: "Phone",
                                type: "phone",
                                required: true,
                                sensitivity: "contact",
                            },
                            {
                                key: "state",
                                label: "State",
                                type: "text",
                                required: true,
                                sensitivity: "campaign_safe",
                                validation: {
                                    min_length: 2,
                                    max_length: 2,
                                    pattern: "^[A-Za-z]{2}$",
                                },
                            },
                            {
                                key: "weight_lb",
                                label: "Weight (lb)",
                                type: "number",
                                required: true,
                                sensitivity: "sensitive_health",
                                validation: { min_value: 1, max_value: 1000 },
                            },
                        ],
                    },
                ],
            },
        })

        render(<EmbedFormPageClient slug="lead-form" initialParentOrigin="https://www.ewisurrogacy.com" />)

        expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
        await waitForEmbedMessageListener()
        window.dispatchEvent(
            new MessageEvent("message", {
                origin: "https://www.ewisurrogacy.com",
                data: { type: "sf:form:init", attribution: {} },
            }),
        )
        await waitFor(() => {
            expect(createEmbedFormSession).toHaveBeenCalled()
        })

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: "Embed Lead" },
        })
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: "embed@example.com" },
        })
        fireEvent.change(screen.getByLabelText(/phone/i), {
            target: { value: "123" },
        })
        fireEvent.change(screen.getByLabelText(/state/i), {
            target: { value: "CA" },
        })
        fireEvent.change(screen.getByLabelText(/weight/i), {
            target: { value: "150" },
        })
        fireEvent.click(screen.getByRole("button", { name: /submit/i }))

        expect(await screen.findByText(/phone must be a valid phone number/i)).toBeInTheDocument()
        expect(submitEmbedPublicForm).not.toHaveBeenCalled()
    })

    it("blocks embedded file fields before submitting", async () => {
        getEmbedPublicForm.mockResolvedValueOnce({
            ...embedForm,
            form_schema: {
                ...embedForm.form_schema,
                pages: [
                    {
                        title: "Contact",
                        fields: [
                            ...embedForm.form_schema.pages[0].fields,
                            {
                                key: "supporting_docs",
                                label: "Supporting Documents",
                                type: "file",
                                required: true,
                                sensitivity: "sensitive_health",
                            },
                        ],
                    },
                ],
            },
        })

        render(<EmbedFormPageClient slug="lead-form" initialParentOrigin="https://www.ewisurrogacy.com" />)

        expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
        await waitForEmbedMessageListener()
        window.dispatchEvent(
            new MessageEvent("message", {
                origin: "https://www.ewisurrogacy.com",
                data: { type: "sf:form:init", attribution: {} },
            }),
        )
        await waitFor(() => {
            expect(createEmbedFormSession).toHaveBeenCalled()
        })

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: "Embed Lead" },
        })
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: "embed@example.com" },
        })
        expect(screen.queryByLabelText(/supporting documents/i)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: /submit/i }))

        expect(await screen.findByText(/cannot collect file uploads/i)).toBeInTheDocument()
        expect(submitEmbedPublicForm).not.toHaveBeenCalled()
    })

    it("posts only non-PII lifecycle messages to the parent frame", async () => {
        const originalParent = Object.getOwnPropertyDescriptor(window, "parent")
        const postMessage = vi.fn()
        Object.defineProperty(window, "parent", {
            configurable: true,
            value: { postMessage },
        })

        try {
            render(<EmbedFormPageClient slug="lead-form" initialParentOrigin="https://www.ewisurrogacy.com" />)

            expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
            await waitForEmbedMessageListener()
            window.dispatchEvent(
                new MessageEvent("message", {
                    origin: "https://www.ewisurrogacy.com",
                    data: {
                        type: "sf:form:init",
                        attribution: {
                            utm_source: "meta",
                            free_text_medical_notes: "private health text",
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
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            expect(await screen.findByRole("heading", { name: "Request received" })).toBeInTheDocument()
            const messages = postMessage.mock.calls.map(([message]) => message)
            expect(messages).toEqual(
                expect.arrayContaining([
                    expect.objectContaining({ type: "sf:form:ready" }),
                    expect.objectContaining({ type: "sf:form:started" }),
                    expect.objectContaining({
                        type: "sf:form:submitted",
                        submissionRef: "submission-1",
                    }),
                ]),
            )
            const serializedMessages = JSON.stringify(messages)
            expect(serializedMessages).not.toContain("Embed Lead")
            expect(serializedMessages).not.toContain("embed@example.com")
            expect(serializedMessages).not.toContain("private health text")
            expect(serializedMessages).not.toContain("utm_source")
        } finally {
            if (originalParent) {
                Object.defineProperty(window, "parent", originalParent)
            }
        }
    })

    it("does not create duplicate embed sessions when the parent sends init more than once", async () => {
        render(<EmbedFormPageClient slug="lead-form" initialParentOrigin="https://www.ewisurrogacy.com" />)

        expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
        await waitForEmbedMessageListener()

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
