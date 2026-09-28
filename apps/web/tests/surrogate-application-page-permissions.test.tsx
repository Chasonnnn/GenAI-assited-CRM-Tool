import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import ApplicationPage from "@/app/(app)/surrogates/[id]/application/page"
import { ApiError } from "@/lib/api"

const mocks = vi.hoisted(() => ({ context: vi.fn(), legacy: vi.fn(), scoped: vi.fn(), refetch: vi.fn(), tab: vi.fn() }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }), useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }))
vi.mock("@/components/ui/tabs", () => ({ TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div> }))
vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({ useSurrogateDetailData: () => mocks.context() }))
vi.mock("@/lib/hooks/use-forms", () => ({ useForms: (options: { enabled?: boolean }) => mocks.legacy(options.enabled), useSurrogateApplicationForms: (id: string | null) => mocks.scoped(id) }))
vi.mock("@/components/surrogates/SurrogateApplicationTab", () => ({ SurrogateApplicationTab: (props: unknown) => { mocks.tab(props); return <div>Application content</div> } }))

describe("scoped application page", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 2, permissions: ["view_form_submissions"] }, canEditSurrogate: false })
        mocks.legacy.mockReturnValue({ data: [] })
        mocks.scoped.mockReturnValue({ data: [{ id: "form-1", name: "Application", status: "published", is_default_surrogate_application: true }], refetch: mocks.refetch })
    })

    it("loads record-scoped metadata without requesting builder access", () => {
        render(<ApplicationPage />)
        expect(mocks.legacy).toHaveBeenCalledWith(false)
        expect(mocks.scoped).toHaveBeenCalledWith("surrogate-1")
        expect(mocks.tab).toHaveBeenLastCalledWith(expect.objectContaining({ formId: "form-1", formsAccess: "ready", access: { scoped: true, canEdit: false, canSend: false } }))
    })

    it("requires review and edit together, with sending separate", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions"] }, canEditSurrogate: true })
        render(<ApplicationPage />)
        expect(mocks.tab).toHaveBeenLastCalledWith(expect.objectContaining({ access: { scoped: true, canEdit: true, canSend: false } }))
    })

    it("does not load application metadata without submission view", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 2, permissions: ["edit_surrogates"] }, canEditSurrogate: true })
        render(<ApplicationPage />)
        expect(screen.getByRole("heading", { name: "No access to application" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Overview" })).toHaveAttribute("href", "/surrogates/surrogate-1")
        expect(mocks.scoped).toHaveBeenCalledWith(null)
        expect(mocks.tab).not.toHaveBeenCalled()
    })

    it("renders loading, then passes a retryable metadata failure to the tab", () => {
        mocks.scoped.mockReturnValue({ isLoading: true })
        const view = render(<ApplicationPage />)
        expect(view.container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument()
        expect(mocks.tab).not.toHaveBeenCalled()
        mocks.scoped.mockReturnValue({ isError: true, error: new ApiError(500, "Internal Server Error"), refetch: mocks.refetch })
        view.rerender(<ApplicationPage />)
        const props = mocks.tab.mock.lastCall?.[0] as { formsAccess: string; onRetryForms: () => void }
        expect(props.formsAccess).toBe("error")
        props.onRetryForms()
        expect(mocks.refetch).toHaveBeenCalledOnce()
    })

    it("passes a forbidden forms list to the tab under version one", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 1, permissions: [] }, canEditSurrogate: true })
        mocks.legacy.mockReturnValue({ isError: true, error: new ApiError(403, "Forbidden"), refetch: mocks.refetch })
        render(<ApplicationPage />)
        expect(mocks.tab).toHaveBeenLastCalledWith(expect.objectContaining({ formsAccess: "forbidden", access: { scoped: false, canEdit: true, canSend: true } }))
    })

    it("retains the legacy builder query for version one", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 1, permissions: [] }, canEditSurrogate: true })
        render(<ApplicationPage />)
        expect(mocks.legacy).toHaveBeenCalledWith(true)
        expect(mocks.scoped).toHaveBeenCalledWith(null)
    })
})
