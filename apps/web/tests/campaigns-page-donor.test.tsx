import type { PropsWithChildren, ReactNode } from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { useQuery } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import CampaignsPage from "../app/(app)/automation/campaigns/page"

const mockCreateCampaign = vi.fn()
const mockPreviewFilters = vi.fn()
const mockSendCampaign = vi.fn()
const mockPreviewFiltersReset = vi.fn()
let mockPermissions = new Set(["manage_email_templates"])
let mockEmptyCampaigns = false
let mockMessagingTemplates: Array<{ id: string; name: string; body: string }> = []

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
    DialogBody: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogFooter: ({ children, start }: PropsWithChildren<{ start?: ReactNode }>) => (
        <div>
            {start}
            {children}
        </div>
    ),
}))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        isRetrying: false,
        retry: vi.fn(),
        can: (permission: string) => mockPermissions.has(permission),
    }),
}))

vi.mock("@/lib/hooks/use-campaigns", () => ({
    useCampaigns: () => ({
        data: mockEmptyCampaigns ? [] : [{
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
    useCampaignPreview: (id: string | undefined, options?: { enabled?: boolean }) => ({
        data: id && options?.enabled !== false ? { total_count: 4, sample_recipients: [] } : undefined,
        isLoading: false,
    }),
    usePreviewFilters: () => ({
        mutate: mockPreviewFilters,
        reset: mockPreviewFiltersReset,
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
                return { data: mockMessagingTemplates, isLoading: false } as never
            }
            return { data: [], isLoading: false } as never
        })
        mockPermissions = new Set(["manage_email_templates"])
        mockEmptyCampaigns = false
        mockMessagingTemplates = [{
            id: "message-template-1",
            name: "Promotional message",
            body: "Hello",
        }]
    })

    const openWizardToReview = () => {
        render(<CampaignsPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Campaign" })[0]!)
        fireEvent.change(screen.getByLabelText("Campaign name"), {
            target: { value: "Egg donor outreach" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.change(screen.getByRole("combobox", { name: "Recipient type" }), {
            target: { value: "egg_donor" },
        })
        fireEvent.click(screen.getByRole("checkbox", { name: "Egg Screening" }))
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.change(screen.getByRole("combobox", { name: "Email template" }), {
            target: { value: "template-1" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
    }

    it("shows a friendly donor label in the campaign list", () => {
        render(<CampaignsPage />)

        expect(screen.getAllByText("Egg Donors").length).toBeGreaterThan(0)
    })

    it("labels the four wizard steps and marks the current one", () => {
        render(<CampaignsPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Campaign" })[0]!)

        const progress = screen.getByRole("list", { name: "Progress" })
        const steps = within(progress).getAllByRole("listitem")
        expect(steps.map((step) => step.textContent)).toEqual([
            "1Setup (current step)",
            "2Audience",
            "3Content",
            "4Review & send",
        ])
        expect(steps[0]).toHaveAttribute("aria-current", "step")
    })

    it("uses the exact egg donor pipeline for filters, preview, and creation", async () => {
        openWizardToReview()

        expect(vi.mocked(useQuery).mock.calls.some(([options]) =>
            options.queryKey[0] === "defaultPipeline" && options.queryKey[1] === "egg_donor"
        )).toBe(true)
        expect(mockPreviewFilters).toHaveBeenCalledWith({
            channel: "email",
            recipientType: "egg_donor",
            filterCriteria: { stage_ids: ["egg-stage-1"] },
            includeUnsubscribed: false,
        })
        expect(screen.getByText("Egg Donors · Egg Screening · All states · Unsubscribed excluded")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Maya Donor" })).toHaveAttribute(
            "href",
            "/donors/donor-egg-1",
        )

        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

        await waitFor(() => {
            expect(mockCreateCampaign).toHaveBeenCalledWith(expect.objectContaining({
                name: "Egg donor outreach",
                recipient_type: "egg_donor",
                filter_criteria: { stage_ids: ["egg-stage-1"] },
            }))
        })
    })

    it("saves a draft by default and never sends without a choice", async () => {
        openWizardToReview()

        expect(screen.getByRole("radio", { name: "Save as draft" })).toBeChecked()
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

        await waitFor(() => expect(mockCreateCampaign).toHaveBeenCalledTimes(1))
        expect(mockCreateCampaign.mock.calls[0]?.[0]).not.toHaveProperty("scheduled_at")
        expect(mockSendCampaign).not.toHaveBeenCalled()
    })

    it("asks for confirmation with the recipient count before sending now", async () => {
        openWizardToReview()

        fireEvent.click(screen.getByRole("radio", { name: "Send now" }))
        fireEvent.click(screen.getByRole("button", { name: "Send Campaign" }))

        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Send to 2 recipients now?")).toBeInTheDocument()
        expect(mockCreateCampaign).not.toHaveBeenCalled()

        fireEvent.click(within(confirm).getByRole("button", { name: "Send now" }))

        await waitFor(() => {
            expect(mockSendCampaign).toHaveBeenCalledWith({ id: "campaign-new", sendNow: true })
        })
    })

    it("keeps Schedule disabled until a send time is chosen", () => {
        openWizardToReview()

        fireEvent.click(screen.getByRole("radio", { name: "Schedule for later" }))

        expect(screen.getByRole("button", { name: "Schedule Campaign" })).toBeDisabled()
        expect(screen.queryByText(/ready to/i)).not.toBeInTheDocument()
    })

    it("does not offer donor recipient types for messaging campaigns", () => {
        render(<CampaignsPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Campaign" })[0]!)

        fireEvent.change(screen.getByRole("combobox", { name: "Channel" }), { target: { value: "messaging" } })
        fireEvent.change(screen.getByLabelText("Campaign name"), {
            target: { value: "Messaging campaign" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))

        expect(screen.queryByRole("option", { name: "Egg Donors" })).not.toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Sperm Donors" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        expect(screen.getByRole("combobox", { name: "SMS template" })).toBeInTheDocument()
    })

    it("explains an empty SMS template list instead of showing an empty select", () => {
        mockMessagingTemplates = []
        render(<CampaignsPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Campaign" })[0]!)

        fireEvent.change(screen.getByRole("combobox", { name: "Channel" }), { target: { value: "messaging" } })
        fireEvent.change(screen.getByLabelText("Campaign name"), { target: { value: "SMS" } })
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        fireEvent.click(screen.getByRole("button", { name: "Next" }))

        expect(screen.getByText("No promotional SMS templates")).toBeInTheDocument()
        expect(screen.queryByRole("combobox", { name: "SMS template" })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Next" })).toBeDisabled()
    })

    it("loads promotional SMS templates only for the SMS path of an open wizard", () => {
        vi.mocked(useQuery).mockClear()
        render(<CampaignsPage />)

        const messagingCalls = vi.mocked(useQuery).mock.calls.filter(
            ([options]) => options.queryKey[0] === "messaging-templates",
        )
        expect(messagingCalls.length).toBeGreaterThan(0)
        expect(messagingCalls.every(([options]) => options.enabled === false)).toBe(true)
    })

    it("hides create and manage actions without the campaign permission", async () => {
        mockPermissions = new Set()
        render(<CampaignsPage />)

        expect(screen.queryByRole("button", { name: "Create Campaign" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Actions for Egg donor screening" }))
        expect(await screen.findByRole("menuitem", { name: "View Details" })).toBeInTheDocument()
        expect(screen.queryByRole("menuitem", { name: "Send Now" })).not.toBeInTheDocument()
        expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument()
        expect(screen.queryByRole("menuitem", { name: "Duplicate" })).not.toBeInTheDocument()
        expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument()
    })

    it("shows an empty state without create copy for roles that cannot create", () => {
        mockEmptyCampaigns = true
        mockPermissions = new Set()
        const view = render(<CampaignsPage />)

        expect(screen.getByRole("heading", { name: "No campaigns yet", level: 3 })).toBeInTheDocument()
        expect(screen.queryByText(/create your first campaign/i)).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Create Campaign" })).not.toBeInTheDocument()

        view.unmount()
        mockPermissions = new Set(["manage_email_templates"])
        render(<CampaignsPage />)
        expect(screen.getAllByRole("button", { name: "Create Campaign" })).toHaveLength(2)
    })

    it("shows the recipient count in the list Send Now confirmation", async () => {
        render(<CampaignsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Actions for Egg donor screening" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Send Now" }))

        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Send to 4 recipients now?")).toBeInTheDocument()
    })
})
