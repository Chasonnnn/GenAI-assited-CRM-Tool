import React from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import EmbedFormPageClient from "../app/embed/forms/[slug]/page.client"
import { getPublicFieldValidationError, type PublicFieldValue } from "@/lib/forms/public-field-validation"
import { ApiError } from "@/lib/api"

vi.unmock("@tanstack/react-query")

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

const smsConsentOptions = {
    operational: {
        disclosure: "I agree to receive application and appointment texts. Reply STOP to opt out.",
        sms_terms_url: "https://www.ewisurrogacy.com/sms-terms",
        privacy_policy_url: "https://www.ewisurrogacy.com/privacy",
    },
    promotional: {
        disclosure: "I agree to receive promotional texts about surrogacy opportunities. Reply STOP to opt out.",
        sms_terms_url: "https://www.ewisurrogacy.com/sms-terms",
        privacy_policy_url: "https://www.ewisurrogacy.com/privacy",
    },
}

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
    messaging_consent: {
        phone_field_key: null,
        operational: null,
        promotional: null,
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

function renderEmbedForm(props: React.ComponentProps<typeof EmbedFormPageClient>) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    })
    const renderPage = (pageProps: React.ComponentProps<typeof EmbedFormPageClient>) => (
        <QueryClientProvider client={queryClient}>
            <EmbedFormPageClient {...pageProps} />
        </QueryClientProvider>
    )
    const view = render(renderPage(props))
    return {
        ...view,
        rerenderEmbedForm: (nextProps: React.ComponentProps<typeof EmbedFormPageClient>) => {
            view.rerender(renderPage(nextProps))
        },
    }
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
            outcome: "received",
        })
    })

    afterEach(() => {
        addEventListenerSpy?.mockRestore()
        addEventListenerSpy = null
    })

    it("loads via parent origin, creates a sanitized embed session, and submits lead answers", async () => {
        renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

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
        expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
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
                    sms_operational: false,
                    sms_promotional: false,
                    sms_phone_field_key: null,
                }),
            )
        })
        expect(await screen.findByRole("heading", { name: "Request received" })).toBeInTheDocument()
    })

    it.each<{ value: PublicFieldValue | undefined; error: string | null }>([
        { value: undefined, error: null },
        { value: [], error: "Please add at least 2 rows for History" },
        { value: [{}], error: "Please add at least 2 rows for History" },
        { value: [{}, {}], error: null },
        { value: [{}, {}, {}], error: null },
        { value: [{}, {}, {}, {}], error: "Please limit History to 3 rows" },
    ])("validates explicit optional table row counts: %o", ({ value, error }) => {
        expect(getPublicFieldValidationError({
            key: "history", label: "History", type: "repeatable_table",
            required: false, min_rows: 2, max_rows: 3,
            columns: [{ key: "detail", label: "Detail", type: "text" }],
        }, value)).toBe(error)
    })

    it.each([
        { required: true, columnRequired: false },
        { required: true, columnRequired: true },
        { required: false, columnRequired: true },
    ])("submits visible minimum rows without requiring untouched optional tables: %o", async ({ required, columnRequired }) => {
        getEmbedPublicForm.mockResolvedValue({
            ...embedForm,
            form_schema: {
                ...embedForm.form_schema,
                pages: [{
                    title: "Contact",
                    fields: [
                        ...embedForm.form_schema.pages[0].fields,
                        {
                            key: "history", label: "History", type: "repeatable_table",
                            required, min_rows: 2, max_rows: 3,
                            columns: [{ key: "detail", label: "Detail", type: "text", required: columnRequired }],
                        },
                        {
                            key: "follow_up", label: "History follow-up", type: "text",
                            show_if: { field_key: "history", operator: "is_not_empty" },
                        },
                        {
                            key: "hidden", label: "Hidden table", type: "repeatable_table",
                            required: true, min_rows: 3,
                            columns: [{ key: "detail", label: "Hidden detail", type: "text" }],
                            show_if: { field_key: "full_name", operator: "equals", value: "Other applicant" },
                        },
                    ],
                }],
            },
        })
        renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })
        expect(await screen.findAllByLabelText(/detail/i)).toHaveLength(2)
        if (required) {
            expect(await screen.findByLabelText("History follow-up")).toBeInTheDocument()
        } else {
            expect(screen.queryByLabelText("History follow-up")).not.toBeInTheDocument()
        }
        await waitForEmbedMessageListener()
        window.dispatchEvent(new MessageEvent("message", {
            origin: "https://www.ewisurrogacy.com",
            data: { type: "sf:form:init", attribution: {} },
        }))
        await waitFor(() => expect(createEmbedFormSession).toHaveBeenCalled())
        fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Embed Lead" } })
        fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "embed@example.com" } })
        const submitButton = screen.getByRole("button", { name: /submit/i })
        fireEvent.click(submitButton)

        if (required && columnRequired) {
            expect(await screen.findByText("Please complete: Detail")).toBeInTheDocument()
            expect(submitEmbedPublicForm).not.toHaveBeenCalled()
            const cells = screen.getAllByLabelText(/detail/i)
            fireEvent.change(cells[0]!, { target: { value: "First row" } })
            fireEvent.click(submitButton)
            expect(submitEmbedPublicForm).not.toHaveBeenCalled()
            fireEvent.change(cells[1]!, { target: { value: "Second row" } })
            fireEvent.click(submitButton)
        }

        await waitFor(() => expect(submitEmbedPublicForm).toHaveBeenCalledWith(
            "lead-form",
            expect.objectContaining({
                answers: {
                    full_name: "Embed Lead",
                    email: "embed@example.com",
                    ...(required ? {
                        history: columnRequired ? [{ detail: "First row" }, { detail: "Second row" }] : [{}, {}],
                    } : {}),
                },
            }),
        ))
        expect(await screen.findByRole("heading", { name: "Request received" })).toBeInTheDocument()
    })

    it("keeps the newest form when an older slug request finishes last", async () => {
        let resolveFirst: (value: typeof embedForm) => void = () => undefined
        let resolveSecond: (value: typeof embedForm) => void = () => undefined
        const firstRequest = new Promise<typeof embedForm>((resolve) => {
            resolveFirst = resolve
        })
        const secondRequest = new Promise<typeof embedForm>((resolve) => {
            resolveSecond = resolve
        })
        getEmbedPublicForm.mockImplementation((slug: string) =>
            slug === "first-form" ? firstRequest : secondRequest
        )

        const view = renderEmbedForm({
            slug: "first-form",
            initialParentOrigin: "https://www.ewisurrogacy.com",
        })
        await waitFor(() => expect(getEmbedPublicForm).toHaveBeenCalledTimes(1))

        view.rerenderEmbedForm({
            slug: "second-form",
            initialParentOrigin: "https://www.ewisurrogacy.com",
        })
        await waitFor(() => expect(getEmbedPublicForm).toHaveBeenCalledTimes(2))

        await act(async () => {
            resolveSecond({
                ...embedForm,
                form_id: "form-2",
                form_schema: { ...embedForm.form_schema, public_title: "Second Form" },
            })
        })
        expect(await screen.findByRole("heading", { name: "Second Form" })).toBeInTheDocument()

        await act(async () => {
            resolveFirst({
                ...embedForm,
                form_schema: { ...embedForm.form_schema, public_title: "Older Form" },
            })
        })

        expect(screen.getByRole("heading", { name: "Second Form" })).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Older Form" })).not.toBeInTheDocument()
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

        renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

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

        renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

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
            getEmbedPublicForm.mockResolvedValue({
                ...embedForm,
                form_schema: {
                    ...embedForm.form_schema,
                    pages: [{
                        title: "Contact",
                        fields: [
                            ...embedForm.form_schema.pages[0].fields,
                            {
                                key: "history", label: "History", type: "repeatable_table",
                                required: true, min_rows: 2,
                                columns: [{ key: "detail", label: "Detail", type: "text" }],
                            },
                        ],
                    }],
                },
            })
            renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

            expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
            expect(screen.getAllByLabelText("Detail")).toHaveLength(2)
            expect(postMessage).not.toHaveBeenCalledWith(
                { type: "sf:form:started" }, "https://www.ewisurrogacy.com",
            )
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
        renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

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

    it.each([
        {
            name: "a stale form version",
            error: new ApiError(409, "Conflict", "Published version is no longer current"),
            message: "This form changed. Reload the page and try again.",
        },
        {
            name: "a pending duplicate applicant",
            error: new ApiError(409, "Conflict", "An intake submission is already pending review."),
            message: "Unable to submit the form. Please try again.",
        },
        {
            name: "a conflict without a detail",
            error: new ApiError(409, "Conflict"),
            message: "Unable to submit the form. Please try again.",
        },
        {
            name: "a network failure",
            error: new Error("Network down"),
            message: "Unable to submit the form. Please try again.",
        },
    ])("shows the submit failure message for $name", async ({ error, message }) => {
        submitEmbedPublicForm.mockRejectedValueOnce(error)
        renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

        expect(await screen.findByRole("heading", { name: "Become a Surrogate" })).toBeInTheDocument()
        await waitForEmbedMessageListener()
        window.dispatchEvent(
            new MessageEvent("message", {
                origin: "https://www.ewisurrogacy.com",
                data: { type: "sf:form:init", attribution: {} },
            }),
        )
        await waitFor(() => expect(createEmbedFormSession).toHaveBeenCalled())
        fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Embed Lead" } })
        fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "embed@example.com" } })
        fireEvent.click(screen.getByRole("button", { name: /submit/i }))

        expect(await screen.findByText(message)).toBeInTheDocument()
        expect(screen.getByLabelText(/full name/i)).toHaveValue("Embed Lead")
        expect(screen.queryByRole("heading", { name: "Request received" })).not.toBeInTheDocument()
        expect(document.body).not.toHaveTextContent(error.message)
    })

    describe("SMS consent", () => {
        const [fullNameField, emailField] = embedForm.form_schema.pages[0].fields
        const homePhoneField = {
            key: "phone",
            label: "Home Phone",
            type: "phone",
            required: false,
            sensitivity: "contact",
        }
        const mobilePhoneField = {
            key: "mobile_number",
            label: "Mobile Phone",
            type: "phone",
            required: false,
            sensitivity: "contact",
        }
        const contactPreferenceField = {
            key: "contact_preference",
            label: "Contact Preference",
            type: "text",
            required: false,
            sensitivity: "campaign_safe",
        }
        const operationalConsent = {
            phone_field_key: "mobile_number",
            operational: smsConsentOptions.operational,
            promotional: null,
        }
        const smsForm = {
            ...embedForm,
            form_schema: {
                ...embedForm.form_schema,
                pages: [
                    {
                        title: "Contact",
                        fields: [fullNameField, homePhoneField, mobilePhoneField, emailField],
                    },
                ],
            },
            messaging_consent: operationalConsent,
        }
        const conditionalPhoneForm = {
            ...smsForm,
            form_schema: {
                ...smsForm.form_schema,
                pages: [
                    {
                        title: "Contact",
                        fields: [
                            fullNameField,
                            contactPreferenceField,
                            {
                                ...mobilePhoneField,
                                show_if: {
                                    field_key: "contact_preference",
                                    operator: "not_equals",
                                    value: "Email only",
                                },
                            },
                            emailField,
                        ],
                    },
                ],
            },
        }
        const missingPhoneMessage = "Add a phone number to receive text messages, or uncheck to continue."

        async function startEmbedSession() {
            await waitForEmbedMessageListener()
            window.dispatchEvent(
                new MessageEvent("message", {
                    origin: "https://www.ewisurrogacy.com",
                    data: { type: "sf:form:init", attribution: {} },
                }),
            )
            await waitFor(() => expect(createEmbedFormSession).toHaveBeenCalled())
        }

        async function renderStartedSmsForm(form: unknown) {
            getEmbedPublicForm.mockResolvedValue(form)
            renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })
            await screen.findByLabelText(/full name/i)
            await startEmbedSession()
            fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Embed Lead" } })
            fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "embed@example.com" } })
        }

        function getOperationalCheckbox() {
            return screen.getByRole("checkbox", { name: /application and appointment texts/i })
        }

        function isBefore(first: HTMLElement, second: HTMLElement): boolean {
            return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
        }

        it("renders the SMS consent directly after the mapped phone field with readable disclosure and links", async () => {
            getEmbedPublicForm.mockResolvedValue(smsForm)
            renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

            const phoneInput = await screen.findByLabelText("Mobile Phone")
            const smsCheckbox = getOperationalCheckbox()
            const emailInput = screen.getByLabelText(/email/i)
            expect(isBefore(screen.getByLabelText("Home Phone"), phoneInput)).toBe(true)
            expect(isBefore(phoneInput, smsCheckbox)).toBe(true)
            expect(isBefore(smsCheckbox, emailInput)).toBe(true)
            expect(isBefore(smsCheckbox, screen.getByText(/By submitting, you agree/i))).toBe(true)
            expect(smsCheckbox).not.toBeChecked()

            expect(screen.getByText(/application and appointment texts/i)).toHaveClass("text-sm", "text-stone-700")
            const termsLink = screen.getByRole("link", { name: "Terms of Service" })
            expect(termsLink).toHaveAttribute("href", "https://www.ewisurrogacy.com/sms-terms")
            expect(termsLink).toHaveAttribute("target", "_blank")
            const privacyLink = screen.getByRole("link", { name: "Privacy Policy" })
            expect(privacyLink).toHaveAttribute("href", "https://www.ewisurrogacy.com/privacy")
            expect(privacyLink).toHaveAttribute("target", "_blank")
            expect(screen.queryByRole("link", { name: "SMS Terms" })).not.toBeInTheDocument()
        })

        it("submits with both SMS choices unchecked and no phone number", async () => {
            await renderStartedSmsForm({
                ...smsForm,
                messaging_consent: { phone_field_key: "mobile_number", ...smsConsentOptions },
            })

            const smsCheckboxes = screen.getAllByRole("checkbox")
            expect(smsCheckboxes).toHaveLength(2)
            expect(smsCheckboxes[0]).not.toBeChecked()
            expect(smsCheckboxes[1]).not.toBeChecked()
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            await waitFor(() => expect(submitEmbedPublicForm).toHaveBeenCalledWith(
                "lead-form",
                expect.objectContaining({
                    answers: { full_name: "Embed Lead", email: "embed@example.com" },
                    sms_operational: false,
                    sms_promotional: false,
                    sms_phone_field_key: null,
                }),
            ))
        })

        it("shows an inline message instead of submitting when SMS is checked without a phone number", async () => {
            await renderStartedSmsForm(smsForm)

            const smsCheckbox = getOperationalCheckbox()
            fireEvent.click(smsCheckbox)
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            const message = await screen.findByText("Enter your phone number to receive text messages.")
            expect(message).toHaveAttribute("role", "alert")
            expect(submitEmbedPublicForm).not.toHaveBeenCalled()
            expect(smsCheckbox).toHaveAttribute("aria-invalid", "true")
            expect(smsCheckbox).toHaveAccessibleDescription(message.textContent ?? "")
            expect(screen.getByLabelText("Mobile Phone")).toHaveFocus()

            fireEvent.change(screen.getByLabelText("Mobile Phone"), { target: { value: "(555) 123-4567" } })
            expect(screen.queryByText("Enter your phone number to receive text messages.")).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            await waitFor(() => expect(submitEmbedPublicForm).toHaveBeenCalledWith(
                "lead-form",
                expect.objectContaining({
                    answers: {
                        full_name: "Embed Lead",
                        mobile_number: "(555) 123-4567",
                        email: "embed@example.com",
                    },
                    sms_operational: true,
                    sms_promotional: false,
                    sms_phone_field_key: "mobile_number",
                }),
            ))
        })

        it("reports a malformed phone inline on the first attempt when SMS is checked", async () => {
            await renderStartedSmsForm(smsForm)

            fireEvent.change(screen.getByLabelText("Mobile Phone"), { target: { value: "123" } })
            const smsCheckbox = getOperationalCheckbox()
            fireEvent.click(smsCheckbox)
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            const message = await screen.findByText("Enter a valid phone number to receive text messages.")
            expect(message).toHaveAttribute("role", "alert")
            expect(smsCheckbox).toHaveAttribute("aria-invalid", "true")
            expect(smsCheckbox).toHaveAccessibleDescription(message.textContent ?? "")
            expect(screen.getByLabelText("Mobile Phone")).toHaveFocus()
            expect(screen.queryByText(/must be a valid phone number/i)).not.toBeInTheDocument()
            expect(submitEmbedPublicForm).not.toHaveBeenCalled()
        })

        it("submits after unchecking SMS that blocked an empty phone", async () => {
            await renderStartedSmsForm(smsForm)

            fireEvent.click(getOperationalCheckbox())
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))
            await screen.findByText("Enter your phone number to receive text messages.")

            fireEvent.click(getOperationalCheckbox())
            expect(screen.queryByRole("alert")).not.toBeInTheDocument()
            expect(getOperationalCheckbox()).not.toHaveAttribute("aria-invalid")
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            await waitFor(() => expect(submitEmbedPublicForm).toHaveBeenCalledWith(
                "lead-form",
                expect.objectContaining({
                    answers: { full_name: "Embed Lead", email: "embed@example.com" },
                    sms_operational: false,
                    sms_promotional: false,
                    sms_phone_field_key: null,
                }),
            ))
        })

        it("blocks checked SMS after conditional logic hides the phone field until SMS is unchecked", async () => {
            await renderStartedSmsForm(conditionalPhoneForm)

            expect(isBefore(screen.getByLabelText("Mobile Phone"), getOperationalCheckbox())).toBe(true)
            fireEvent.click(getOperationalCheckbox())
            fireEvent.change(screen.getByLabelText("Contact Preference"), { target: { value: "Email only" } })

            expect(screen.queryByLabelText("Mobile Phone")).not.toBeInTheDocument()
            const smsCheckbox = getOperationalCheckbox()
            expect(smsCheckbox).toBeChecked()
            expect(isBefore(screen.getByLabelText(/email/i), smsCheckbox)).toBe(true)
            expect(isBefore(smsCheckbox, screen.getByText(/By submitting, you agree/i))).toBe(true)
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            const message = await screen.findByText(missingPhoneMessage)
            expect(message).toHaveAttribute("role", "alert")
            expect(smsCheckbox).toHaveAttribute("aria-invalid", "true")
            expect(smsCheckbox).toHaveAccessibleDescription(missingPhoneMessage)
            expect(smsCheckbox).toHaveFocus()
            expect(submitEmbedPublicForm).not.toHaveBeenCalled()

            fireEvent.click(smsCheckbox)
            expect(screen.queryByText(missingPhoneMessage)).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            await waitFor(() => expect(submitEmbedPublicForm).toHaveBeenCalledWith(
                "lead-form",
                expect.objectContaining({
                    answers: {
                        full_name: "Embed Lead",
                        contact_preference: "Email only",
                        email: "embed@example.com",
                    },
                    sms_operational: false,
                    sms_promotional: false,
                    sms_phone_field_key: null,
                }),
            ))
        })

        it("blocks checked SMS when the mapped phone field is not on the form", async () => {
            await renderStartedSmsForm({ ...embedForm, messaging_consent: operationalConsent })

            const smsCheckbox = getOperationalCheckbox()
            expect(isBefore(screen.getByLabelText(/email/i), smsCheckbox)).toBe(true)
            fireEvent.click(smsCheckbox)
            fireEvent.click(screen.getByRole("button", { name: /submit/i }))

            expect(await screen.findByText(missingPhoneMessage)).toBeInTheDocument()
            expect(smsCheckbox).toHaveAttribute("aria-invalid", "true")
            expect(submitEmbedPublicForm).not.toHaveBeenCalled()
        })

        it("posts only the validation reason to the parent frame for SMS consent errors", async () => {
            const originalParent = Object.getOwnPropertyDescriptor(window, "parent")
            const postMessage = vi.fn()
            Object.defineProperty(window, "parent", {
                configurable: true,
                value: { postMessage },
            })

            try {
                await renderStartedSmsForm(conditionalPhoneForm)

                fireEvent.change(screen.getByLabelText("Mobile Phone"), { target: { value: "555-01" } })
                fireEvent.click(getOperationalCheckbox())
                fireEvent.click(screen.getByRole("button", { name: /submit/i }))
                await screen.findByText("Enter a valid phone number to receive text messages.")

                fireEvent.change(screen.getByLabelText("Contact Preference"), { target: { value: "Email only" } })
                fireEvent.click(screen.getByRole("button", { name: /submit/i }))
                await screen.findByText(missingPhoneMessage)

                const errorMessages = postMessage.mock.calls.filter(
                    ([message]) => (message as { type?: string }).type === "sf:form:error",
                )
                expect(errorMessages).toEqual([
                    [{ type: "sf:form:error", reason: "validation" }, "https://www.ewisurrogacy.com"],
                    [{ type: "sf:form:error", reason: "validation" }, "https://www.ewisurrogacy.com"],
                ])
                const serializedMessages = JSON.stringify(postMessage.mock.calls)
                expect(serializedMessages).not.toContain("555-01")
                expect(serializedMessages).not.toContain("55501")
                expect(serializedMessages).not.toContain("Embed Lead")
                expect(submitEmbedPublicForm).not.toHaveBeenCalled()
            } finally {
                if (originalParent) {
                    Object.defineProperty(window, "parent", originalParent)
                }
            }
        })

        it("sends the mapped phone field key with checked SMS and shows the server message when the form changed", async () => {
            const originalParent = Object.getOwnPropertyDescriptor(window, "parent")
            const postMessage = vi.fn()
            Object.defineProperty(window, "parent", {
                configurable: true,
                value: { postMessage },
            })
            submitEmbedPublicForm.mockRejectedValueOnce(
                new ApiError(409, "Conflict", "This form changed. Reload the page and try again."),
            )

            try {
                await renderStartedSmsForm(smsForm)
                fireEvent.change(screen.getByLabelText("Mobile Phone"), { target: { value: "(555) 123-4567" } })
                fireEvent.click(getOperationalCheckbox())
                fireEvent.click(screen.getByRole("button", { name: /submit/i }))

                expect(await screen.findByText("This form changed. Reload the page and try again.")).toBeInTheDocument()
                expect(submitEmbedPublicForm).toHaveBeenCalledWith(
                    "lead-form",
                    expect.objectContaining({
                        sms_operational: true,
                        sms_promotional: false,
                        sms_phone_field_key: "mobile_number",
                    }),
                )
                const errorMessages = postMessage.mock.calls.filter(
                    ([message]) => (message as { type?: string }).type === "sf:form:error",
                )
                expect(errorMessages).toEqual([
                    [{ type: "sf:form:error", reason: "submit" }, "https://www.ewisurrogacy.com"],
                ])
            } finally {
                if (originalParent) {
                    Object.defineProperty(window, "parent", originalParent)
                }
            }
        })

        it.each([
            {
                name: "a null phone field key",
                messagingConsent: { phone_field_key: null, operational: null, promotional: null },
            },
            { name: "missing options", messagingConsent: undefined },
        ])("does not render SMS consent with $name", async ({ messagingConsent }) => {
            getEmbedPublicForm.mockResolvedValue({ ...smsForm, messaging_consent: messagingConsent })
            renderEmbedForm({ slug: "lead-form", initialParentOrigin: "https://www.ewisurrogacy.com" })

            await screen.findByLabelText("Mobile Phone")
            expect(screen.queryAllByRole("checkbox")).toHaveLength(0)
            expect(screen.queryByRole("link", { name: "Terms of Service" })).not.toBeInTheDocument()
        })
    })
})
