import type { ReactNode } from "react"
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { TasksApprovalsSection } from "@/components/tasks/TasksApprovalsSection"
import type { StatusChangeRequestDetail } from "@/lib/api/status-change-requests"

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/lib/hooks/use-status-change-requests", () => ({
    useApproveStatusChangeRequest: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRejectStatusChangeRequest: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-import", () => ({
    useApproveImport: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRejectImport: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRunImportInline: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-tasks", () => ({
    useResolveWorkflowApproval: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function statusRequest(
    entityType: StatusChangeRequestDetail["request"]["entity_type"],
    entityId: string,
): StatusChangeRequestDetail {
    return {
        request: {
            id: `req-${entityId}`,
            organization_id: "org-1",
            entity_type: entityType,
            entity_id: entityId,
            target_stage_id: "stage-1",
            target_status: null,
            effective_at: "2026-09-01T00:00:00Z",
            reason: "Needs rescreening",
            requested_by_user_id: "u2",
            requested_at: "2026-09-01T00:00:00Z",
            status: "pending",
            approved_by_user_id: null,
            approved_at: null,
            rejected_by_user_id: null,
            rejected_at: null,
            cancelled_by_user_id: null,
            cancelled_at: null,
        },
        entity_name: entityType === "donor" ? "Maya Donor" : "Jane Applicant",
        entity_number: entityType === "donor" ? "D10001" : "S10001",
        requester_name: "Case Manager",
        target_stage_label: "Contacted",
        current_stage_label: "Pre-Screening",
    }
}

describe("TasksApprovalsSection donor stage requests", () => {
    it("links donor stage regression requests to the donor record", () => {
        render(
            <TasksApprovalsSection
                pendingApprovals={[]}
                pendingStatusRequests={[
                    statusRequest("donor", "donor-1"),
                    statusRequest("surrogate", "surrogate-1"),
                ]}
                pendingImportApprovals={[]}
                loadingApprovals={false}
                loadingStatusRequests={false}
                loadingImportApprovals={false}
                onResolvedStatusRequests={() => {}}
                onResolvedImportApprovals={() => {}}
                currentUserId="u1"
            />,
        )

        expect(screen.getAllByText("Stage Regression Request")).toHaveLength(2)
        expect(screen.getByRole("link", { name: "Maya Donor (D10001)" })).toHaveAttribute(
            "href",
            "/donors/donor-1",
        )
        expect(screen.getByRole("link", { name: "Jane Applicant (S10001)" })).toHaveAttribute(
            "href",
            "/surrogates/surrogate-1",
        )
    })
})
