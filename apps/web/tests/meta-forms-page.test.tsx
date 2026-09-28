import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import MetaFormsPage from "../app/(app)/settings/integrations/meta/forms/page"
import { ApiError } from "@/lib/api"

let mockPermissions: string[] = ["manage_meta_leads"]
const mockUseMetaForms = vi.fn()
const mockUseSyncMetaForms = vi.fn()
const mockUseDeleteMetaForm = vi.fn()
const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockPermissions.includes(permission),
    }),
}))

vi.mock("@/lib/hooks/use-meta-forms", () => ({
    useMetaForms: () => mockUseMetaForms(),
    useSyncMetaForms: () => mockUseSyncMetaForms(),
    useDeleteMetaForm: () => mockUseDeleteMetaForm(),
}))

vi.mock("@/components/ui/toast", () => ({ toast: mockToast }))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
    usePathname: () => "/settings/integrations/meta/forms",
    useSearchParams: () => new URLSearchParams(),
}))

const FORM = {
    id: "form-1",
    form_external_id: "ext-1",
    form_name: "Spring intake",
    page_id: "page-1",
    page_name: "Agency page",
    lead_kind: "surrogate",
    mapping_status: "mapped",
    unconverted_leads: 0,
    last_lead_at: null,
}

describe("MetaFormsPage", () => {
    beforeEach(() => {
        mockPermissions = ["manage_meta_leads"]
        mockToast.success.mockReset()
        mockToast.error.mockReset()
        mockUseMetaForms.mockReset()
        mockUseMetaForms.mockReturnValue({ data: [FORM], isLoading: false })
        mockUseSyncMetaForms.mockReturnValue({ mutate: vi.fn(), isPending: false })
        mockUseDeleteMetaForm.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    })

    it("shows the restricted state and requests no forms without manage_meta_leads", () => {
        mockPermissions = ["manage_integrations"]

        render(<MetaFormsPage />)

        expect(screen.getByRole("heading", { name: "Permission required" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Sync forms/ })).not.toBeInTheDocument()
        expect(mockUseMetaForms).not.toHaveBeenCalled()
    })

    it("shows a load error instead of the empty state when forms fail to load", () => {
        const refetch = vi.fn()
        mockUseMetaForms.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, "Internal Server Error", "boom secret detail"),
            isFetching: false,
            refetch,
        })

        render(<MetaFormsPage />)

        expect(screen.getByText("Couldn't load lead forms")).toBeInTheDocument()
        expect(screen.queryByText("No lead forms")).not.toBeInTheDocument()
        expect(screen.queryByText(/boom secret detail/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalled()
    })

    it("keeps the loaded forms when a background refetch fails", () => {
        mockUseMetaForms.mockReturnValue({
            data: [FORM],
            isLoading: false,
            isError: true,
            error: new ApiError(500, "Internal Server Error", "boom"),
            isFetching: false,
            refetch: vi.fn(),
        })

        render(<MetaFormsPage />)

        expect(screen.getByText("Spring intake")).toBeInTheDocument()
        expect(screen.queryByText("Couldn't load lead forms")).not.toBeInTheDocument()
    })

    it("shows the empty state without helper copy when no forms are synced", () => {
        mockUseMetaForms.mockReturnValue({ data: [], isLoading: false, isError: false })

        render(<MetaFormsPage />)

        expect(screen.getByText("No lead forms")).toBeInTheDocument()
        expect(screen.queryByText(/Click Sync forms/)).not.toBeInTheDocument()
        expect(screen.getAllByRole("button", { name: /Sync forms/ })).toHaveLength(1)
    })

    it("confirms Sync forms success with a toast", () => {
        const mutate = vi.fn((_input: unknown, options: { onSuccess: () => void }) => options.onSuccess())
        mockUseSyncMetaForms.mockReturnValue({ mutate, isPending: false })

        render(<MetaFormsPage />)
        fireEvent.click(screen.getByRole("button", { name: /Sync forms/ }))

        expect(mockToast.success).toHaveBeenCalledWith("Forms synced")
    })

    it("shows a sanitized toast when Sync forms fails", () => {
        const mutate = vi.fn((_input: unknown, options: { onError: (error: unknown) => void }) =>
            options.onError(new ApiError(502, "Bad Gateway", "graph.facebook.com returned OAuthException")),
        )
        mockUseSyncMetaForms.mockReturnValue({ mutate, isPending: false })

        render(<MetaFormsPage />)
        fireEvent.click(screen.getByRole("button", { name: /Sync forms/ }))

        expect(mockToast.error).toHaveBeenCalledWith("Couldn't sync forms. Try again.")
    })

    it("deletes a form from a destructive confirmation that names it", async () => {
        const deleteForm = vi.fn().mockResolvedValue(undefined)
        mockUseDeleteMetaForm.mockReturnValue({ mutateAsync: deleteForm, isPending: false })

        render(<MetaFormsPage />)
        fireEvent.click(screen.getByRole("button", { name: "Delete" }))

        const dialog = await screen.findByRole("alertdialog", { name: "Delete Spring intake?" })
        const confirm = within(dialog).getByRole("button", { name: "Delete form" })
        expect(confirm).toHaveClass("bg-destructive")
        fireEvent.click(confirm)

        await waitFor(() => expect(deleteForm).toHaveBeenCalledWith("form-1"))
        await waitFor(() => expect(mockToast.success).toHaveBeenCalledWith("Form deleted"))
    })
})
