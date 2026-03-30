import { describe, it, expect, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"
import MetaFormMappingPage from "../app/(app)/settings/integrations/meta/forms/[id]/page"

const mockPush = vi.fn()
const mockUseMetaFormMapping = vi.fn()
const mockUseUpdateMetaFormMapping = vi.fn()
const mockUseMetaFormUnconvertedLeads = vi.fn()
const mockUseReconvertMetaFormLeads = vi.fn()
const mockUseAiMapImport = vi.fn()

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
}))

vi.mock("@/lib/hooks/use-import", () => ({
    useAiMapImport: () => mockUseAiMapImport(),
}))

describe("MetaFormMappingPage", () => {
    beforeEach(() => {
        mockPush.mockReset()
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
                available_fields: ["full_name", "email", "phone", "state", "journey_timing_preference"],
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

    it("renders unconverted lead details when failures exist", () => {
        render(<MetaFormMappingPage />)

        expect(screen.getByText(/reprocess queued/i)).toBeInTheDocument()
        expect(screen.getByText(/lead_failed/i)).toBeInTheDocument()
        expect(screen.getByText(/1 eligible, 1 blocked/i)).toBeInTheDocument()
        expect(screen.getAllByText(/eligible/i).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/blocked/i).length).toBeGreaterThan(0)
        expect(screen.getByText(/duplicate email/i)).toBeInTheDocument()
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
})
