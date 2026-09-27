import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import ApplicationPage from "@/app/(app)/surrogates/[id]/application/page"

const mocks = vi.hoisted(() => ({ context: vi.fn(), legacy: vi.fn(), scoped: vi.fn(), refetch: vi.fn(), tab: vi.fn() }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }) }))
vi.mock("@/components/ui/tabs", () => ({ TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div> }))
vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({ useSurrogateDetailData: () => mocks.context() }))
vi.mock("@/lib/hooks/use-forms", () => ({ useForms: (enabled: boolean) => mocks.legacy(enabled), useSurrogateApplicationForms: (id: string | null) => mocks.scoped(id) }))
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
        expect(mocks.tab).toHaveBeenLastCalledWith(expect.objectContaining({ formId: "form-1", access: { scoped: true, canEdit: false, canSend: false } }))
    })

    it("requires review and edit together, with sending separate", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 2, permissions: ["view_form_submissions", "review_form_submissions"] }, canEditSurrogate: true })
        render(<ApplicationPage />)
        expect(mocks.tab).toHaveBeenLastCalledWith(expect.objectContaining({ access: { scoped: true, canEdit: true, canSend: false } }))
    })

    it("does not load application metadata without submission view", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 2, permissions: ["edit_surrogates"] }, canEditSurrogate: true })
        render(<ApplicationPage />)
        expect(screen.getByText("Application unavailable")).toBeInTheDocument()
        expect(mocks.scoped).toHaveBeenCalledWith(null)
        expect(mocks.tab).not.toHaveBeenCalled()
    })

    it("renders loading and retryable metadata failure", () => {
        mocks.scoped.mockReturnValue({ isLoading: true })
        const view = render(<ApplicationPage />)
        expect(view.container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument()
        mocks.scoped.mockReturnValue({ isError: true, refetch: mocks.refetch })
        view.rerender(<ApplicationPage />)
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(mocks.refetch).toHaveBeenCalledOnce()
        expect(mocks.tab).not.toHaveBeenCalled()
    })

    it("retains the legacy builder query for version one", () => {
        mocks.context.mockReturnValue({ effectivePermissions: { policy_version: 1, permissions: [] }, canEditSurrogate: true })
        render(<ApplicationPage />)
        expect(mocks.legacy).toHaveBeenCalledWith(true)
        expect(mocks.scoped).toHaveBeenCalledWith(null)
    })
})
