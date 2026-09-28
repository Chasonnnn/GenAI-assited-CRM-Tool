import { act, fireEvent, render, screen, within } from "@testing-library/react"
import { Activity } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import FormBuilderPage from "../app/(app)/automation/forms/[id]/page.client"
import type { FormCreatePayload, FormRead, FormSchema, FormUpdatePayload } from "@/lib/api/forms"

const api = vi.hoisted(() => ({
    createForm: vi.fn(),
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
const routerReplace = vi.hoisted(() => vi.fn())

vi.mock("@/lib/api/forms", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/forms")>()),
    ...api,
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: navigationState.formId }),
    useRouter: () => ({ push: vi.fn(), replace: routerReplace }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: toastSuccess, error: toastError },
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({
        data: { policy_version: 1, permissions: ["edit_surrogates", "manage_forms"] },
    }),
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
const saveButton = () => screen.getByRole("button", { name: /^save$/i })
const headerPublishButton = () =>
    screen
        .getAllByRole("button", { name: /^publish$/i })
        .find((button) => !button.closest("[role='alertdialog']")) as HTMLElement

function renderBuilder(mode: "visible" | "hidden" = "visible") {
    return (
        <Activity mode={mode}>
            <FormBuilderPage />
        </Activity>
    )
}

function addRequiredIdentityFields() {
    fireEvent.click(screen.getByRole("button", { name: "Add preset Full Name field" }))
    fireEvent.click(screen.getByRole("button", { name: "Add preset Email field" }))
    fireEvent.click(screen.getByRole("button", { name: "Add preset Phone field" }))
    fireEvent.click(screen.getByRole("button", { name: "Demographics" }))
    fireEvent.click(screen.getByRole("button", { name: "Add preset Date of Birth field" }))
}

function editTitle(value: string) {
    if (!screen.queryByLabelText("Title")) {
        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))
    }
    fireEvent.change(screen.getByLabelText("Title"), { target: { value } })
}

describe("FormBuilderPage autosave", () => {
    let server: Map<string, FormRead>
    let updates: PendingUpdate[]
    let creates: Array<{ finish: () => void }>

    const settleStartedUpdates = async (from = 0) => {
        for (const update of updates.slice(from)) {
            if (!update.settled) update.finish()
        }
        await advance(10)
    }

    beforeEach(() => {
        vi.useFakeTimers()
        navigationState.formId = "form-a"
        routerReplace.mockReset()
        toastError.mockReset()
        toastSuccess.mockReset()
        server = new Map([
            ["form-a", buildForm("form-a")],
            ["form-b", buildForm("form-b", { status: "draft", published_schema: null })],
        ])
        updates = []
        creates = []
        api.createForm.mockImplementation(
            (payload: FormCreatePayload) =>
                new Promise<FormRead>((resolve) => {
                    creates.push({
                        finish: () => {
                            const created = buildForm("form-new", {
                                name: payload.name,
                                status: "draft",
                                form_schema: payload.form_schema ?? null,
                                published_schema: null,
                            })
                            server.set(created.id, created)
                            resolve(created)
                        },
                    })
                }),
        )
        api.publishForm.mockReset()
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

    it("ignores Save and Publish while a new form is being created", async () => {
        navigationState.formId = "new"
        render(<FormBuilderPage />)
        await advance(10)
        fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Published Intake" } })
        addRequiredIdentityFields()

        fireEvent.click(saveButton())
        await advance(10)
        expect(creates).toHaveLength(1)
        expect(saveButton()).toBeDisabled()
        expect(headerPublishButton()).toBeDisabled()

        fireEvent.click(saveButton())
        fireEvent.click(headerPublishButton())
        await advance(10)
        expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()

        creates[0].finish()
        await advance(10)
        await advance(5000)

        expect(api.createForm).toHaveBeenCalledTimes(1)
        expect(api.publishForm).not.toHaveBeenCalled()
        expect(routerReplace.mock.calls).toEqual([["/automation/forms/form-new"]])
        expect(toastSuccess.mock.calls).toEqual([["Form saved"]])
        expect(saveButton()).toBeEnabled()
    })

    it("does not redirect or report a create that finishes after the builder closes", async () => {
        navigationState.formId = "new"
        const view = render(<FormBuilderPage />)
        await advance(10)
        fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Published Intake" } })
        fireEvent.click(saveButton())
        await advance(10)
        expect(creates).toHaveLength(1)

        view.unmount()
        creates[0].finish()
        await advance(10)

        expect(routerReplace).not.toHaveBeenCalled()
        expect(toastSuccess).not.toHaveBeenCalled()
        expect(toastError).not.toHaveBeenCalled()
    })

    it("ignores Save clicked before a starting autosave has rendered", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await act(async () => {
            await vi.advanceTimersByTimeAsync(1200)
            fireEvent.click(saveButton())
        })
        await advance(10)
        expect(updates).toHaveLength(1)

        await settleStartedUpdates()
        await advance(10)
        await advance(5000)

        expect(updates).toHaveLength(1)
        expect(toastSuccess).not.toHaveBeenCalled()
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
    })

    it("waits for an autosave before publishing from an open dialog", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        fireEvent.click(headerPublishButton())
        await advance(10)
        const dialog = screen.getByRole("alertdialog", { name: /publish form/i })

        await advance(1200)
        await advance(10)
        expect(updates).toHaveLength(1)
        const confirm = within(dialog).getByRole("button", { name: /^publish$/i })
        expect(confirm).toBeDisabled()
        fireEvent.click(confirm)
        await advance(10)
        expect(updates).toHaveLength(1)

        updates[0].finish()
        await advance(10)
        expect(confirm).toBeEnabled()
        fireEvent.click(confirm)
        await advance(10)
        await settleStartedUpdates(1)
        await advance(10)

        expect(updates.map((update) => update.title)).toEqual(["Apply now", "Apply now"])
        expect(api.publishForm).toHaveBeenCalledTimes(1)
        expect(toastSuccess).toHaveBeenCalledWith("Form published")
        expect(header().getByText("Published")).toBeInTheDocument()
    })

    it("does not resend a draft whose autosave failed until it changes or is saved", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await advance(1200)
        await advance(10)
        expect(updates).toHaveLength(1)

        updates[0].fail()
        await advance(10)
        await advance(12000)
        expect(updates).toHaveLength(1)
        expect(screen.getByText("Autosave failed")).toBeInTheDocument()

        editTitle("Apply now!")
        await advance(1200)
        await advance(10)
        expect(updates.map((update) => update.title)).toEqual(["Apply now", "Apply now!"])

        updates[1].fail()
        await advance(10)
        await advance(12000)
        expect(updates).toHaveLength(2)

        fireEvent.click(saveButton())
        await advance(10)
        await settleStartedUpdates(2)
        await advance(5000)

        expect(updates.map((update) => update.title)).toEqual(["Apply now", "Apply now!", "Apply now!"])
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
    })

    it("autosaves a failed draft again after it is edited away and back", async () => {
        render(<FormBuilderPage />)
        await advance(10)
        editTitle("Apply now")
        await advance(1200)
        await advance(10)
        updates[0].fail()
        await advance(10)

        editTitle("Apply now!")
        await advance(500)
        editTitle("Apply now")
        await advance(1200)
        await advance(10)

        expect(updates.map((update) => update.title)).toEqual(["Apply now", "Apply now"])
    })

    it("keeps a form created while the builder is hidden and redirects when it is shown", async () => {
        navigationState.formId = "new"
        const view = render(renderBuilder())
        await advance(10)
        fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Published Intake" } })
        fireEvent.click(saveButton())
        await advance(10)
        expect(creates).toHaveLength(1)

        view.rerender(renderBuilder("hidden"))
        await advance(10)
        creates[0].finish()
        await advance(10)
        expect(routerReplace).not.toHaveBeenCalled()

        view.rerender(renderBuilder())
        await advance(10)
        expect(routerReplace.mock.calls).toEqual([["/automation/forms/form-new"]])

        fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Published Intake v2" } })
        fireEvent.click(saveButton())
        await advance(10)
        await settleStartedUpdates()
        await advance(10)

        expect(api.createForm).toHaveBeenCalledTimes(1)
        expect(updates.map((update) => update.formId)).toEqual(["form-new"])
        expect(routerReplace).toHaveBeenCalledTimes(1)
    })

    it("clears Save when the builder is hidden and shown again during the save", async () => {
        const view = render(renderBuilder())
        await advance(10)
        editTitle("Apply now")
        fireEvent.click(saveButton())
        await advance(10)
        expect(updates).toHaveLength(1)

        view.rerender(renderBuilder("hidden"))
        await advance(10)
        updates[0].finish()
        await advance(10)
        expect(toastSuccess).not.toHaveBeenCalled()

        view.rerender(renderBuilder())
        await advance(10)
        await advance(5000)

        expect(updates).toHaveLength(1)
        expect(saveButton()).toBeEnabled()
        expect(headerPublishButton()).toBeEnabled()
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
    })

    it("clears Publish when the builder is hidden and shown again during the publish", async () => {
        const view = render(renderBuilder())
        await advance(10)
        editTitle("Apply now")
        fireEvent.click(headerPublishButton())
        await advance(10)
        const dialog = screen.getByRole("alertdialog", { name: /publish form/i })
        fireEvent.click(within(dialog).getByRole("button", { name: /^publish$/i }))
        await advance(10)
        expect(updates).toHaveLength(1)

        view.rerender(renderBuilder("hidden"))
        await advance(10)
        view.rerender(renderBuilder())
        await advance(10)
        await settleStartedUpdates()
        await advance(10)
        await advance(5000)

        expect(api.publishForm).toHaveBeenCalledTimes(1)
        expect(toastSuccess).toHaveBeenCalledWith("Form published")
        expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
        expect(header().getByText("Published")).toBeInTheDocument()
        expect(saveButton()).toBeEnabled()
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
