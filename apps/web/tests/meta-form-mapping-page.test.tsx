import { describe, it, expect, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import MetaFormMappingPage from "../app/(app)/settings/integrations/meta/forms/[id]/page"
import { ApiError } from "@/lib/api"

const mockPush = vi.fn()
const mockUseMetaFormMapping = vi.fn()
const mockUseUpdateMetaFormMapping = vi.fn()
const mockUseMetaFormUnconvertedLeads = vi.fn()
const mockUseReconvertMetaFormLeads = vi.fn()
const mockUseAiMapImport = vi.fn()
const mockUseRerouteMetaFormLead = vi.fn()
const mockToast = vi.hoisted(() => ({ success: vi.fn(), warning: vi.fn(), error: vi.fn() }))
const DONOR_FIELDS = ["full_name", "email", "phone", "state", "education", "date_of_birth", "race", "height_ft", "weight_lb"]
const SURROGATE_FIELDS = ["full_name", "email", "phone", "state", "journey_timing_preference"]

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "form-1" }),
    useRouter: () => ({
        push: mockPush,
    }),
}))

vi.mock("@/lib/hooks/use-meta-forms", () => ({
    useMetaFormMapping: (formId: string) => mockUseMetaFormMapping(formId),
    useUpdateMetaFormMapping: (formId: string) => mockUseUpdateMetaFormMapping(formId),
    useMetaFormUnconvertedLeads: (formId: string) => mockUseMetaFormUnconvertedLeads(formId),
    useReconvertMetaFormLeads: (formId: string) => mockUseReconvertMetaFormLeads(formId),
    useRerouteMetaFormLead: (formId: string) => mockUseRerouteMetaFormLead(formId),
}))

vi.mock("@/components/ui/toast", () => ({ toast: mockToast }))

vi.mock("@/lib/hooks/use-import", () => ({
    useAiMapImport: () => mockUseAiMapImport(),
}))

let mockPermissions: string[] = ["manage_meta_leads"]

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockPermissions.includes(permission),
    }),
}))

describe("MetaFormMappingPage access and load failures", () => {
    beforeEach(() => {
        mockPermissions = ["manage_meta_leads"]
        mockUseMetaFormMapping.mockReset()
        mockUseMetaFormUnconvertedLeads.mockReturnValue({ data: undefined, isLoading: false })
        mockUseUpdateMetaFormMapping.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseReconvertMetaFormLeads.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRerouteMetaFormLead.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseAiMapImport.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    })

    it("shows the restricted state and requests no mapping without manage_meta_leads", () => {
        mockPermissions = []

        render(<MetaFormMappingPage />)

        expect(screen.getByRole("heading", { name: "Permission required" })).toBeInTheDocument()
        expect(mockUseMetaFormMapping).not.toHaveBeenCalled()
    })

    it("replaces the spinner with a retryable error when the mapping fails to load", () => {
        const refetch = vi.fn()
        mockUseMetaFormMapping.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(500, "Internal Server Error"),
            refetch,
        })

        render(<MetaFormMappingPage />)

        expect(screen.getByRole("heading", { name: "Couldn't load this form mapping" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalled()
    })

    it("shows the not-found state for a missing form", () => {
        mockUseMetaFormMapping.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(404, "Not Found"),
            refetch: vi.fn(),
        })

        render(<MetaFormMappingPage />)

        expect(screen.getByRole("heading", { name: "Form not found" })).toBeInTheDocument()
        expect(screen.getAllByRole("link", { name: /Back to forms/ }).length).toBeGreaterThan(0)
    })
})

describe("MetaFormMappingPage", () => {
    beforeEach(() => {
        mockPush.mockReset()
        mockPermissions = ["manage_meta_leads", "view_donors", "edit_donors"]
        mockToast.success.mockReset()
        mockToast.warning.mockReset()
        mockToast.error.mockReset()
        mockUseRerouteMetaFormLead.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseMetaFormMapping.mockReturnValue({
            data: {
                form: {
                    id: "form-1",
                    form_external_id: "form_ext_1",
                    form_name: "Lead Form",
                    page_id: "page_1",
                    page_name: "Meta Page",
                    mapping_status: "mapped",
                    current_version_id: "version-1",
                    mapping_version_id: "version-1",
                    mapping_updated_at: null,
                    mapping_updated_by_name: null,
                    lead_kind: "surrogate",
                    is_active: true,
                    synced_at: "2026-03-08T00:00:00Z",
                    unconverted_leads: 1,
                    total_leads: 3,
                    last_lead_at: "2026-03-08T00:00:00Z",
                },
                columns: [
                    { key: "full_name", label: "Full Name", question_type: "text" },
                    { key: "email", label: "Email", question_type: "text" },
                ],
                column_suggestions: [
                    {
                        csv_column: "full_name",
                        suggested_field: "full_name",
                        confidence: 0.99,
                        confidence_level: "high",
                        transformation: null,
                        sample_values: ["Failed Lead"],
                        reason: "Matched",
                        warnings: [],
                        default_action: "map",
                        needs_inversion: false,
                    },
                    {
                        csv_column: "email",
                        suggested_field: "email",
                        confidence: 0.99,
                        confidence_level: "high",
                        transformation: null,
                        sample_values: ["failed@example.com"],
                        reason: "Matched",
                        warnings: [],
                        default_action: "map",
                        needs_inversion: false,
                    },
                ],
                sample_rows: [{ full_name: "Failed Lead", email: "failed@example.com" }],
                has_live_leads: true,
                available_fields: SURROGATE_FIELDS,
                available_fields_by_lead_kind: {
                    surrogate: SURROGATE_FIELDS,
                    egg_donor: DONOR_FIELDS,
                    sperm_donor: DONOR_FIELDS,
                },
                ai_available: false,
                mapping_rules: [
                    {
                        csv_column: "full_name",
                        surrogate_field: "full_name",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                    {
                        csv_column: "email",
                        surrogate_field: "email",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                ],
                unknown_column_behavior: "metadata",
            },
            isLoading: false,
        })
        mockUseUpdateMetaFormMapping.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseReconvertMetaFormLeads.mockReturnValue({
            mutateAsync: vi.fn().mockResolvedValue({
                success: true,
                queued_count: 1,
                blocked_count: 1,
                blocked_reasons: { duplicate_email: 1 },
                message: "Queued 1 eligible lead(s) for reconversion.",
            }),
            isPending: false,
        })
        mockUseMetaFormUnconvertedLeads.mockReturnValue({
            data: {
                total: 2,
                eligible_count: 1,
                blocked_count: 1,
                items: [
                    {
                        id: "lead-db-1",
                        meta_lead_id: "lead_failed",
                        status: "convert_failed",
                        conversion_error: "Missing required fields: phone_number",
                        full_name: "Failed Lead",
                        email: "failed@example.com",
                        phone: null,
                        received_at: "2026-03-08T01:00:00Z",
                        meta_created_time: "2026-03-08T00:30:00Z",
                        is_converted: false,
                        reprocess_eligible: true,
                        reprocess_block_reason: null,
                    },
                    {
                        id: "lead-db-2",
                        meta_lead_id: "lead_duplicate",
                        status: "convert_failed",
                        conversion_error: "duplicate key value violates unique constraint",
                        full_name: "Duplicate Lead",
                        email: "dupe@example.com",
                        phone: null,
                        received_at: "2026-03-08T02:00:00Z",
                        meta_created_time: "2026-03-08T01:30:00Z",
                        is_converted: false,
                        reprocess_eligible: false,
                        reprocess_block_reason: "duplicate_email",
                    },
                ],
            },
            isLoading: false,
        })
        mockUseAiMapImport.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
    })

    it("flags a stored donor mapping targeting an unsupported field as repair-required", () => {
        const baseline = mockUseMetaFormMapping()
        mockUseMetaFormMapping.mockReturnValue({
            ...baseline,
            data: {
                ...baseline.data,
                form: { ...baseline.data.form, lead_kind: "egg_donor" },
                available_fields: ["full_name", "email", "phone", "state", "education"],
                unsupported_mapped_fields: ["source"],
            },
        })

        render(<MetaFormMappingPage />)

        expect(screen.getByText(/mapping repair required/i)).toBeInTheDocument()
        expect(
            screen.getByText(/donor records converted from meta always use the meta source/i)
        ).toBeInTheDocument()
    })

    it("does not show the mapping repair alert without unsupported fields", () => {
        render(<MetaFormMappingPage />)

        expect(screen.queryByText(/mapping repair required/i)).not.toBeInTheDocument()
        expect(screen.getByText(/reprocess queued/i)).toBeInTheDocument()
        expect(screen.getByText(/lead_failed/i)).toBeInTheDocument()
        expect(screen.getByText(/1 eligible, 1 blocked/i)).toBeInTheDocument()
        expect(screen.getAllByText(/eligible/i).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/blocked/i).length).toBeGreaterThan(0)
        expect(screen.getByText("Duplicate email")).toBeInTheDocument()
        expect(screen.getAllByText("Conversion failed")).toHaveLength(2)
        expect(screen.queryByText("convert_failed")).not.toBeInTheDocument()
        expect(screen.getAllByText(/failed@example.com/i).length).toBeGreaterThan(0)
    })

    it("queues eligible leads for reconversion with one click", async () => {
        const mutateAsync = vi.fn().mockResolvedValue({
            success: true,
            queued_count: 1,
            blocked_count: 1,
            blocked_reasons: { duplicate_email: 1 },
            message: "Queued 1 eligible lead(s) for reconversion.",
        })
        mockUseReconvertMetaFormLeads.mockReturnValue({
            mutateAsync,
            isPending: false,
        })

        render(<MetaFormMappingPage />)

        fireEvent.click(screen.getByRole("button", { name: /re-convert eligible leads/i }))

        expect(mutateAsync).toHaveBeenCalledTimes(1)
        expect(
            await screen.findByText(/queued 1 eligible lead\(s\) for reconversion/i)
        ).toBeInTheDocument()
    })

    it("shows journey timing as a selectable mapping option", async () => {
        render(<MetaFormMappingPage />)

        expect(screen.getByRole("combobox", { name: /action for full_name/i })).toHaveTextContent("Map")
        expect(screen.getByRole("combobox", { name: /action for full_name/i })).not.toHaveTextContent("map")

        const mapToSelect = screen.getByRole("combobox", {
            name: /map full_name to field/i,
        })
        fireEvent.mouseDown(mapToSelect)

        const journeyOption = await screen.findByRole("option", { name: "Journey Timing" })
        expect(journeyOption).toBeInTheDocument()

        fireEvent.mouseMove(journeyOption)
        fireEvent.click(journeyOption)

        expect(
            within(screen.getByRole("combobox", { name: /map full_name to field/i }))
                .getByText("Journey Timing")
        ).toBeInTheDocument()
    })

    it("preserves an unsaved column edit when mapping data refreshes", async () => {
        const view = render(<MetaFormMappingPage />)
        const mapToSelect = screen.getByRole("combobox", {
            name: /map full_name to field/i,
        })
        const emailMapToSelect = screen.getByRole("combobox", {
            name: /map email to field/i,
        })

        fireEvent.mouseDown(mapToSelect)
        const phoneOption = await screen.findByRole("option", { name: "Phone" })
        fireEvent.mouseMove(phoneOption)
        fireEvent.click(phoneOption)
        expect(mapToSelect).toHaveTextContent("Phone")

        const latestResult = mockUseMetaFormMapping.mock.results.at(-1)?.value as {
            data: Record<string, unknown> & { form: Record<string, unknown> }
            isLoading: boolean
        }
        mockUseMetaFormMapping.mockReturnValue({
            ...latestResult,
            data: {
                ...latestResult.data,
                mapping_rules: [
                    {
                        csv_column: "full_name",
                        surrogate_field: "full_name",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                    {
                        csv_column: "email",
                        surrogate_field: "state",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                ],
                form: {
                    ...latestResult.data.form,
                    synced_at: "2026-03-08T01:00:00Z",
                },
            },
        })
        view.rerender(<MetaFormMappingPage />)

        expect(mapToSelect).toHaveTextContent("Phone")
        expect(emailMapToSelect).toHaveTextContent("State")
    })

    it("saves manually touched unknown Meta columns when warn behavior omits untouched columns", async () => {
        const mutateAsync = vi.fn()
        mockUseUpdateMetaFormMapping.mockReturnValue({
            mutateAsync,
            isPending: false,
        })
        mockUseMetaFormMapping.mockReturnValue({
            data: {
                form: {
                    id: "form-1",
                    form_external_id: "form_ext_1",
                    form_name: "Lead Form",
                    page_id: "page_1",
                    page_name: "Meta Page",
                    mapping_status: "mapped",
                    current_version_id: "version-1",
                    mapping_version_id: "version-1",
                    mapping_updated_at: null,
                    mapping_updated_by_name: null,
                    is_active: true,
                    synced_at: "2026-03-08T00:00:00Z",
                    unconverted_leads: 0,
                    total_leads: 3,
                    last_lead_at: "2026-03-08T00:00:00Z",
                },
                columns: [
                    { key: "full_name", label: "Full Name", question_type: "text" },
                    { key: "email", label: "Email", question_type: "text" },
                    { key: "favorite_color", label: "Favorite Color", question_type: "text" },
                    { key: "hobby", label: "Hobby", question_type: "text" },
                ],
                column_suggestions: [
                    {
                        csv_column: "full_name",
                        suggested_field: "full_name",
                        confidence: 0.99,
                        confidence_level: "high",
                        transformation: null,
                        sample_values: ["Failed Lead"],
                        reason: "Matched",
                        warnings: [],
                        default_action: "map",
                        needs_inversion: false,
                    },
                    {
                        csv_column: "email",
                        suggested_field: "email",
                        confidence: 0.99,
                        confidence_level: "high",
                        transformation: null,
                        sample_values: ["failed@example.com"],
                        reason: "Matched",
                        warnings: [],
                        default_action: "map",
                        needs_inversion: false,
                    },
                    {
                        csv_column: "favorite_color",
                        suggested_field: null,
                        confidence: 0,
                        confidence_level: "none",
                        transformation: null,
                        sample_values: ["blue"],
                        reason: "No match",
                        warnings: [],
                        default_action: "ignore",
                        needs_inversion: false,
                    },
                    {
                        csv_column: "hobby",
                        suggested_field: null,
                        confidence: 0,
                        confidence_level: "none",
                        transformation: null,
                        sample_values: ["cycling"],
                        reason: "No match",
                        warnings: [],
                        default_action: "ignore",
                        needs_inversion: false,
                    },
                ],
                sample_rows: [
                    {
                        full_name: "Failed Lead",
                        email: "failed@example.com",
                        favorite_color: "blue",
                        hobby: "cycling",
                    },
                ],
                has_live_leads: true,
                available_fields: ["full_name", "email"],
                available_fields_by_lead_kind: {
                    surrogate: ["full_name", "email"],
                    egg_donor: DONOR_FIELDS,
                    sperm_donor: DONOR_FIELDS,
                },
                ai_available: false,
                mapping_rules: [
                    {
                        csv_column: "full_name",
                        surrogate_field: "full_name",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                    {
                        csv_column: "email",
                        surrogate_field: "email",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                ],
                unknown_column_behavior: "warn",
            },
            isLoading: false,
        })

        render(<MetaFormMappingPage />)

        fireEvent.mouseDown(screen.getByRole("combobox", { name: /action for favorite_color/i }))
        const customOption = await screen.findByRole("option", { name: "Custom" })
        fireEvent.mouseMove(customOption)
        fireEvent.click(customOption)
        fireEvent.change(screen.getByRole("textbox", { name: /custom field key for favorite_color/i }), {
            target: { value: "favorite_color" },
        })
        fireEvent.click(screen.getByRole("button", { name: /save mapping/i }))

        expect(mutateAsync).toHaveBeenCalledWith({
            column_mappings: expect.arrayContaining([
                expect.objectContaining({
                    csv_column: "favorite_color",
                    action: "custom",
                    custom_field_key: "favorite_color",
                }),
            ]),
            lead_kind: "surrogate",
            unknown_column_behavior: "warn",
        })
        expect(mutateAsync.mock.calls[0][0].column_mappings).not.toEqual(
            expect.arrayContaining([expect.objectContaining({ csv_column: "hobby" })])
        )
    })

    it("saves whether a Meta form creates surrogates, egg donors, or sperm donors", async () => {
        const mutateAsync = vi.fn().mockResolvedValue({ success: true })
        mockUseUpdateMetaFormMapping.mockReturnValue({
            mutateAsync,
            isPending: false,
        })

        render(<MetaFormMappingPage />)

        const leadType = screen.getByRole("combobox", { name: /^lead type$/i })
        expect(leadType).toHaveTextContent("Surrogate")
        fireEvent.mouseDown(leadType)
        const eggDonorOption = await screen.findByRole("option", { name: "Egg donor" })
        fireEvent.mouseMove(eggDonorOption)
        fireEvent.click(eggDonorOption)
        expect(screen.getByText("Profile photo follow-up required")).toBeInTheDocument()
        expect(screen.getByText(/Meta lead forms do not send file uploads/i)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: /save mapping/i }))

        await waitFor(() =>
            expect(mutateAsync).toHaveBeenCalledWith(
                expect.objectContaining({ lead_kind: "egg_donor" })
            )
        )
    })

    function withJourneyAndMetadataColumns() {
        const baseline = mockUseMetaFormMapping()
        const suggestion = (csv_column: string, suggested_field: string | null, default_action: string) => ({
            csv_column,
            suggested_field,
            confidence: suggested_field ? 0.9 : 0,
            confidence_level: suggested_field ? "high" : "none",
            transformation: null,
            sample_values: ["sample"],
            reason: "Matched",
            warnings: [],
            default_action,
            needs_inversion: false,
        })
        mockUseMetaFormMapping.mockReturnValue({
            ...baseline,
            data: {
                ...baseline.data,
                columns: [
                    ...baseline.data.columns,
                    { key: "timing", label: "Timing", question_type: "text" },
                    { key: "campaign", label: "Campaign", question_type: "text" },
                ],
                column_suggestions: [
                    ...baseline.data.column_suggestions,
                    suggestion("timing", "journey_timing_preference", "map"),
                    suggestion("campaign", null, "metadata"),
                ],
                mapping_rules: [
                    ...baseline.data.mapping_rules,
                    {
                        csv_column: "timing",
                        surrogate_field: "journey_timing_preference",
                        transformation: null,
                        action: "map",
                        custom_field_key: null,
                    },
                    {
                        csv_column: "campaign",
                        surrogate_field: null,
                        transformation: null,
                        action: "metadata",
                        custom_field_key: null,
                    },
                ],
            },
        })
    }

    async function chooseOption(combobox: HTMLElement, name: string) {
        fireEvent.mouseDown(combobox)
        const option = await screen.findByRole("option", { name })
        fireEvent.mouseMove(option)
        fireEvent.click(option)
    }

    it("resets surrogate-only targets and metadata when the lead type switches to a donor", async () => {
        const mutateAsync = vi.fn().mockResolvedValue({ success: true })
        mockUseUpdateMetaFormMapping.mockReturnValue({ mutateAsync, isPending: false })
        withJourneyAndMetadataColumns()
        render(<MetaFormMappingPage />)

        expect(screen.getByRole("combobox", { name: /map timing to field/i })).toHaveTextContent("Journey Timing")
        expect(screen.getByRole("combobox", { name: /action for campaign/i })).toHaveTextContent("Metadata")

        await chooseOption(screen.getByRole("combobox", { name: /^lead type$/i }), "Egg donor")

        expect(screen.getByRole("combobox", { name: /action for timing/i })).toHaveTextContent("Ignore")
        expect(screen.queryByRole("combobox", { name: /map timing to field/i })).not.toBeInTheDocument()
        expect(screen.getByRole("combobox", { name: /action for campaign/i })).toHaveTextContent("Ignore")
        expect(screen.getByRole("combobox", { name: /unknown columns behavior/i })).toHaveTextContent("Ignore")

        fireEvent.mouseDown(screen.getByRole("combobox", { name: /action for campaign/i }))
        expect(await screen.findByRole("option", { name: "Map" })).toBeInTheDocument()
        expect(screen.getByRole("option", { name: "Ignore" })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Metadata" })).not.toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Custom" })).not.toBeInTheDocument()

        fireEvent.mouseDown(screen.getByRole("combobox", { name: /map full_name to field/i }))
        expect(await screen.findByRole("option", { name: "Education" })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Journey Timing" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /save mapping/i }))
        await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
        const payload = mutateAsync.mock.calls[0][0]
        expect(payload.lead_kind).toBe("egg_donor")
        expect(payload.unknown_column_behavior).toBe("ignore")
        expect(payload.column_mappings).toEqual(expect.arrayContaining([
            expect.objectContaining({ csv_column: "timing", action: "ignore", surrogate_field: null }),
            expect.objectContaining({ csv_column: "campaign", action: "ignore" }),
        ]))

        await chooseOption(screen.getByRole("combobox", { name: /^lead type$/i }), "Surrogate")
        expect(screen.getByRole("combobox", { name: /map timing to field/i })).toHaveTextContent("Journey Timing")
        expect(screen.getByRole("combobox", { name: /action for campaign/i })).toHaveTextContent("Metadata")
    })

    it("hides metadata choices for a stored donor form", async () => {
        withJourneyAndMetadataColumns()
        const current = mockUseMetaFormMapping()
        mockUseMetaFormMapping.mockReturnValue({
            ...current,
            data: { ...current.data, form: { ...current.data.form, lead_kind: "sperm_donor" } },
        })
        render(<MetaFormMappingPage />)

        expect(screen.getByRole("combobox", { name: /action for campaign/i })).toHaveTextContent("Ignore")
        fireEvent.mouseDown(screen.getByRole("combobox", { name: /unknown columns behavior/i }))
        expect(await screen.findByRole("option", { name: "Warn only" })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Store metadata" })).not.toBeInTheDocument()
    })

    it("reroutes one unconverted lead to another lead type", async () => {
        const mutateAsync = vi.fn().mockResolvedValue({
            success: true,
            lead_kind: "egg_donor",
            queued: false,
            reprocess_block_reason: "mapping_not_ready",
            message: "Lead type updated. The lead was not queued for conversion.",
        })
        mockUseRerouteMetaFormLead.mockReturnValue({ mutateAsync, isPending: false })
        render(<MetaFormMappingPage />)

        const leadType = screen.getByRole("combobox", { name: "Lead type for lead_failed" })
        expect(leadType).toHaveTextContent("Surrogate")
        await chooseOption(leadType, "Egg donor")

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ leadId: "lead-db-1", leadKind: "egg_donor" }))
        expect(mockUseRerouteMetaFormLead).toHaveBeenCalledWith("form-1")
        await waitFor(() => expect(mockToast.warning).toHaveBeenCalledWith(
            "Lead type changed to Egg donor. Not queued: mapping not ready."
        ))
    })

    it("disables donor form lead types without edit_donors", async () => {
        mockPermissions = ["manage_meta_leads"]
        render(<MetaFormMappingPage />)

        fireEvent.mouseDown(screen.getByRole("combobox", { name: /^lead type$/i }))
        expect(await screen.findByRole("option", { name: "Sperm donor" })).toHaveAttribute("aria-disabled", "true")
        expect(screen.getByRole("option", { name: "Surrogate" })).not.toHaveAttribute("aria-disabled", "true")
    })

    it("disables donor lead types for reroute without edit_donors", async () => {
        mockPermissions = ["manage_meta_leads"]
        const baseline = mockUseMetaFormUnconvertedLeads()
        mockUseMetaFormUnconvertedLeads.mockReturnValue({
            ...baseline,
            data: {
                ...baseline.data,
                items: [
                    baseline.data.items[0],
                    { ...baseline.data.items[1], lead_kind: "egg_donor" },
                ],
            },
        })
        render(<MetaFormMappingPage />)

        expect(screen.getByRole("combobox", { name: "Lead type for lead_duplicate" })).toHaveTextContent("Egg donor")
        expect(screen.getByRole("combobox", { name: "Lead type for lead_duplicate" })).toBeDisabled()
        fireEvent.mouseDown(screen.getByRole("combobox", { name: "Lead type for lead_failed" }))
        const list = await screen.findByRole("listbox")
        expect(within(list).getByRole("option", { name: "Egg donor" })).toHaveAttribute("aria-disabled", "true")
        expect(within(list).getByRole("option", { name: "Surrogate" })).not.toHaveAttribute("aria-disabled", "true")
    })
})
