import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { FormSubmissionRead } from "@/lib/api/forms"
import FormSubmissionsPage from "@/app/(app)/automation/form-submissions/page"

const mocks = vi.hoisted(() => ({
    access: vi.fn(), forms: vi.fn(), submissions: vi.fn(), candidates: vi.fn(),
    resolve: vi.fn(), retry: vi.fn(), promote: vi.fn(), refetch: vi.fn(),
    searchParams: new URLSearchParams(),
}))
vi.mock("next/navigation", () => ({ useSearchParams: () => mocks.searchParams }))
vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { user_id: "reviewer" } }) }))
vi.mock("@/lib/hooks/use-permissions", () => ({ useEffectivePermissions: () => mocks.access() }))
vi.mock("@tanstack/react-query", () => ({ useQuery: () => mocks.forms() }))
vi.mock("@/lib/api/forms", async (importOriginal) => ({ ...await importOriginal<typeof import("@/lib/api/forms")>(), listSubmissionReviewForms: vi.fn(), getSubmissionFileDownloadUrl: vi.fn() }))
vi.mock("@/lib/hooks/use-forms", () => ({
    useFormSubmissions: (...args: unknown[]) => mocks.submissions(...args),
    useSubmissionMatchCandidates: (...args: unknown[]) => mocks.candidates(...args),
    useResolveSubmissionMatch: () => ({ mutateAsync: mocks.resolve, isPending: false }),
    useRetrySubmissionMatch: () => ({ mutateAsync: mocks.retry, isPending: false }),
    usePromoteIntakeLead: () => ({ mutateAsync: mocks.promote, isPending: false }),
    useApproveFormSubmission: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRejectFormSubmission: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRescanSubmissionFile: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmissionDonorCandidates: () => ({ data: [], isLoading: false, isError: false }),
}))
vi.mock("@/lib/hooks/use-donors", () => ({ useDonors: () => ({ data: undefined, isLoading: false, isError: false }) }))
vi.mock("@/components/ui/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

function submission(): FormSubmissionRead {
    return { id: "submission-1", form_id: "form-1", lead_kind: "surrogate", status: "pending_review",
        submitted_at: "2026-09-07T15:00:00Z", answers: { full_name: "Synthetic Applicant", email: "applicant@test.invalid" },
        source_mode: "shared", match_status: "ambiguous_review", files: [] }
}

describe("standalone form submission access", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.searchParams = new URLSearchParams()
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["view_form_submissions"] }, isLoading: false, isError: false, refetch: mocks.refetch })
        mocks.forms.mockReturnValue({ data: [{ id: "form-1", name: "Applicant intake" }], isLoading: false, isError: false, refetch: mocks.refetch })
        mocks.submissions.mockReturnValue({ data: [submission()], isLoading: false, isError: false, refetch: mocks.refetch })
        mocks.candidates.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: mocks.refetch })
        mocks.resolve.mockResolvedValue({})
        mocks.refetch.mockResolvedValue({})
    })

    it("does not fetch the workspace while access is loading or denied", () => {
        mocks.access.mockReturnValue({ isLoading: true })
        const view = render(<FormSubmissionsPage />)
        expect(view.container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument()
        expect(mocks.forms).not.toHaveBeenCalled()
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["review_form_submissions"] } })
        view.rerender(<FormSubmissionsPage />)
        expect(screen.getByRole("heading", { level: 1, name: "Form Submissions" })).toBeInTheDocument()
        expect(screen.getByText("No access to Form Submissions")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Go to Dashboard" })).toHaveAttribute("href", "/dashboard")
        expect(mocks.forms).not.toHaveBeenCalled()
    })

    it.each(["permissions", "forms", "submissions"])("renders a retryable %s error", (surface) => {
        const target = surface === "permissions" ? mocks.access : surface === "forms" ? mocks.forms : mocks.submissions
        target.mockReturnValue({ isError: true, refetch: mocks.refetch })
        render(<FormSubmissionsPage />)
        expect(screen.getByRole("heading", { level: 1, name: "Form Submissions" })).toBeInTheDocument()
        expect(screen.getByText(/^Couldn't load/)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(mocks.refetch).toHaveBeenCalledTimes(1)
    })

    it("renders loading and empty submission history", () => {
        mocks.submissions.mockReturnValue({ isLoading: true, data: undefined })
        const view = render(<FormSubmissionsPage />)
        expect(screen.getByText("Loading submission history…")).toBeInTheDocument()
        mocks.submissions.mockReturnValue({ data: [], isLoading: false })
        view.rerender(<FormSubmissionsPage />)
        expect(screen.getByText("No submissions in this view.")).toBeInTheDocument()
    })

    it("renders an empty form list without fetching a submission queue", () => {
        mocks.forms.mockReturnValue({ data: [], isLoading: false })
        render(<FormSubmissionsPage />)
        expect(screen.getByText("No submissions available")).toBeInTheDocument()
        expect(mocks.submissions).not.toHaveBeenCalled()
    })

    it("renders populated history without review controls or candidate requests for a viewer", () => {
        render(<FormSubmissionsPage />)
        expect(screen.getByText("Synthetic Applicant")).toBeInTheDocument()
        expect(screen.getByRole("combobox", { name: "Form" })).toHaveTextContent("Applicant intake")
        expect(screen.queryByText("Ambiguous Match Queue")).not.toBeInTheDocument()
        expect(screen.queryByText("Lead Promotion Queue")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Open Approval Queue" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Keep As Lead" })).not.toBeInTheDocument()
        expect(mocks.candidates).toHaveBeenLastCalledWith(null)
        expect(mocks.resolve).not.toHaveBeenCalled()
    })

    it.each(["surrogate", "egg_donor", "sperm_donor"] as const)("requires the exact Create action to promote %s leads", (lead_kind) => {
        const module = lead_kind === "surrogate" ? "surrogates" : "donors"
        const name = lead_kind === "surrogate" ? "Promote Lead" : lead_kind === "egg_donor" ? "Promote to Egg Donor" : "Promote to Sperm Donor"
        mocks.submissions.mockReturnValue({ data: [{ ...submission(), lead_kind, match_status: "lead_created", intake_lead_id: "lead-1" }], isLoading: false })
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions", `edit_${module}`] } })
        const view = render(<FormSubmissionsPage />)
        expect(screen.getByRole("button", { name })).toBeDisabled()
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions", `create_${module}`] } })
        view.rerender(<FormSubmissionsPage />)
        expect(screen.getByRole("button", { name })).toBeEnabled()
    })

    it("allows an authorized reviewer to resolve an ambiguous submission", async () => {
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions"] } })
        render(<FormSubmissionsPage />)
        expect(screen.getByText("Ambiguous Match Queue")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Keep As Lead" }))
        await waitFor(() => expect(mocks.resolve).toHaveBeenCalledWith({ submissionId: "submission-1", payload: { create_intake_lead: true, review_notes: null } }))
        expect(mocks.refetch).toHaveBeenCalled()
    })

    it("opens the form named in the link", () => {
        mocks.searchParams = new URLSearchParams("form=form-2")
        mocks.forms.mockReturnValue({ data: [{ id: "form-1", name: "Applicant intake" }, { id: "form-2", name: "Donor follow-up" }], isLoading: false, isError: false })
        render(<FormSubmissionsPage />)
        expect(screen.getByRole("combobox", { name: "Form" })).toHaveTextContent("Donor follow-up")
        expect(mocks.submissions).toHaveBeenLastCalledWith("form-2", { limit: 100 })
    })

    it("falls back to the first form when the linked form is not reviewable", () => {
        mocks.searchParams = new URLSearchParams("form=other-org-form")
        render(<FormSubmissionsPage />)
        expect(screen.getByRole("combobox", { name: "Form" })).toHaveTextContent("Applicant intake")
        expect(mocks.submissions).toHaveBeenLastCalledWith("form-1", { limit: 100 })
    })

    it("shows donor review controls only with donor edit access", () => {
        mocks.submissions.mockReturnValue({ data: [{ ...submission(), lead_kind: "egg_donor" }], isLoading: false })
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions", "edit_surrogates"] } })
        const view = render(<FormSubmissionsPage />)
        expect(screen.getByRole("button", { name: "Create Intake Lead" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Link to Donor" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument()
        mocks.access.mockReturnValue({ data: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions", "edit_donors"] } })
        view.rerender(<FormSubmissionsPage />)
        expect(screen.getByRole("button", { name: "Link to Donor" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument()
    })
})
