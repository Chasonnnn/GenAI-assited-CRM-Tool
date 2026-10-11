import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import MessageTemplateEditorPageClient from "@/app/(app)/automation/message-templates/[key]/page.client"
import MessageTemplatesPage from "@/app/(app)/automation/message-templates/page"
import { SendTestMessageDialog } from "@/components/messaging/send-test-message-dialog"
import { TestPhonesCard } from "@/components/messaging/test-phones-card"
import type { MessagingTemplateVersion, MessagingTestPhone, TwilioReadiness } from "@/lib/api/twilio"

const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockParams = { key: "family-1" }
const mockAccess = vi.fn()
const mockVersions = vi.fn()
const mockUsage = vi.fn()
const mockTestPhones = vi.fn()
const mockCreate = vi.fn()
const mockSaveDraft = vi.fn()
const mockPublish = vi.fn()
const mockSendTest = vi.fn()
const mockAddPhone = vi.fn()
const mockVerifyPhone = vi.fn()
const mockRemovePhone = vi.fn()
const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush, replace: mockReplace, back: vi.fn() }),
    useParams: () => mockParams,
    useSearchParams: () => new URLSearchParams(),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: (...args: unknown[]) => mockToastSuccess(...args),
        error: (...args: unknown[]) => mockToastError(...args),
    },
}))

const mutation = (fn: ReturnType<typeof vi.fn>) => ({ mutateAsync: fn, isPending: false })

vi.mock("@/lib/hooks/use-messaging-templates", () => ({
    useMessagingAccess: () => mockAccess(),
    useMessagingTemplateVersions: () => mockVersions(),
    useMessagingTemplateUsage: () => mockUsage(),
    useMessagingSmsVariables: () => ({
        data: [
            { name: "first_name", description: "Contact first name", sample: "Jane" },
            { name: "org_name", description: "Organization name", sample: "EWI Family Global" },
        ],
    }),
    useMessagingTestPhones: () => mockTestPhones(),
    useCreateMessagingTemplate: () => mutation(mockCreate),
    useSaveMessagingTemplateDraft: () => mutation(mockSaveDraft),
    usePublishMessagingTemplate: () => mutation(mockPublish),
    useSendMessagingTemplateTest: () => mutation(mockSendTest),
    useAddMessagingTestPhone: () => mutation(mockAddPhone),
    useVerifyMessagingTestPhone: () => mutation(mockVerifyPhone),
    useRemoveMessagingTestPhone: () => mutation(mockRemovePhone),
}))

const readiness = {
    gates: [
        { key: "operational_route", label: "Operational route", status: "pass", detail: null, route: "operational" },
        { key: "operational_sender_registration", label: "A2P campaign", status: "pass", detail: null, route: "operational" },
        { key: "promotional_route", label: "Promotional route", status: "pass", detail: null, route: "promotional" },
        { key: "promotional_sender_registration", label: "A2P campaign", status: "fail", detail: "Pending", route: "promotional" },
    ],
} as unknown as TwilioReadiness

vi.mock("@/lib/hooks/use-twilio", () => ({
    useTwilioReadiness: () => ({ data: readiness }),
    useTwilioSettings: () => ({
        data: {
            legal_messaging_brand: "EWI Family Global",
            expected_frequency: "Msg frequency varies",
            support_contact: "(512) 555-0100",
            routes: {
                operational: { sender_phone_masked: "+1 ••• ••• 0100" },
                promotional: { sender_phone_masked: null },
            },
        },
    }),
}))

function version(overrides: Partial<MessagingTemplateVersion>): MessagingTemplateVersion {
    return {
        id: "v1",
        template_key: "family-1",
        version: 1,
        name: "Consultation reminder",
        purpose: "operational",
        body: "Reminder: your call with {{org_name}} is soon.",
        status: "published",
        is_enrollment_confirmation: false,
        content_classification: "no_phi",
        published_at: "2026-10-01T12:00:00Z",
        created_at: "2026-10-01T12:00:00Z",
        ...overrides,
    }
}

const phone = (overrides: Partial<MessagingTestPhone>): MessagingTestPhone => ({
    id: "phone-1",
    label: "My phone",
    phone_last4: "0142",
    verified_at: "2026-10-06T12:00:00Z",
    code_expires_at: null,
    stopped_purposes: [],
    created_by_name: "Jordan Admin",
    created_at: "2026-10-06T12:00:00Z",
    ...overrides,
})

beforeEach(() => {
    vi.clearAllMocks()
    mockParams.key = "family-1"
    mockAccess.mockReturnValue({ loading: false, allowed: true })
    mockVersions.mockReturnValue({
        data: [
            version({ id: "v1", version: 1, status: "published" }),
            version({ id: "v2", version: 2, status: "draft", body: "Reminder: your call is {{first_name}}." }),
            version({
                id: "o1",
                template_key: "family-2",
                name: "Opt-in confirmation",
                body: "EWI Family Global: You're signed up.",
                is_enrollment_confirmation: true,
                created_at: "2026-09-01T12:00:00Z",
            }),
            version({
                id: "p1",
                template_key: "family-3",
                name: "Info session",
                purpose: "promotional",
                status: "draft",
                published_at: null,
                created_at: "2026-08-01T12:00:00Z",
            }),
        ],
        isLoading: false,
        isError: false,
        isFetching: false,
    })
    mockUsage.mockReturnValue({
        data: [{ template_key: "family-1", uses: [{ kind: "workflow", id: "wf-1", name: "Remind before consult" }] }],
    })
    mockTestPhones.mockReturnValue({ data: [phone({})], isLoading: false, isError: false })
})

describe("Message Templates list", () => {
    it("lists one row per template with status, usage, and route readiness", () => {
        render(<MessageTemplatesPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Message Templates" })).toBeInTheDocument()
        const routes = screen.getByRole("status", { name: "Messaging routes" })
        expect(routes).toHaveTextContent("Operational route: ready")
        expect(routes).toHaveTextContent("Promotional route: A2P campaign not ready")

        const rows = screen.getAllByRole("row").slice(1)
        expect(rows).toHaveLength(3)
        expect(within(rows[0]!).getByRole("link", { name: "Consultation reminder" })).toHaveAttribute(
            "href",
            "/automation/message-templates/family-1",
        )
        expect(within(rows[0]!).getByText("Published · v1")).toBeInTheDocument()
        expect(within(rows[0]!).getByText("Draft v2")).toBeInTheDocument()
        expect(within(rows[0]!).getByText("1 workflow")).toBeInTheDocument()
        expect(within(rows[1]!).getByText("Opt-in confirmation", { selector: "[data-slot=badge]" })).toBeInTheDocument()
    })

    it("filters by purpose and search", () => {
        render(<MessageTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Promotional" }))
        expect(screen.getAllByRole("row").slice(1)).toHaveLength(1)
        expect(screen.getByRole("link", { name: "Info session" })).toBeInTheDocument()

        fireEvent.change(screen.getByRole("searchbox", { name: "Search templates" }), { target: { value: "nothing" } })
        expect(screen.getByText("No matching templates")).toBeInTheDocument()
    })

    it("shows the empty, error, and restricted states", () => {
        mockVersions.mockReturnValue({ data: [], isLoading: false, isError: false, isFetching: false })
        const { unmount } = render(<MessageTemplatesPage />)
        expect(screen.getByText("No message templates")).toBeInTheDocument()
        unmount()

        mockVersions.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error("down"), refetch: vi.fn(), isFetching: false })
        const errored = render(<MessageTemplatesPage />)
        expect(screen.getByText("Couldn't load message templates")).toBeInTheDocument()
        errored.unmount()

        mockAccess.mockReturnValue({ loading: false, allowed: false })
        render(<MessageTemplatesPage />)
        expect(screen.getByText("Message templates are restricted")).toBeInTheDocument()
    })

    it("opens New template", () => {
        render(<MessageTemplatesPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "New template" })[0]!)
        expect(mockPush).toHaveBeenCalledWith("/automation/message-templates/new")
    })
})

describe("Message template editor", () => {
    it("edits the draft in place and publishes it", async () => {
        mockSaveDraft.mockResolvedValue(version({ id: "v2", version: 2, status: "draft" }))
        mockPublish.mockResolvedValue(version({ id: "v2", version: 2, status: "published" }))
        render(<MessageTemplateEditorPageClient />)

        expect(screen.getByText("Draft v2")).toBeInTheDocument()
        expect(screen.getByText("Live: v1")).toBeInTheDocument()
        expect(screen.getByText("Reminder: your call is Jane.")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Remind before consult" })).toHaveAttribute("href", "/automation/workflows/wf-1")

        fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Your call is soon." } })
        expect(screen.getByText("18 characters · 1 segment")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Publish v2" }))

        await waitFor(() => expect(mockPublish).toHaveBeenCalledWith("v2"))
        expect(mockSaveDraft).toHaveBeenCalledWith({
            templateKey: "family-1",
            draftId: "v2",
            update: { name: "Consultation reminder", body: "Your call is soon.", is_enrollment_confirmation: false },
        })
        expect(mockToastSuccess).toHaveBeenCalledWith("Published v2")
    })

    it("shows what an opt-in confirmation still needs", () => {
        mockParams.key = "family-2"
        render(<MessageTemplateEditorPageClient />)

        const checklist = screen.getByRole("list", { name: "Required for opt-in confirmation" })
        expect(within(checklist).getByText("Brand name")).toHaveTextContent("(included)")
        expect(within(checklist).getByText("STOP instructions")).toHaveTextContent("(missing)")
    })

    it("creates a new template and opens it", async () => {
        mockParams.key = "new"
        mockCreate.mockResolvedValue(version({ id: "n1", template_key: "family-9", status: "draft" }))
        render(<MessageTemplateEditorPageClient />)

        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Missing documents" } })
        fireEvent.change(screen.getByLabelText("Message"), { target: { value: "We still need a few documents." } })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/automation/message-templates/family-9"))
        expect(mockCreate).toHaveBeenCalledWith({
            name: "Missing documents",
            purpose: "operational",
            body: "We still need a few documents.",
            is_enrollment_confirmation: false,
        })
    })
})

describe("Send test message dialog", () => {
    const templates = [
        { id: "v2", label: "Consultation reminder · Draft v2", purpose: "operational" as const },
        { id: "p1", label: "Info session · Draft v1", purpose: "promotional" as const },
    ]

    it("sends the chosen template to a verified test phone", async () => {
        mockSendTest.mockResolvedValue({ id: "t1", provider_status: "queued" })
        const onOpenChange = vi.fn()
        render(<SendTestMessageDialog open onOpenChange={onOpenChange} templates={templates} defaultTemplateId="v2" />)

        expect(screen.getByText(/From \+1 ••• ••• 0100 on the operational route/)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))

        await waitFor(() => expect(mockSendTest).toHaveBeenCalledWith({ templateId: "v2", testPhoneId: "phone-1" }))
        expect(mockToastSuccess).toHaveBeenCalledWith("Test message sent to My phone")
        expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it("does not offer a phone that replied STOP to the template's purpose", () => {
        mockTestPhones.mockReturnValue({
            data: [phone({ stopped_purposes: ["operational", "promotional"] }), phone({ id: "phone-2", label: "Pending", verified_at: null })],
            isLoading: false,
        })
        render(<SendTestMessageDialog open onOpenChange={vi.fn()} templates={templates} defaultTemplateId="v2" />)

        expect(screen.getByText("Replied STOP")).toBeInTheDocument()
        expect(screen.queryByText("Pending")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Send test" })).toBeDisabled()
    })

    it("links to test phone setup when none is verified", () => {
        mockTestPhones.mockReturnValue({ data: [], isLoading: false })
        render(<SendTestMessageDialog open onOpenChange={vi.fn()} templates={templates} defaultTemplateId="v2" />)

        expect(screen.getByText("No verified test phones.")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Manage test phones" })).toHaveAttribute(
            "href",
            "/settings/integrations/messaging#test-phones",
        )
    })
})

describe("Test phones card", () => {
    it("sends a code, verifies a pending phone, and removes one", async () => {
        mockTestPhones.mockReturnValue({
            data: [
                phone({}),
                phone({ id: "phone-2", label: "Intake team phone", phone_last4: "0188", verified_at: null, code_expires_at: "2999-01-01T00:00:00Z" }),
                phone({ id: "phone-3", label: "Old ops line", phone_last4: "0107", stopped_purposes: ["operational", "promotional"] }),
            ],
            isLoading: false,
            isError: false,
        })
        mockAddPhone.mockResolvedValue(phone({ id: "phone-4" }))
        mockVerifyPhone.mockResolvedValue(phone({ id: "phone-2" }))
        mockRemovePhone.mockResolvedValue(undefined)
        render(<TestPhonesCard />)

        const table = screen.getByRole("table", { name: "Test phones" })
        const rows = within(table).getAllByRole("row").slice(1)
        expect(within(rows[0]!).getByText("•••-0142")).toBeInTheDocument()
        expect(within(rows[1]!).getByText("Code sent")).toBeInTheDocument()
        expect(within(rows[2]!).getByText("Replied STOP")).toBeInTheDocument()

        fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Front desk" } })
        fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "(512) 555-0199" } })
        fireEvent.click(screen.getByRole("button", { name: "Send code" }))
        await waitFor(() => expect(mockAddPhone).toHaveBeenCalledWith({ label: "Front desk", phone: "(512) 555-0199" }))

        fireEvent.change(screen.getByLabelText("Verification code for Intake team phone"), { target: { value: "12a3456" } })
        fireEvent.click(within(rows[1]!).getByRole("button", { name: "Verify" }))
        await waitFor(() => expect(mockVerifyPhone).toHaveBeenCalledWith({ id: "phone-2", code: "123456" }))

        fireEvent.click(within(rows[2]!).getByRole("button", { name: "Remove" }))
        await waitFor(() => expect(mockRemovePhone).toHaveBeenCalledWith("phone-3"))
    })

    it("shows the empty state", () => {
        mockTestPhones.mockReturnValue({ data: [], isLoading: false, isError: false })
        render(<TestPhonesCard />)
        expect(screen.getByText("No test phones.")).toBeInTheDocument()
    })
})
