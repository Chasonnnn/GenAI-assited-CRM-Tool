import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import PipelinesSettingsPage from "../app/(app)/settings/pipelines/page"

const mockUseAuth = vi.fn()
const mockUsePipelines = vi.fn()
const mockUsePipeline = vi.fn()
const mockUsePipelineVersions = vi.fn()
const mockUsePipelineDependencyGraph = vi.fn()
const mockUsePipelineChangePreview = vi.fn()
const mockRollbackPipeline = vi.fn()
const mockApplyPipelineDraft = vi.fn()
const mockUseRecommendedPipelineDraft = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-pipelines", () => ({
    usePipelines: () => mockUsePipelines(),
    usePipeline: (id: string | null) => mockUsePipeline(id),
    usePipelineVersions: (id: string | null) => mockUsePipelineVersions(id),
    usePipelineDependencyGraph: (id: string | null) => mockUsePipelineDependencyGraph(id),
    usePipelineChangePreview: (id: string | null, draft: unknown) =>
        mockUsePipelineChangePreview(id, draft),
    useRollbackPipeline: () => ({ mutateAsync: mockRollbackPipeline, isPending: false }),
    useApplyPipelineDraft: () => ({ mutateAsync: mockApplyPipelineDraft, isPending: false }),
    useRecommendedPipelineDraft: () => ({
        mutateAsync: mockUseRecommendedPipelineDraft,
        isPending: false,
    }),
}))

const pipelineFixture = {
    id: "p1",
    name: "Default Pipeline",
    is_default: true,
    stages: [
        {
            id: "s1",
            stage_key: "new_unread",
            slug: "new_unread",
            label: "New Unread",
            color: "#3b82f6",
            order: 1,
            stage_type: "intake" as const,
            is_active: true,
            semantics: {
                capabilities: {
                    counts_as_contacted: false,
                    eligible_for_matching: false,
                    locks_match_state: false,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: false,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "none" as const,
                terminal_outcome: "none" as const,
                integration_bucket: "intake" as const,
                analytics_bucket: "new_unread",
                suggestion_profile_key: "new_unread_followup",
                requires_reason_on_enter: false,
            },
        },
        {
            id: "s2",
            stage_key: "contacted",
            slug: "contacted",
            label: "Contacted",
            color: "#06b6d4",
            order: 2,
            stage_type: "intake" as const,
            is_active: true,
            semantics: {
                capabilities: {
                    counts_as_contacted: true,
                    eligible_for_matching: false,
                    locks_match_state: false,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: false,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "none" as const,
                terminal_outcome: "none" as const,
                integration_bucket: "qualified" as const,
                analytics_bucket: "contacted",
                suggestion_profile_key: "contacted_followup",
                requires_reason_on_enter: false,
            },
        },
        {
            id: "s3",
            stage_key: "on_hold",
            slug: "on_hold",
            label: "On-Hold",
            color: "#b4536a",
            order: 3,
            stage_type: "paused" as const,
            is_active: true,
            semantics: {
                capabilities: {
                    counts_as_contacted: false,
                    eligible_for_matching: false,
                    locks_match_state: false,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: false,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "resume_previous_stage" as const,
                terminal_outcome: "none" as const,
                integration_bucket: "none" as const,
                analytics_bucket: "on_hold",
                suggestion_profile_key: null,
                requires_reason_on_enter: true,
            },
        },
        {
            id: "s4",
            stage_key: "lost",
            slug: "lost",
            label: "Lost",
            color: "#ef4444",
            order: 4,
            stage_type: "terminal" as const,
            is_active: true,
            semantics: {
                capabilities: {
                    counts_as_contacted: false,
                    eligible_for_matching: false,
                    locks_match_state: false,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: false,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "none" as const,
                terminal_outcome: "lost" as const,
                integration_bucket: "lost" as const,
                analytics_bucket: "lost",
                suggestion_profile_key: null,
                requires_reason_on_enter: false,
            },
        },
    ],
    feature_config: {
        schema_version: 1,
        journey: {
            phases: [],
            milestones: [
                {
                    slug: "application_intake",
                    label: "Application & Intake",
                    description: "Initial application received.",
                    mapped_stage_keys: ["new_unread", "contacted"],
                    is_soft: false,
                },
            ],
        },
        analytics: {
            funnel_stage_keys: ["new_unread", "contacted"],
            performance_stage_keys: ["contacted", "lost"],
            qualification_stage_key: "contacted",
            conversion_stage_key: "lost",
        },
        role_visibility: {},
        role_mutation: {},
    },
    current_version: 2,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
}

const dependencyGraphFixture = {
    pipeline_id: "p1",
    version: 2,
    stages: pipelineFixture.stages.map((stage) => ({
        stage_id: stage.id,
        stage_key: stage.stage_key,
        slug: stage.slug,
        label: stage.label,
        category: stage.stage_type,
        stage_type: stage.stage_type,
        is_active: stage.is_active,
        surrogate_count: stage.stage_key === "contacted" ? 3 : 0,
        journey_milestone_slugs:
            stage.stage_key === "contacted" ? ["application_intake"] : [],
        analytics_funnel:
            stage.stage_key === "contacted",
        intelligent_suggestion_rules: [],
        integration_refs: [],
        campaign_refs: [],
        workflow_refs: [],
        role_visibility_roles: [],
        role_mutation_roles: [],
    })),
}

const previewFixture = {
    impact_areas: ["analytics", "ui_gating"],
    validation_errors: [],
    blocking_issues: [],
    required_remaps: [],
    safe_auto_fixes: [],
    dependency_graph: dependencyGraphFixture,
}

describe("PipelinesSettingsPage", () => {
    beforeEach(() => {
        mockUseAuth.mockReset()
        mockUsePipelines.mockReset()
        mockUsePipeline.mockReset()
        mockUsePipelineVersions.mockReset()
        mockUsePipelineDependencyGraph.mockReset()
        mockUsePipelineChangePreview.mockReset()
        mockRollbackPipeline.mockReset()
        mockApplyPipelineDraft.mockReset()
        mockUseRecommendedPipelineDraft.mockReset()

        mockUseAuth.mockReturnValue({ user: { role: "admin" } })
        mockUsePipelines.mockReturnValue({ data: [pipelineFixture], isLoading: false })
        mockUsePipeline.mockReturnValue({ data: pipelineFixture, isLoading: false })
        mockUsePipelineVersions.mockReturnValue({ data: [], isLoading: false, isError: false })
        mockUsePipelineDependencyGraph.mockReturnValue({
            data: dependencyGraphFixture,
            isLoading: false,
        })
        mockUsePipelineChangePreview.mockReturnValue({
            data: previewFixture,
            isLoading: false,
        })
        mockApplyPipelineDraft.mockResolvedValue({})
        mockUseRecommendedPipelineDraft.mockResolvedValue({
            name: "Default Pipeline",
            stages: pipelineFixture.stages,
            feature_config: pipelineFixture.feature_config,
        })
    })

    it("renders editable slugs, hides stage keys until expanded, and keeps categories editable", () => {
        render(<PipelinesSettingsPage />)

        expect(screen.getByText("Pipeline Settings")).toBeInTheDocument()
        expect(screen.getAllByLabelText("Stage slug")[0]).toBeEnabled()
        expect(screen.queryByLabelText("Stage key")).not.toBeInTheDocument()
        expect(screen.getAllByLabelText("Stage category")[0]).toBeEnabled()
        expect(
            screen.getByText(/workflows, analytics, suggestions, and integrations follow stage semantics/i),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /edit details for new unread/i }))

        expect(screen.getByLabelText("Stage key")).toBeDisabled()
    })

    it("hides stage details by default and expands them on demand", () => {
        render(<PipelinesSettingsPage />)

        expect(screen.queryByText("Behavior preset")).not.toBeInTheDocument()
        expect(screen.queryByText("53 active surrogates")).not.toBeInTheDocument()
        expect(screen.queryByText("Journey: application_intake")).not.toBeInTheDocument()
        expect(screen.queryByText("Analytics funnel")).not.toBeInTheDocument()
        expect(
            screen.queryByText(
                /expand to edit behavior presets, buckets, and capability toggles for this stage/i,
            ),
        ).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /edit details for contacted/i }))

        expect(screen.getByText("Behavior preset")).toBeInTheDocument()
        expect(screen.getByLabelText("Stage key")).toBeInTheDocument()
        expect(screen.getByText("3 active surrogates")).toBeInTheDocument()
        expect(screen.getByText("Journey: application_intake")).toBeInTheDocument()
        expect(screen.getByText("Analytics funnel")).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: /hide details for contacted/i }),
        ).toHaveAttribute("aria-expanded", "true")
    })

    it("hides journey milestone details by default and expands them on demand", () => {
        render(<PipelinesSettingsPage />)

        expect(
            screen.queryByLabelText("Application & Intake includes New Unread"),
        ).not.toBeInTheDocument()

        fireEvent.click(
            screen.getByRole("button", { name: /edit details for application & intake/i }),
        )

        expect(
            screen.getByLabelText("Application & Intake includes New Unread"),
        ).toBeInTheDocument()
        expect(screen.getByText("2 mapped stages")).toBeInTheDocument()
    })

    it("hides analytics funnel details by default and expands them on demand", () => {
        render(<PipelinesSettingsPage />)

        expect(
            screen.queryByLabelText("Include New Unread in analytics funnel"),
        ).not.toBeInTheDocument()

        fireEvent.click(
            screen.getByRole("button", { name: /edit details for analytics funnel/i }),
        )

        expect(
            screen.getByLabelText("Include New Unread in analytics funnel"),
        ).toBeInTheDocument()
        expect(screen.getByText("2 funnel stages")).toBeInTheDocument()
    })

    it("adds a stage and saves through applyPipelineDraft", async () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /add stage/i }))
        const labelInputs = screen.getAllByPlaceholderText("Label")
        const slugInputs = screen.getAllByLabelText("Stage slug")
        fireEvent.change(labelInputs[labelInputs.length - 1] as HTMLInputElement, {
            target: { value: "Matching Review" },
        })
        fireEvent.change(slugInputs[slugInputs.length - 1] as HTMLInputElement, {
            target: { value: "matching_review" },
        })

        expect(screen.getByText("Unsaved changes")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: /save changes/i }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })

        const call = mockApplyPipelineDraft.mock.calls[0][0]
        expect(call.id).toBe("p1")
        expect(call.data.expected_version).toBe(2)
        expect(
            call.data.stages.some(
                (stage: { stage_key?: string; slug: string }) =>
                    stage.slug === "matching_review"
                    && stage.stage_key === "matching_review",
            ),
        ).toBe(true)
    })

    it("deletes a stage with a remap target and applies the draft", async () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /remove contacted/i }))
        fireEvent.change(screen.getByLabelText("Remap target stage"), {
            target: { value: "new_unread" },
        })
        fireEvent.click(screen.getByRole("button", { name: /confirm removal/i }))

        fireEvent.click(screen.getByRole("button", { name: /save changes/i }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })

        const call = mockApplyPipelineDraft.mock.calls[0][0]
        expect(call.data.remaps).toEqual([
            {
                removed_stage_key: "contacted",
                target_stage_key: "new_unread",
            },
        ])
    })

    it("rolls back to a previous version", async () => {
        mockUseAuth.mockReturnValue({ user: { role: "developer" } })
        mockUsePipelineVersions.mockReturnValue({
            data: [
                {
                    id: "v2",
                    version: 2,
                    created_at: new Date().toISOString(),
                    comment: "Current",
                },
                {
                    id: "v1",
                    version: 1,
                    created_at: new Date(Date.now() - 86400000).toISOString(),
                    comment: "Initial",
                },
            ],
            isLoading: false,
            isError: false,
        })
        mockRollbackPipeline.mockResolvedValue({})

        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /restore/i }))

        await waitFor(() => {
            expect(mockRollbackPipeline).toHaveBeenCalledWith({ id: "p1", version: 1 })
        })
    })
})
