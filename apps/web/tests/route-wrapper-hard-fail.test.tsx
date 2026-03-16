import { describe, expect, it, beforeEach, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const mockNotFound = vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND")
})
const mockGetServerRouteResourceStatus = vi.fn()

vi.mock("next/navigation", async () => {
    const actual = await vi.importActual("next/navigation")
    return {
        ...actual,
        notFound: () => mockNotFound(),
    }
})

vi.mock("@/lib/server-route-resource", () => ({
    getServerRouteResourceStatus: (...args: unknown[]) =>
        mockGetServerRouteResourceStatus(...args),
}))

vi.mock("../app/(app)/automation/campaigns/[id]/page.client", () => ({
    default: () => <div>Campaign Client</div>,
}))

vi.mock("../app/(app)/automation/forms/[id]/page.client", () => ({
    default: () => <div>Form Builder Client</div>,
}))

vi.mock("../app/(app)/intended-parents/matches/[id]/page.client", () => ({
    default: () => <div>Match Client</div>,
}))

vi.mock("../app/(app)/settings/team/members/[id]/page.client", () => ({
    default: () => <div>Member Client</div>,
}))

vi.mock("../app/(app)/settings/team/roles/[role]/page.client", () => ({
    default: () => <div>Role Client</div>,
}))

vi.mock("../app/ops/templates/email/[id]/page.client", () => ({
    default: () => <div>Email Template Client</div>,
}))

vi.mock("../app/ops/templates/forms/[id]/page.client", () => ({
    default: () => <div>Form Template Client</div>,
}))

vi.mock("../app/ops/templates/workflows/[id]/page.client", () => ({
    default: () => <div>Workflow Template Client</div>,
}))

import CampaignDetailPage from "../app/(app)/automation/campaigns/[id]/page"
import FormBuilderPage from "../app/(app)/automation/forms/[id]/page"
import MatchDetailPage from "../app/(app)/intended-parents/matches/[id]/page"
import MemberDetailPage from "../app/(app)/settings/team/members/[id]/page"
import RoleDetailPage from "../app/(app)/settings/team/roles/[role]/page"
import PlatformEmailTemplatePage from "../app/ops/templates/email/[id]/page"
import PlatformFormTemplatePage from "../app/ops/templates/forms/[id]/page"
import PlatformWorkflowTemplatePage from "../app/ops/templates/workflows/[id]/page"

describe("route wrappers", () => {
    beforeEach(() => {
        mockNotFound.mockClear()
        mockGetServerRouteResourceStatus.mockReset()
        mockGetServerRouteResourceStatus.mockResolvedValue("ok")
    })

    it("campaign detail hard-404s missing campaigns", async () => {
        mockGetServerRouteResourceStatus.mockResolvedValueOnce("not_found")

        await expect(
            CampaignDetailPage({ params: Promise.resolve({ id: "camp-1" }) }),
        ).rejects.toThrow("NEXT_NOT_FOUND")
        expect(mockGetServerRouteResourceStatus).toHaveBeenCalledWith("/campaigns/camp-1")
    })

    it("form builder bypasses the route check for new forms", async () => {
        const ui = await FormBuilderPage({
            params: Promise.resolve({ id: "new" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).not.toHaveBeenCalled()
        expect(screen.getByText("Form Builder Client")).toBeInTheDocument()
    })

    it("match detail checks the match resource", async () => {
        const ui = await MatchDetailPage({
            params: Promise.resolve({ id: "match-1" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).toHaveBeenCalledWith("/matches/match-1")
        expect(screen.getByText("Match Client")).toBeInTheDocument()
    })

    it("member detail checks the member resource", async () => {
        const ui = await MemberDetailPage({
            params: Promise.resolve({ id: "member-1" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).toHaveBeenCalledWith(
            "/settings/permissions/members/member-1",
        )
        expect(screen.getByText("Member Client")).toBeInTheDocument()
    })

    it("role detail checks the role resource", async () => {
        const ui = await RoleDetailPage({
            params: Promise.resolve({ role: "admin" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).toHaveBeenCalledWith(
            "/settings/permissions/roles/admin",
        )
        expect(screen.getByText("Role Client")).toBeInTheDocument()
    })

    it("email template bypasses the route check for new templates", async () => {
        const ui = await PlatformEmailTemplatePage({
            params: Promise.resolve({ id: "new" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).not.toHaveBeenCalled()
        expect(screen.getByText("Email Template Client")).toBeInTheDocument()
    })

    it("form template checks the platform form template resource", async () => {
        const ui = await PlatformFormTemplatePage({
            params: Promise.resolve({ id: "tpl-form-1" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).toHaveBeenCalledWith(
            "/platform/templates/forms/tpl-form-1",
        )
        expect(screen.getByText("Form Template Client")).toBeInTheDocument()
    })

    it("workflow template checks the platform workflow template resource", async () => {
        const ui = await PlatformWorkflowTemplatePage({
            params: Promise.resolve({ id: "tpl-workflow-1" }),
        })

        render(ui)
        expect(mockGetServerRouteResourceStatus).toHaveBeenCalledWith(
            "/platform/templates/workflows/tpl-workflow-1",
        )
        expect(screen.getByText("Workflow Template Client")).toBeInTheDocument()
    })
})
