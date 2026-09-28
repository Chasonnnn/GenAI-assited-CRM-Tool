import { act, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import FormBuilderPage from "../app/(app)/automation/forms/[id]/page.client"
import type { FormRead, FormSchema, FormUpdatePayload } from "@/lib/api/forms"

const api = vi.hoisted(() => ({
    getForm: vi.fn(),
    listFormIntakeLinks: vi.fn(),
    listFormMappings: vi.fn(),
    listFormSubmissions: vi.fn(),
    publishForm: vi.fn(),
    setFormMappings: vi.fn(),
    updateForm: vi.fn(),
}))
const { toastError, toastSuccess } = vi.hoisted(() => ({ toastError: vi.fn(), toastSuccess: vi.fn() }))
const navigationState = vi.hoisted(() => ({ formId: "form-a" }))

vi.mock("@/lib/api/forms", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/forms")>()),
    ...api,
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: navigationState.formId }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: toastSuccess, error: toastError },
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
                { key: "date_of_birth", label: "Date of Birth", type: "date", required: true },
                { key: "phone", label: "Phone", type: "phone", required: true },
                { key: "email", label: "Email", type: "email", required: true },
            ],
        },
    ],
    public_title: "Apply today",
}

const buildForm = (id: string, overrides: Partial<FormRead> = {}): FormRead => ({
    id,
    name: id === "form-a" ? "Surrogate Application" : "Donor Interest",
    status: "published",
    purpose: "surrogate_application",
    lead_kind: "surrogate",
    created_at: "2026-09-20T00:00:00Z",
    updated_at: "2026-09-20T00:00:00Z",
    description: null,
    form_schema: liveSchema,
    published_schema: liveSchema,
    max_file_size_bytes: 10 * 1024 * 1024,
    max_file_count: 10,
    allowed_mime_types: null,
    default_application_email_template_id: null,
    ...overrides,
})

type PendingUpdate = {
    formId: string
    title: string | null | undefined
    settled: boolean
    finish: () => void
    fail: () => void
}

async function advance(ms: number) {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
    })
}

const header = () => within(screen.getByLabelText("Form name").parentElement as HTMLElement)
const headerPublishButton = () =>
    screen
        .getAllByRole("button", { name: /^publish$/i })
        .find((button) => !button.closest("[role='alertdialog']")) as HTMLElement

function editTitle(value: string) {
    if (!screen.queryByLabelText("Title")) {
        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))
    }
    fireEvent.change(screen.getByLabelText("Title"), { target: { value } })
}

describe("FormBuilderPage autosave", () => {
    let server: Map<string, FormRead>
    let updates: PendingUpdate[]

    const settleStartedUpdates = async (from = 0) => {
        for (const update of updates.slice(from)) {
            if (!update.settled) update.finish()
        }
        await advance(10)
    }

    beforeEach(() => {
        vi.useFakeTimers()
        navigationState.formId = "form-a"
        toastError.mockReset()
        toastSuccess.mockReset()
        server = new Map([
            ["form-a", buildForm("form-a")],
            ["form-b", buildForm("form-b", { status: "draft", published_schema: null })],
        ])
        updates = []
        api.getForm.mockImplementation(async (formId: string) => server.get(formId))
        api.listFormMappings.mockResolvedValue([])
        api.listFormIntakeLinks.mockResolvedValue([])
        api.listFormSubmissions.mockResolvedValue([])
        api.setFormMappings.mockResolvedValue([])
        api.publishForm.mockImplementation(async (formId: string) => {
            const form = server.get(formId) as FormRead
            server.set(formId, { ...form, status: "published", published_schema: form.form_schema ?? null })
            return { id: formId, status: "published", published_at: "2026-09-27T00:00:00Z" }
        })
        api.updateForm.mockImplementation(
            (formId: string, payload: FormUpdatePayload) =>
                new Promise<FormRead>((resolve, reject) => {
                    const update: PendingUpdate = {
                        formId,
                        title: payload.form_schema?.public_title,
                        settled: false,
                        finish: () => {
                            update.settled = true
                            const form = server.get(formId) as FormRead
                            const saved = { ...form, form_schema: payload.form_schema ?? form.form_schema ?? null }
                            server.set(formId, saved)
                            resolve(saved)
                        },
                        fail: () => {
                            update.settled = true
                            reject(new Error("Network error"))
                        },
                    }
                    updates.push(update)
                }),
        )
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("saves an edit made during an in-flight autosave once, then settles", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        expect(header().getByText("Published")).toBeInTheDocument()

        editTitle("Apply now")
        await advance(1200)
        await advance(10)
        expect(updates.map((update) => update.title)).toEqual(["Apply now"])

        editTitle("Apply this week")
        await advance(3000)
        expect(updates).toHaveLength(1)

        updates[0].finish()
        await advance(10)
        await advance(1200)
        await advance(10)
        expect(updates.map((update) => update.title)).toEqual(["Apply now", "Apply this week"])

        updates[1].finish()
        await advance(10)
        await advance(5000)

        expect(updates).toHaveLength(2)
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
        expect(header().getByText("Unpublished changes")).toBeInTheDocument()
        expect(headerPublishButton()).toBeEnabled()
    })

    it("keeps a manual save when an older autosave fails afterwards", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await advance(1200)
        await advance(3000)
        expect(updates).toHaveLength(1)

        editTitle("Apply this week")
        fireEvent.click(screen.getByRole("button", { name: /^save$/i }))
        await advance(10)
        await settleStartedUpdates(1)
        updates[0].fail()
        await advance(10)
        await settleStartedUpdates(1)
        await advance(5000)

        expect(updates.map((update) => update.title)).toEqual(["Apply now", "Apply this week"])
        expect(toastSuccess).toHaveBeenCalledWith("Form saved")
        expect(screen.queryByText("Autosave failed")).not.toBeInTheDocument()
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
    })

    it("keeps a publish when an older autosave fails afterwards", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await advance(1200)
        await advance(3000)
        expect(updates).toHaveLength(1)

        editTitle("Apply this week")
        fireEvent.click(headerPublishButton())
        await advance(10)
        const dialog = screen.getByRole("alertdialog", { name: /publish form/i })
        fireEvent.click(within(dialog).getByRole("button", { name: /^publish$/i }))
        await advance(10)
        await settleStartedUpdates(1)
        updates[0].fail()
        await advance(10)
        await settleStartedUpdates(1)
        await advance(5000)

        expect(api.publishForm).toHaveBeenCalledTimes(1)
        expect(toastSuccess).toHaveBeenCalledWith("Form published")
        expect(screen.queryByText("Autosave failed")).not.toBeInTheDocument()
        expect(header().getByText("Published")).toBeInTheDocument()
        expect(headerPublishButton()).toBeDisabled()
    })

    it("does not autosave a form opened from another form without edits", async () => {
        const view = render(<FormBuilderPage />)
        await advance(10)

        navigationState.formId = "form-b"
        view.rerender(<FormBuilderPage />)
        await advance(10)
        await advance(5000)

        expect(header().getByText("Draft")).toBeInTheDocument()
        expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument()
        expect(updates).toHaveLength(0)
    })

    it("ignores an older autosave result after leaving and returning to the form", async () => {
        const view = render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await advance(1200)
        await advance(3000)
        expect(updates).toHaveLength(1)

        navigationState.formId = "form-b"
        view.rerender(<FormBuilderPage />)
        await advance(10)
        navigationState.formId = "form-a"
        view.rerender(<FormBuilderPage />)
        await advance(10)

        updates[0].finish()
        await advance(10)
        await advance(5000)

        expect(updates.map((update) => [update.formId, update.title])).toEqual([["form-a", "Apply now"]])
    })

    it("does not let a result for the previous form change the form being edited", async () => {
        const view = render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await advance(1200)
        await advance(3000)
        expect(updates).toHaveLength(1)

        navigationState.formId = "form-b"
        view.rerender(<FormBuilderPage />)
        await advance(10)
        expect(header().getByText("Draft")).toBeInTheDocument()
        editTitle("Join our program")

        updates[0].finish()
        await advance(10)
        expect(header().getByText("Draft")).toBeInTheDocument()
        expect(screen.getByLabelText("Title")).toHaveValue("Join our program")

        await advance(1200)
        await settleStartedUpdates(1)
        await advance(5000)

        expect(updates.map((update) => [update.formId, update.title])).toEqual([
            ["form-a", "Apply now"],
            ["form-b", "Join our program"],
        ])
        expect(header().getByText("Draft")).toBeInTheDocument()
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
    })
})
