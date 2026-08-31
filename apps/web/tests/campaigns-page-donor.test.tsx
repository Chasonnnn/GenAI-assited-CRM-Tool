import type { PropsWithChildren } from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useQuery } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import CampaignsPage from "../app/(app)/automation/campaigns/page"

const mockCreateCampaign = vi.fn()
const mockPreviewFilters = vi.fn()
const mockSendCampaign = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@tanstack/react-query", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@tanstack/react-query")>()
    return { ...actual, useQuery: vi.fn() }
})

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
        "aria-label": ariaLabel,
    }: PropsWithChildren<{
        value?: string
        onValueChange: (value: string) => void
        "aria-label"?: string
    }>) => (
        <select
            value={value ?? ""}
            onChange={(event) => onValueChange(event.target.value)}
            aria-label={ariaLabel}
        >
            <option value="">Select</option>
            {children}
        </select>
    ),
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: PropsWithChildren) => <>{children}</>,
    SelectItem: ({ value, children }: PropsWithChildren<{ value: string }>) => (
        <option value={value}>{children}</option>
    ),
}))

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ open, children }: PropsWithChildren<{ open?: boolean }>) => open ? <div>{children}</div> : null,
    DialogContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogHeader: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogTitle: ({ children }: PropsWithChildren) => <h2>{children}</h2>,
    DialogDescription: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogFooter: ({ children }: PropsWithChildren) => <div>{children}</div>,
}))

vi.mock("@/lib/hooks/use-campaigns", () => ({
    useCampaigns: () => ({
        data: [{
            id: "campaign-egg",
            name: "Egg donor screening",
            channel: "email",
            email_template_name: "Screening reminder",
            message_template_name: null,
            recipient_type: "egg_donor",
            status: "draft",
            scheduled_at: null,
            include_unsubscribed: false,
            total_recipients: 4,
            sent_count: 0,
            delivered_count: 0,
            failed_count: 0,
            opened_count: 0,
            clicked_count: 0,
            created_at: "2026-08-29T12:00:00Z",
        }],
        isLoading: false,
    }),
    useCreateCampaign: () => ({ mutateAsync: mockCreateCampaign, isPending: false }),
    useDeleteCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDuplicateCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCancelCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSendCampaign: () => ({ mutateAsync: mockSendCampaign, isPending: false }),
    usePreviewFilters: () => ({
        mutate: mockPreviewFilters,
        data: {
            total_count: 2,
            sample_recipients: [{
                entity_type: "egg_donor",
                entity_id: "donor-egg-1",
                email: "maya@example.com",
                phone_last4: null,
                name: "Maya Donor",
                stage: "Egg Screening",
            }],
        },
        isPending: false,
    }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: () => ({
        data: [{ id: "template-1", name: "Screening reminder", subject: "Hello" }],
    }),
}))

vi.mock("@/lib/hooks/use-metadata", () => ({
    useIntendedParentStatuses: () => ({ data: { statuses: [] } }),
}))

vi.mock("@/lib/api/twilio", () => ({
    listMessagingTemplates: vi.fn().mockResolvedValue([]),
}))

describe("donor campaign creation", () => {
    beforeEach(() => {
        mockCreateCampaign.mockReset().mockResolvedValue({ id: "campaign-new" })
        mockPreviewFilters.mockReset()
        mockSendCampaign.mockReset().mockResolvedValue({})
        vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
            if (queryKey[0] === "defaultPipeline") {
                const entityType = queryKey[1]
                return {
                    data: {
                        stages: entityType === "egg_donor"
                            ? [{
                                id: "egg-stage-1",
                                label: "Egg Screening",
                                color: "#7C3AED",
                                stage_key: "pre_screening",
                                stage_type: "intake",
                                category: "intake",
                                is_active: true,
                            }]
                            : [{
                                id: "surrogate-stage-1",
                                label: "Surrogate Intake",
                                color: "#0EA5E9",
                                stage_key: "new",
                                stage_type: "intake",
                                category: "intake",
                                is_active: true,
                            }],
                    },
                    isLoading: false,
                } as never
            }
            if (queryKey[0] === "messaging-templates") {
                return {
                    data: [{
                        id: "message-template-1",
                        name: "Promotional message",
                        body: "Hello",
                    }],
                    isLoading: false,
                } as never
            }
            return { data: [], isLoading: false } as never
        })
    })

    it("shows a friendly donor label in the campaign list", () => {
        render(<CampaignsPage />)

        expect(screen.getAllByText("Egg Donors").length).toBeGreaterThan(0)
    })

    it("uses the exact egg donor pipeline for filters, preview, and creation", async () => {
        render(<CampaignsPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Campaign" })[0]!)

        fireEvent.change(screen.getByLabelText("Campaign Name *"), {
            target: { value: "Egg donor outreach" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.change(screen.getByRole("combobox", { name: "Email template" }), {
            target: { value: "template-1" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.change(screen.getByRole("combobox", { name: "Recipient type" }), {
            target: { value: "egg_donor" },
        })

        expect(screen.getByText("Egg Screening")).toBeInTheDocument()
        expect(screen.queryByText("Surrogate Intake")).not.toBeInTheDocument()
        expect(vi.mocked(useQuery).mock.calls.some(([options]) =>
            options.queryKey[0] === "defaultPipeline" && options.queryKey[1] === "egg_donor"
        )).toBe(true)

        fireEvent.click(screen.getByRole("checkbox", { name: "Egg Screening" }))
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.click(screen.getByRole("button", { name: "Next" }))

        expect(screen.getAllByText("Egg Donors").length).toBeGreaterThan(0)
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        expect(mockPreviewFilters).toHaveBeenCalledWith({
            channel: "email",
            recipientType: "egg_donor",
            filterCriteria: { stage_ids: ["egg-stage-1"] },
            includeUnsubscribed: false,
        })
        expect(screen.getByRole("link", { name: "Maya Donor" })).toHaveAttribute(
            "href",
            "/donors/donor-egg-1",
        )

        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.click(screen.getByRole("button", { name: "Send Campaign" }))

        await waitFor(() => {
            expect(mockCreateCampaign).toHaveBeenCalledWith(expect.objectContaining({
                name: "Egg donor outreach",
                recipient_type: "egg_donor",
                filter_criteria: { stage_ids: ["egg-stage-1"] },
            }))
        })
    })

    it("does not offer donor recipient types for messaging campaigns", () => {
        render(<CampaignsPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Campaign" })[0]!)

        fireEvent.change(screen.getByRole("combobox"), { target: { value: "messaging" } })
        fireEvent.change(screen.getByLabelText("Campaign Name *"), {
            target: { value: "Messaging campaign" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.change(screen.getByRole("combobox", { name: "Email template" }), {
            target: { value: "message-template-1" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))

        expect(screen.queryByRole("option", { name: "Egg Donors" })).not.toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Sperm Donors" })).not.toBeInTheDocument()
    })
})
