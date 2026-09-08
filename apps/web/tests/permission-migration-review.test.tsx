import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { PermissionMigrationReview } from "@/components/permissions/permission-migration-review"
import * as scopes from "@/lib/api/record-scopes"

vi.mock("@/lib/api/record-scopes", async (original) => ({ ...await original<typeof scopes>(), reviewHandoff: vi.fn(), reviewPoolGrant: vi.fn() }))
vi.mock("@/components/app-link", () => ({ default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a> }))
vi.mock("@/lib/hooks/use-pipelines", () => ({ usePipelines: () => ({ data: [], isLoading: false }) }))
const candidate: scopes.HandoffCandidate = { kind: "surrogate", record_id: "record-1", record_number: "S10001", fingerprint: "record-fingerprint", phase_requires_review: true }
const review: scopes.ScopeMigrationReview = { ready: false, collaborators: [], handoff_candidates: [candidate], unresolved_handoffs: [candidate], missing_approval_gate_pipeline_ids: [], legacy_pool_grants: [] }
function choose(label: string, option: string) { fireEvent.click(screen.getByRole("combobox", { name: label })); const item = screen.getByRole("option", { name: option }); fireEvent.mouseMove(item); fireEvent.click(item) }

describe("record scope migration review", () => {
    beforeEach(() => { vi.mocked(scopes.reviewHandoff).mockReset().mockResolvedValue({}); vi.mocked(scopes.reviewPoolGrant).mockReset().mockResolvedValue({}) })
    it("requires an evidence reference and approval phase for an uncertain historical record", async () => {
        const onResolved = vi.fn()
        render(<PermissionMigrationReview review={review} members={[]} onResolved={onResolved} />)
        expect(screen.getByRole("link", { name: "S10001" })).toHaveAttribute("href", "/surrogates/record-1")
        const save = screen.getByRole("button", { name: "Save record review" })
        expect(save).toBeDisabled()
        choose("Historical Intake owner", "No verified Intake owner")
        fireEvent.change(screen.getByRole("textbox", { name: "Evidence reference" }), { target: { value: "Audit entry 42" } })
        expect(save).toBeDisabled()
        choose("Verified approval phase", "After approval")
        expect(save).toBeEnabled()
        fireEvent.click(save)
        await waitFor(() => expect(scopes.reviewHandoff).toHaveBeenCalledWith(candidate, { decision: "no_verified_owner", evidence_reference: "Audit entry 42", resolved_phase: "post_approval" }))
        expect(onResolved).toHaveBeenCalledOnce()
    })

    it("keeps a failed historical review available for correction", async () => {
        vi.mocked(scopes.reviewHandoff).mockRejectedValue(new Error("Record changed; review again"))
        const onResolved = vi.fn()
        render(<PermissionMigrationReview review={review} members={[]} onResolved={onResolved} />)
        choose("Historical Intake owner", "No verified Intake owner")
        choose("Verified approval phase", "Before approval")
        fireEvent.change(screen.getByRole("textbox", { name: "Evidence reference" }), { target: { value: "Review 42" } })
        fireEvent.click(screen.getByRole("button", { name: "Save record review" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("Record changed")
        expect(screen.getByRole("textbox", { name: "Evidence reference" })).toHaveValue("Review 42")
        expect(onResolved).not.toHaveBeenCalled()
    })

    it("does not remove a legacy pool until an explicit resolution is saved", async () => {
        const grant = { id: "pool-1", source_user_id: "source-1", grantee_user_id: "grantee-1", current_record_ids: ["record-1"], fingerprint: "pool-fingerprint" }
        render(<PermissionMigrationReview review={{ ...review, unresolved_handoffs: [], legacy_pool_grants: [grant] }} members={[]} onResolved={vi.fn()} />)
        expect(screen.getByRole("button", { name: "Save pool resolution" })).toBeDisabled()
        choose("Pool resolution", "Remove shared pool access")
        expect(scopes.reviewPoolGrant).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole("button", { name: "Save pool resolution" }))
        await waitFor(() => expect(scopes.reviewPoolGrant).toHaveBeenCalledWith(grant, "remove", undefined))
    })
})
