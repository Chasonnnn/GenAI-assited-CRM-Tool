import { act, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import FormBuilderPage from "../app/(app)/automation/forms/[id]/page.client"
import type { FormRead, FormSchema, FormUpdatePayload } from "@/lib/api/forms"

const api = vi.hoisted(() => ({
    getForm: vi.fn(),
    listFormIntakeLinks: vi.fn(),
    listFormMappings: vi.fn(),
    listFormSubmissions: vi.fn(),
    setFormMappings: vi.fn(),
    updateForm: vi.fn(),
}))

vi.mock("@/lib/api/forms", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/forms")>()),
    ...api,
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "form-1" }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: { policy_version: 1, permissions: ["edit_surrogates"] } }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { org_id: "org-1", user_id: "user-1" } }),
}))

vi.mock("@/lib/hooks/use-form-mapping-options", () => ({
    useFormMappingOptions: () => ({ data: [] }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
}))

vi.mock("@/lib/hooks/use-signature", () => ({
    useOrgSignature: () => ({ data: null }),
}))

const liveSchema: FormSchema = {
    pages: [
        {
            title: "Application",
            fields: [
                { key: "full_name", label: "Full Name", type: "text", required: true },
                { key: "email", label: "Email", type: "email", required: true },
            ],
        },
    ],
    public_title: "Apply today",
}

const buildForm = (formSchema: FormSchema = liveSchema): FormRead => ({
    id: "form-1",
    name: "Surrogate Application",
    status: "published",
    purpose: "surrogate_application",
    lead_kind: "surrogate",
    created_at: "2026-09-20T00:00:00Z",
    updated_at: "2026-09-20T00:00:00Z",
    description: null,
    form_schema: formSchema,
    published_schema: liveSchema,
    max_file_size_bytes: 10 * 1024 * 1024,
    max_file_count: 10,
    allowed_mime_types: null,
    default_application_email_template_id: null,
})

type PendingUpdate = { payload: FormUpdatePayload; finish: () => void }

async function advance(ms: number) {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
    })
}

describe("FormBuilderPage autosave", () => {
    let updates: PendingUpdate[]

    beforeEach(() => {
        vi.useFakeTimers()
        updates = []
        api.getForm.mockResolvedValue(buildForm())
        api.listFormMappings.mockResolvedValue([])
        api.listFormIntakeLinks.mockResolvedValue([])
        api.listFormSubmissions.mockResolvedValue([])
        api.setFormMappings.mockResolvedValue([])
        api.updateForm.mockImplementation(
            (_formId: string, payload: FormUpdatePayload) =>
                new Promise<FormRead>((resolve) => {
                    updates.push({
                        payload,
                        finish: () => resolve(buildForm(payload.form_schema ?? liveSchema)),
                    })
                }),
        )
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("saves an edit made during an in-flight autosave once, then settles", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        const header = within(screen.getByLabelText("Form name").parentElement as HTMLElement)
        expect(header.getByText("Published")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Apply now" } })
        await advance(1200)
        await advance(10)
        expect(updates.map((update) => update.payload.form_schema?.public_title)).toEqual(["Apply now"])

        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Apply this week" } })
        await advance(3000)
        expect(updates).toHaveLength(1)

        updates[0].finish()
        await advance(10)
        await advance(1200)
        await advance(10)
        expect(updates.map((update) => update.payload.form_schema?.public_title)).toEqual([
            "Apply now",
            "Apply this week",
        ])

        updates[1].finish()
        await advance(10)
        await advance(5000)

        expect(updates).toHaveLength(2)
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
        expect(header.getByText("Unpublished changes")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^publish$/i })).toBeEnabled()
    })
})
