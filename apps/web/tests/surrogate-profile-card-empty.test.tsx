import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { ProfileCard } from "@/components/surrogates/profile/ProfileCard"

const state = vi.hoisted(() => ({
    profile: null as Record<string, unknown> | null,
    enterEditMode: vi.fn(),
    syncProfile: vi.fn(),
    exportProfile: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    useSearchParams: () => new URLSearchParams("return_to=%2Fsurrogates"),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
    usePathname: () => "/surrogates/sur-1/profile",
}))

vi.mock("@/components/surrogates/profile/ProfileCard/context", () => ({
    ProfileCardProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
    useProfileCardData: () => ({
        surrogateId: "sur-1",
        profile: state.profile,
        isLoading: false,
        error: null,
    }),
    useProfileCardMode: () => ({ mode: { type: "view" }, enterEditMode: state.enterEditMode }),
    useProfileCardEdits: () => ({ editedFields: {}, setFieldValue: vi.fn() }),
    useProfileCardActions: () => ({
        cancelAllChanges: vi.fn(),
        syncProfile: state.syncProfile,
        exportProfile: state.exportProfile,
        isSyncing: false,
        isExporting: false,
    }),
}))

vi.mock("@/components/surrogates/profile/ProfileCard/Section", () => ({
    Section: ({ title, children }: { title: string; children?: ReactNode }) => (
        <section aria-label={title}>{children}</section>
    ),
}))

vi.mock("@/components/surrogates/profile/ProfileCard/SaveBar", () => ({
    SaveBar: () => null,
}))

describe("ProfileCard without an application", () => {
    beforeEach(() => {
        state.profile = {
            base_submission_id: null,
            merged_view: { full_name: "QA Surrogate" },
            base_answers: {},
            schema_snapshot: null,
        }
    })

    it("hides Export, Sync and Edit and links to the Application tab", () => {
        render(<ProfileCard surrogateId="sur-1" />)

        expect(screen.getByRole("heading", { name: "No application submitted" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /export/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /sync/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Open Application" })).toHaveAttribute(
            "href",
            "/surrogates/sur-1/application?return_to=%2Fsurrogates",
        )
    })

    it("keeps Export, Sync and Edit once an application is submitted", () => {
        state.profile = {
            base_submission_id: "submission-1",
            merged_view: { full_name: "QA Surrogate" },
            base_answers: {},
            schema_snapshot: { pages: [] },
        }

        render(<ProfileCard surrogateId="sur-1" />)

        expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /sync/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument()
        expect(screen.queryByText("No application submitted")).not.toBeInTheDocument()
    })
})
