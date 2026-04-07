import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
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

const LOCKED_STAGE_FIELDS = [
    "slug",
    "label",
    "color",
    "order",
    "category",
    "stage_type",
    "semantics",
    "is_active",
    "delete",
    "duplicate",
]

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-pipelines", () => ({
    usePipelines: (entityType?: string) => mockUsePipelines(entityType),
    usePipeline: (id: string | null, entityType?: string) => mockUsePipeline(id, entityType),
    usePipelineVersions: (id: string | null, entityType?: string) =>
        mockUsePipelineVersions(id, entityType),
    usePipelineDependencyGraph: (id: string | null, entityType?: string) =>
        mockUsePipelineDependencyGraph(id, entityType),
    usePipelineChangePreview: (
        id: string | null,
        draft: unknown,
        entityType?: string,
        draftFingerprint?: string,
    ) => mockUsePipelineChangePreview(id, draft, entityType, draftFingerprint),
    useRollbackPipeline: () => ({ mutateAsync: mockRollbackPipeline, isPending: false }),
    useApplyPipelineDraft: () => ({ mutateAsync: mockApplyPipelineDraft, isPending: false }),
    useRecommendedPipelineDraft: () => ({
        mutateAsync: mockUseRecommendedPipelineDraft,
        isPending: false,
    }),
}))

const pipelineFixture = {
    id: "p1",
    entity_type: "surrogate" as const,
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
            is_locked: true,
            system_role: "intake_entry",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
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
            is_locked: false,
            system_role: null,
            lock_reason: null,
            locked_fields: [],
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
            is_locked: true,
            system_role: "pause",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
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
            is_locked: true,
            system_role: "lost",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
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

const intendedParentPipelineFixture = {
    id: "ip-p1",
    entity_type: "intended_parent" as const,
    name: "Intended Parent Pipeline",
    is_default: true,
    stages: [
        {
            id: "ip-s1",
            stage_key: "new",
            slug: "new",
            label: "New",
            color: "#3b82f6",
            order: 1,
            stage_type: "intake" as const,
            is_active: true,
            is_locked: true,
            system_role: "intake_entry",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
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
                integration_bucket: "none" as const,
                analytics_bucket: null,
                suggestion_profile_key: null,
                requires_reason_on_enter: false,
            },
        },
        {
            id: "ip-s2",
            stage_key: "ready_to_match",
            slug: "matching_queue",
            label: "Ready to Match",
            color: "#f59e0b",
            order: 2,
            stage_type: "post_approval" as const,
            is_active: true,
            is_locked: true,
            system_role: "handoff",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
            semantics: {
                capabilities: {
                    counts_as_contacted: false,
                    eligible_for_matching: true,
                    locks_match_state: false,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: false,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "none" as const,
                terminal_outcome: "none" as const,
                integration_bucket: "none" as const,
                analytics_bucket: null,
                suggestion_profile_key: null,
                requires_reason_on_enter: false,
            },
        },
        {
            id: "ip-s3",
            stage_key: "matched",
            slug: "paired",
            label: "Matched",
            color: "#10b981",
            order: 3,
            stage_type: "post_approval" as const,
            is_active: true,
            is_locked: true,
            system_role: "matched",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
            semantics: {
                capabilities: {
                    counts_as_contacted: false,
                    eligible_for_matching: false,
                    locks_match_state: true,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: false,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "none" as const,
                terminal_outcome: "none" as const,
                integration_bucket: "none" as const,
                analytics_bucket: null,
                suggestion_profile_key: null,
                requires_reason_on_enter: false,
            },
        },
        {
            id: "ip-s4",
            stage_key: "delivered",
            slug: "birth_complete",
            label: "Delivered",
            color: "#14b8a6",
            order: 4,
            stage_type: "post_approval" as const,
            is_active: true,
            is_locked: true,
            system_role: "delivered",
            lock_reason: "This is a protected system stage used by platform workflows.",
            locked_fields: LOCKED_STAGE_FIELDS,
            semantics: {
                capabilities: {
                    counts_as_contacted: false,
                    eligible_for_matching: false,
                    locks_match_state: true,
                    shows_pregnancy_tracking: false,
                    requires_delivery_details: true,
                    tracks_interview_outcome: false,
                },
                pause_behavior: "none" as const,
                terminal_outcome: "none" as const,
                integration_bucket: "none" as const,
                analytics_bucket: null,
                suggestion_profile_key: null,
                requires_reason_on_enter: false,
            },
        },
    ],
    feature_config: {
        schema_version: 1,
        journey: { phases: [], milestones: [] },
        analytics: {
            funnel_stage_keys: [],
            performance_stage_keys: [],
            qualification_stage_key: null,
            conversion_stage_key: null,
        },
        role_visibility: {},
        role_mutation: {},
    },
    current_version: 1,
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

const intendedParentDependencyGraphFixture = {
    pipeline_id: "ip-p1",
    entity_type: "intended_parent" as const,
    version: 1,
    stages: intendedParentPipelineFixture.stages.map((stage) => ({
        stage_id: stage.id,
        stage_key: stage.stage_key,
        slug: stage.slug,
        label: stage.label,
        category: stage.stage_type,
        stage_type: stage.stage_type,
        is_active: stage.is_active,
        surrogate_count: stage.stage_key === "ready_to_match" ? 2 : 0,
        journey_milestone_slugs: [],
        analytics_funnel: false,
        intelligent_suggestion_rules: [],
        integration_refs: [],
        campaign_refs: [],
        workflow_refs: stage.stage_key === "ready_to_match" ? [{ id: "wf1", name: "Queue Sync", scope: "intended_parent", is_enabled: true, reference_paths: [] }] : [],
        role_visibility_roles: [],
        role_mutation_roles: [],
    })),
}

const intendedParentPreviewFixture = {
    impact_areas: ["campaigns", "workflows", "ui_gating"],
    validation_errors: [],
    blocking_issues: [],
    required_remaps: [],
    safe_auto_fixes: [],
    dependency_graph: intendedParentDependencyGraphFixture,
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
        mockUsePipelines.mockImplementation((entityType?: string) => ({
            data: [
                entityType === "intended_parent"
                    ? intendedParentPipelineFixture
                    : pipelineFixture,
            ],
            isLoading: false,
        }))
        mockUsePipeline.mockImplementation((_id: string | null, entityType?: string) => ({
            data: entityType === "intended_parent" ? intendedParentPipelineFixture : pipelineFixture,
            isLoading: false,
        }))
        mockUsePipelineVersions.mockImplementation(() => ({
            data: [],
            isLoading: false,
            isError: false,
        }))
        mockUsePipelineDependencyGraph.mockImplementation((_id: string | null, entityType?: string) => ({
            data: entityType === "intended_parent"
                ? intendedParentDependencyGraphFixture
                : dependencyGraphFixture,
            isLoading: false,
        }))
        mockUsePipelineChangePreview.mockImplementation(
            (_id: string | null, draft: unknown, entityType?: string) => ({
                data: draft
                    ? (entityType === "intended_parent"
                        ? intendedParentPreviewFixture
                        : previewFixture)
                    : null,
                isLoading: false,
            }),
        )
        mockApplyPipelineDraft.mockResolvedValue({})
        mockUseRecommendedPipelineDraft.mockImplementation(
            async ({ entityType }: { entityType?: string }) => ({
                name:
                    entityType === "intended_parent"
                        ? intendedParentPipelineFixture.name
                        : pipelineFixture.name,
                stages:
                    entityType === "intended_parent"
                        ? intendedParentPipelineFixture.stages
                        : pipelineFixture.stages,
                feature_config:
                    entityType === "intended_parent"
                        ? intendedParentPipelineFixture.feature_config
                        : pipelineFixture.feature_config,
            }),
        )
    })

    it("renders editable slugs, hides stage keys until expanded, and keeps categories editable", () => {
        render(<PipelinesSettingsPage />)

        expect(screen.getByText("Pipeline Settings")).toBeInTheDocument()
        expect(screen.getAllByLabelText("Stage slug")[1]).toBeEnabled()
        expect(screen.queryByLabelText("Stage key")).not.toBeInTheDocument()
        expect(screen.getAllByLabelText("Stage category")[1]).toBeEnabled()
        expect(
            screen.getByText(/downstream behaviors resolve from stage semantics and stage key instead of the slug/i),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /edit details for new unread/i }))

        expect(screen.getByLabelText("Stage key")).toBeDisabled()
    })

    it("renders protected stages as locked system stages and disables their controls", () => {
        render(<PipelinesSettingsPage />)

        expect(screen.getByDisplayValue("New Unread")).toBeDisabled()
        expect(screen.getAllByLabelText("Stage slug")[0]).toBeDisabled()
        expect(screen.getAllByLabelText("Stage category")[0]).toBeDisabled()
        expect(screen.queryByRole("button", { name: /duplicate new unread/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /remove new unread/i })).not.toBeInTheDocument()
        expect(screen.getAllByLabelText("System stage").length).toBeGreaterThan(0)

        fireEvent.click(screen.getByRole("button", { name: /edit details for new unread/i }))

        expect(screen.getByLabelText(/behavior preset for new unread/i)).toBeDisabled()
        expect(
            screen.getByText(/locked because platform workflows depend on it/i),
        ).toBeInTheDocument()
    })

    it("uses dedicated order slots and aligned action rails for locked and unlocked stages", () => {
        render(<PipelinesSettingsPage />)

        const lockedOrderSlot = screen.getByTestId("stage-order-slot-s1")
        const editableOrderSlot = screen.getByTestId("stage-order-slot-s2")
        const lockedActionRail = screen.getByTestId("stage-action-rail-s1")
        const editableActionRail = screen.getByTestId("stage-action-rail-s2")

        expect(lockedOrderSlot).toHaveTextContent("#1")
        expect(editableOrderSlot).toHaveTextContent("#2")

        expect(editableActionRail).toContainElement(
            screen.getByRole("button", { name: /duplicate contacted/i }),
        )
        expect(editableActionRail).toContainElement(
            screen.getByRole("button", { name: /remove contacted/i }),
        )
        expect(editableActionRail).toContainElement(
            screen.getByRole("button", { name: /edit details for contacted/i }),
        )

        expect(lockedActionRail).toHaveTextContent("Locked")
        expect(lockedActionRail).toContainElement(
            screen.getByRole("button", { name: /edit details for new unread/i }),
        )
        expect(
            screen.queryByRole("button", { name: /duplicate new unread/i }),
        ).not.toBeInTheDocument()
        expect(
            screen.queryByRole("button", { name: /remove new unread/i }),
        ).not.toBeInTheDocument()
    })

    it("keeps edit details as the trailing action in every stage row", () => {
        render(<PipelinesSettingsPage />)

        const lockedActionRail = screen.getByTestId("stage-action-rail-s1")
        const editableActionRail = screen.getByTestId("stage-action-rail-s2")

        const lockedButtons = within(lockedActionRail).getAllByRole("button")
        const editableButtons = within(editableActionRail).getAllByRole("button")

        expect(lockedButtons.at(-1)).toHaveAccessibleName(/edit details for new unread/i)
        expect(editableButtons.at(-1)).toHaveAccessibleName(/edit details for contacted/i)
    })

    it("stacks the entity selector with version history in the sidebar column", () => {
        render(<PipelinesSettingsPage />)

        const sidebar = screen.getByTestId("pipelines-sidebar")

        expect(within(sidebar).getByRole("combobox", { name: "Entity" })).toBeInTheDocument()
        expect(within(sidebar).getByText("Version History")).toBeInTheDocument()
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

        expect(screen.getAllByRole("button", { name: "Add Custom Stage" })).toHaveLength(1)

        fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))
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

    it("auto-remaps removed custom stages when resetting to default", async () => {
        const resettablePipelineFixture = {
            ...pipelineFixture,
            current_version: 8,
            stages: [
                pipelineFixture.stages[0],
                {
                    id: "custom-1",
                    stage_key: "application_packet_received",
                    slug: "application_packet_received",
                    label: "Application Packet Received",
                    color: "#8b5cf6",
                    order: 2,
                    stage_type: "intake" as const,
                    is_active: true,
                    is_locked: false,
                    system_role: null,
                    lock_reason: null,
                    locked_fields: [],
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
                        analytics_bucket: "application_submitted",
                        suggestion_profile_key: "application_submitted_followup",
                        requires_reason_on_enter: false,
                    },
                },
                {
                    id: "custom-2",
                    stage_key: "panel_review",
                    slug: "panel_review",
                    label: "Clinical Review",
                    color: "#2563eb",
                    order: 3,
                    stage_type: "intake" as const,
                    is_active: true,
                    is_locked: false,
                    system_role: null,
                    lock_reason: null,
                    locked_fields: [],
                    semantics: {
                        capabilities: {
                            counts_as_contacted: true,
                            eligible_for_matching: false,
                            locks_match_state: false,
                            shows_pregnancy_tracking: false,
                            requires_delivery_details: false,
                            tracks_interview_outcome: true,
                        },
                        pause_behavior: "none" as const,
                        terminal_outcome: "none" as const,
                        integration_bucket: "qualified" as const,
                        analytics_bucket: "under_review",
                        suggestion_profile_key: "under_review_followup",
                        requires_reason_on_enter: false,
                    },
                },
                {
                    id: "custom-3",
                    stage_key: "transfer_readiness",
                    slug: "transfer_readiness",
                    label: "Transfer Readiness",
                    color: "#0f766e",
                    order: 4,
                    stage_type: "post_approval" as const,
                    is_active: true,
                    is_locked: false,
                    system_role: null,
                    lock_reason: null,
                    locked_fields: [],
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
                        integration_bucket: "converted" as const,
                        analytics_bucket: "transfer_readiness",
                        suggestion_profile_key: "transfer_cycle_followup",
                        requires_reason_on_enter: false,
                    },
                },
                pipelineFixture.stages[3],
            ],
            feature_config: {
                ...pipelineFixture.feature_config,
                journey: {
                    phases: [],
                    milestones: [
                        {
                            slug: "application_intake",
                            label: "Application & Intake",
                            description: "Initial application received.",
                            mapped_stage_keys: ["new_unread", "application_packet_received"],
                            is_soft: false,
                        },
                    ],
                },
                analytics: {
                    funnel_stage_keys: ["new_unread", "application_packet_received", "panel_review"],
                    performance_stage_keys: ["application_packet_received", "panel_review", "transfer_readiness"],
                    qualification_stage_key: "application_packet_received",
                    conversion_stage_key: "transfer_readiness",
                },
            },
        }
        const resettableDependencyGraph = {
            pipeline_id: "p1",
            entity_type: "surrogate" as const,
            version: 8,
            stages: resettablePipelineFixture.stages.map((stage) => ({
                stage_id: stage.id,
                stage_key: stage.stage_key,
                slug: stage.slug,
                label: stage.label,
                category: stage.stage_type,
                stage_type: stage.stage_type,
                is_active: stage.is_active,
                surrogate_count:
                    stage.stage_key === "application_packet_received"
                    || stage.stage_key === "panel_review"
                        ? 4
                        : 0,
                journey_milestone_slugs: [],
                analytics_funnel: false,
                intelligent_suggestion_rules: [],
                integration_refs:
                    stage.stage_key === "application_packet_received"
                    || stage.stage_key === "transfer_readiness"
                        ? ["zapier"]
                        : [],
                campaign_refs: [],
                workflow_refs:
                    stage.stage_key === "application_packet_received"
                        ? [{ id: "wf-1", name: "Application Follow-up", scope: "surrogate", is_enabled: true, reference_paths: [] }]
                        : [],
                role_visibility_roles: [],
                role_mutation_roles: [],
            })),
        }
        const recommendedResetDraft = {
            name: resettablePipelineFixture.name,
            stages: [
                {
                    ...pipelineFixture.stages[0],
                    id: null,
                },
                {
                    id: null,
                    stage_key: "application_submitted",
                    slug: "application_submitted",
                    label: "Application Submitted",
                    color: "#8b5cf6",
                    order: 2,
                    stage_type: "intake" as const,
                    is_active: true,
                    semantics: resettablePipelineFixture.stages[1].semantics,
                },
                {
                    id: null,
                    stage_key: "under_review",
                    slug: "under_review",
                    label: "Under Review",
                    color: "#2563eb",
                    order: 3,
                    stage_type: "intake" as const,
                    is_active: true,
                    semantics: resettablePipelineFixture.stages[2].semantics,
                },
                {
                    id: null,
                    stage_key: "transfer_cycle",
                    slug: "transfer_cycle",
                    label: "Transfer Cycle Initiated",
                    color: "#0f766e",
                    order: 4,
                    stage_type: "post_approval" as const,
                    is_active: true,
                    semantics: {
                        ...resettablePipelineFixture.stages[3].semantics,
                        capabilities: {
                            ...resettablePipelineFixture.stages[3].semantics.capabilities,
                            locks_match_state: true,
                        },
                        analytics_bucket: "transfer_cycle",
                    },
                },
                {
                    ...pipelineFixture.stages[3],
                    id: null,
                },
            ],
            feature_config: {
                ...resettablePipelineFixture.feature_config,
                journey: {
                    phases: [],
                    milestones: [
                        {
                            slug: "application_intake",
                            label: "Application & Intake",
                            description: "Initial application received.",
                            mapped_stage_keys: ["new_unread", "application_submitted"],
                            is_soft: false,
                        },
                    ],
                },
                analytics: {
                    funnel_stage_keys: ["new_unread", "application_submitted", "under_review"],
                    performance_stage_keys: ["application_submitted", "under_review", "transfer_cycle"],
                    qualification_stage_key: "application_submitted",
                    conversion_stage_key: "transfer_cycle",
                },
            },
        }

        mockUsePipelines.mockReturnValue({
            data: [resettablePipelineFixture],
            isLoading: false,
        })
        mockUsePipeline.mockReturnValue({
            data: resettablePipelineFixture,
            isLoading: false,
        })
        mockUsePipelineDependencyGraph.mockReturnValue({
            data: resettableDependencyGraph,
            isLoading: false,
        })
        mockUseRecommendedPipelineDraft.mockResolvedValue(recommendedResetDraft)

        const consoleError = vi.spyOn(console, "error").mockImplementation(() => {})

        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /reset to default/i }))

        await waitFor(() => {
            expect(mockUseRecommendedPipelineDraft).toHaveBeenCalledWith({
                id: "p1",
                entityType: "surrogate",
            })
        })
        await waitFor(() => {
            expect(screen.getByDisplayValue("Application Submitted")).toBeInTheDocument()
        })

        fireEvent.click(screen.getByRole("button", { name: /save changes/i }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })

        const call = mockApplyPipelineDraft.mock.calls[0][0]
        expect(call.data.remaps).toEqual([
            {
                removed_stage_key: "application_packet_received",
                target_stage_key: "application_submitted",
            },
            {
                removed_stage_key: "panel_review",
                target_stage_key: "under_review",
            },
            {
                removed_stage_key: "transfer_readiness",
                target_stage_key: "transfer_cycle",
            },
        ])

        const duplicateKeyWarnings = consoleError.mock.calls.filter((args) =>
            args.some((arg) => String(arg).includes("Encountered two children with the same key")),
        )
        expect(duplicateKeyWarnings).toHaveLength(0)
        consoleError.mockRestore()
    })

    it("marks changes immediately and delays preview payloads until edits settle", () => {
        vi.useFakeTimers()

        render(<PipelinesSettingsPage />)

        const labelInputs = screen.getAllByPlaceholderText("Label")
        fireEvent.change(labelInputs[1] as HTMLInputElement, {
            target: { value: "Contacted Updated" },
        })

        expect(screen.getByText("Unsaved changes")).toBeInTheDocument()
        expect(mockUsePipelineChangePreview.mock.lastCall?.[1]).toBeNull()
        expect(mockUsePipelineChangePreview.mock.lastCall?.[3]).toBe("")

        act(() => {
            vi.advanceTimersByTime(1199)
        })

        expect(mockUsePipelineChangePreview.mock.lastCall?.[1]).toBeNull()

        act(() => {
            vi.advanceTimersByTime(1)
        })

        expect(mockUsePipelineChangePreview.mock.lastCall?.[1]).toMatchObject({
            stages: expect.arrayContaining([
                expect.objectContaining({ label: "Contacted Updated" }),
            ]),
        })
        expect(mockUsePipelineChangePreview.mock.lastCall?.[3]).toEqual(
            expect.any(String),
        )

        vi.useRealTimers()
    })

    it("deletes a stage with a remap target and applies the draft", async () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /remove contacted/i }))
        fireEvent.mouseDown(screen.getByRole("combobox", { name: "Remap target stage" }))
        const remapOption = await screen.findByRole("option", { name: "New Unread" })
        fireEvent.mouseMove(remapOption)
        fireEvent.click(remapOption)
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
            expect(mockRollbackPipeline).toHaveBeenCalledWith({
                id: "p1",
                version: 1,
                entityType: "surrogate",
            })
        })
    })

    it("switches to intended-parent scope from the shared entity dropdown and hides surrogate-only editors", async () => {
        render(<PipelinesSettingsPage />)

        const entitySelect = screen.getByRole("combobox", { name: "Entity" })
        expect(entitySelect.tagName).toBe("BUTTON")

        fireEvent.mouseDown(entitySelect)
        const intendedParentOption = await screen.findByRole("option", { name: "Intended Parents" })
        fireEvent.mouseMove(intendedParentOption)
        fireEvent.click(intendedParentOption)

        expect(mockUsePipelines).toHaveBeenLastCalledWith("intended_parent")
        expect(screen.queryByText("Journey Mapping")).not.toBeInTheDocument()
        expect(screen.queryByText("Analytics Funnel")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /edit details for ready to match/i }))

        expect(screen.getByText("2 active records")).toBeInTheDocument()
        expect(screen.queryByText("Integration bucket")).not.toBeInTheDocument()
        expect(screen.queryByText("Suggestion profile")).not.toBeInTheDocument()
        expect(screen.queryByText("Analytics bucket")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: /hide details for ready to match/i })).toBeInTheDocument()
    })
})
