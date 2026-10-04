import { assert, beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import PipelinesSettingsPage from "../app/(app)/settings/pipelines/page"
import { DEFAULT_STAGE_SEMANTICS_BY_KEY, STAGE_DEFS } from "@/lib/constants/stages.generated"
import type { Pipeline, PipelineFeatureConfig, PipelineStage } from "@/lib/api/pipelines"
import { IMPACT_PREVIEW_ID } from "@/lib/pipelines/stage-editor"
import { stageDisplayColor } from "@/lib/stage-colors"

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

const mockCan = vi.fn()
const mockIsMobile = vi.fn(() => false)

vi.mock("@/hooks/use-mobile", () => ({
    useIsMobile: () => mockIsMobile(),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockCan(permission),
    }),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
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
    useRecommendedPipelineDraft: (id: string | null, entityType?: string) => ({
        refetch: () => mockUseRecommendedPipelineDraft(id, entityType),
        isFetching: false,
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
    ] satisfies [PipelineStage, PipelineStage, PipelineStage, PipelineStage],
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
            ] satisfies [PipelineFeatureConfig["journey"]["milestones"][number]],
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

let currentSurrogatePipeline: Pipeline = pipelineFixture

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

function buildPreQualifiedPipelineFixture() {
    const preQualifiedStage = {
        ...pipelineFixture.stages[1],
        id: "s-pre",
        stage_key: "pre_qualified",
        slug: "pre_qualified",
        label: "Pre-Qualified",
        color: "#10b981",
        order: 3,
        semantics: {
            ...pipelineFixture.stages[1].semantics,
            analytics_bucket: "pre_qualified",
            suggestion_profile_key: "qualified_followup",
        },
    }
    const applicationSubmittedStage = {
        ...pipelineFixture.stages[1],
        id: "s-app",
        stage_key: "application_submitted",
        slug: "application_submitted",
        label: "Application Submitted",
        color: "#8b5cf6",
        order: 4,
        semantics: {
            ...pipelineFixture.stages[1].semantics,
            analytics_bucket: "application_submitted",
            suggestion_profile_key: "application_submitted_followup",
        },
    }
    const stages = [
        pipelineFixture.stages[0],
        pipelineFixture.stages[1],
        preQualifiedStage,
        applicationSubmittedStage,
        ...pipelineFixture.stages.slice(2).map((stage, index) => ({
            ...stage,
            order: index + 5,
        })),
    ]
    return {
        ...pipelineFixture,
        stages,
        feature_config: {
            ...pipelineFixture.feature_config,
            journey: {
                ...pipelineFixture.feature_config.journey,
                milestones: [
                    {
                        ...pipelineFixture.feature_config.journey.milestones[0],
                        mapped_stage_keys: [
                            "new_unread",
                            "contacted",
                            "pre_qualified",
                            "application_submitted",
                        ],
                    },
                ],
            },
            analytics: {
                ...pipelineFixture.feature_config.analytics,
                funnel_stage_keys: [
                    "new_unread",
                    "contacted",
                    "pre_qualified",
                    "application_submitted",
                ],
                performance_stage_keys: [
                    "contacted",
                    "pre_qualified",
                    "application_submitted",
                    "lost",
                ],
                qualification_stage_key: "pre_qualified",
            },
        },
    }
}

function buildPreQualifiedDependencyGraphFixture(
    pipeline: ReturnType<typeof buildPreQualifiedPipelineFixture>,
) {
    return {
        pipeline_id: pipeline.id,
        version: pipeline.current_version,
        stages: pipeline.stages.map((stage) => ({
            stage_id: stage.id,
            stage_key: stage.stage_key,
            slug: stage.slug,
            label: stage.label,
            category: stage.stage_type,
            stage_type: stage.stage_type,
            is_active: stage.is_active,
            surrogate_count: stage.stage_key === "pre_qualified" ? 55 : 0,
            journey_milestone_slugs:
                stage.stage_key === "pre_qualified" ? ["application_intake"] : [],
            analytics_funnel: stage.stage_key === "pre_qualified",
            intelligent_suggestion_rules: [],
            integration_refs:
                stage.stage_key === "pre_qualified"
                    ? ["zapier_outbound", "meta_crm_dataset"]
                    : [],
            campaign_refs: [],
            workflow_refs: [],
            role_visibility_roles: [],
            role_mutation_roles: [],
        })),
    }
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

        mockIsMobile.mockReturnValue(false)
        mockUseAuth.mockReturnValue({ user: { role: "admin" } })
        mockCan.mockReset()
        mockCan.mockImplementation((permission: string) => permission === "manage_pipelines")
        mockUsePipelines.mockImplementation((entityType?: string) => ({
            data: [
                entityType === "intended_parent"
                    ? intendedParentPipelineFixture
                    : pipelineFixture,
            ],
            isLoading: false,
        }))
        mockUsePipeline.mockImplementation((_id: string | null, entityType?: string) => ({
            data: entityType === "intended_parent"
                ? intendedParentPipelineFixture
                : currentSurrogatePipeline,
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
        currentSurrogatePipeline = pipelineFixture
    })

    it("edits label, slug and type inline and keeps the stage key in the drawer", () => {
        render(<PipelinesSettingsPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Pipelines" })).toBeInTheDocument()
        expect(screen.getByLabelText("Stage 2 label")).toHaveValue("Contacted")
        expect(screen.getByLabelText("Stage 2 slug")).toBeEnabled()
        expect(screen.getByRole("combobox", { name: "Stage 2 type" })).toBeEnabled()
        expect(screen.getByRole("combobox", { name: "Stage 2 behavior preset" })).toHaveTextContent("Contacted")
        expect(screen.queryByLabelText("Stage key")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Open New Unread settings" }))

        expect(screen.getByLabelText("Stage key")).toBeDisabled()
    })

    it("renders protected stages as locked system stages and disables their controls", () => {
        render(<PipelinesSettingsPage />)

        const lockedRow = screen.getByTestId("stage-row-s1")
        expect(within(lockedRow).getByText("New Unread")).toBeInTheDocument()
        expect(within(lockedRow).queryByRole("textbox")).not.toBeInTheDocument()
        expect(within(lockedRow).queryByRole("combobox")).not.toBeInTheDocument()
        expect(within(lockedRow).getByLabelText("System stage")).toBeInTheDocument()
        expect(lockedRow.querySelector("[data-drag-handle]")).toBeNull()
        expect(screen.getByTestId("stage-row-s2").querySelector("[data-drag-handle]")).not.toBeNull()
        expect(screen.queryByRole("button", { name: /duplicate new unread/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /remove new unread/i })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Open New Unread settings" }))

        const drawer = screen.getByRole("dialog", { name: "New Unread" })
        expect(within(drawer).getByLabelText("Label")).toBeDisabled()
        expect(within(drawer).getByLabelText("Slug")).toBeDisabled()
        expect(within(drawer).getByRole("combobox", { name: /type for new unread/i })).toBeDisabled()
        expect(within(drawer).getByLabelText(/behavior preset for new unread/i)).toBeDisabled()
        expect(within(drawer).getByLabelText("New Unread color")).toBeDisabled()
        expect(within(drawer).getByRole("checkbox", { name: "Counts as contacted" })).toHaveAttribute(
            "aria-disabled",
            "true",
        )
        expect(within(drawer).queryByRole("button", { name: /move new unread/i })).not.toBeInTheDocument()
        expect(within(drawer).queryByRole("button", { name: "Duplicate" })).not.toBeInTheDocument()
        expect(within(drawer).queryByRole("button", { name: "Remove" })).not.toBeInTheDocument()
        expect(within(drawer).getByText(/locked because platform workflows depend on it/i)).toBeInTheDocument()
    })

    it("locks the interview stages in order and hides their removal actions", () => {
        const interviewStages = STAGE_DEFS.filter((stage) =>
            ["interview_scheduled", "reschedule_needed"].includes(stage.stageKey),
        ).map((stage) => {
            const semantics = DEFAULT_STAGE_SEMANTICS_BY_KEY[stage.stageKey]
            assert.isDefined(semantics)
            return {
                ...pipelineFixture.stages[0],
                id: stage.stageKey,
                stage_key: stage.stageKey,
                slug: stage.slug,
                label: stage.label,
                color: stage.color,
                semantics,
                system_role: stage.stageKey,
            }
        })
        currentSurrogatePipeline = {
            ...pipelineFixture,
            stages: [
                ...pipelineFixture.stages.slice(0, 2),
                ...interviewStages,
                ...pipelineFixture.stages.slice(2),
            ].map((stage, index) => ({ ...stage, order: index + 1 })),
        }

        render(<PipelinesSettingsPage />)

        for (const [stageKey, label] of [
            ["interview_scheduled", "Interview Scheduled"],
            ["reschedule_needed", "Reschedule Needed"],
        ] as const) {
            const row = screen.getByTestId(`stage-row-${stageKey}`)
            expect(within(row).getByText(label)).toBeInTheDocument()
            expect(within(row).queryByRole("textbox")).not.toBeInTheDocument()
            expect(screen.queryByRole("button", { name: `Remove ${label}` })).not.toBeInTheDocument()
            expect(screen.queryByRole("button", { name: `Duplicate ${label}` })).not.toBeInTheDocument()
        }
        expect(screen.getByTestId("stage-order-interview_scheduled")).toHaveTextContent("3")
        expect(screen.getByTestId("stage-order-reschedule_needed")).toHaveTextContent("4")
    })

    it("shows duplicate and remove only on unlocked rows", () => {
        render(<PipelinesSettingsPage />)

        const lockedRow = screen.getByTestId("stage-row-s1")
        const editableRow = screen.getByTestId("stage-row-s2")

        expect(screen.getByTestId("stage-order-s1")).toHaveTextContent("1")
        expect(screen.getByTestId("stage-order-s2")).toHaveTextContent("2")
        expect(within(editableRow).getByRole("button", { name: /duplicate contacted/i })).toBeInTheDocument()
        expect(within(editableRow).getByRole("button", { name: /remove contacted/i })).toBeInTheDocument()
        expect(within(lockedRow).getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
            "Open New Unread settings",
        ])
    })

    it("keeps the settings button as the trailing action in every stage row", () => {
        render(<PipelinesSettingsPage />)

        const lockedButtons = within(screen.getByTestId("stage-row-s1")).getAllByRole("button")
        const editableButtons = within(screen.getByTestId("stage-row-s2")).getAllByRole("button")

        expect(lockedButtons.at(-1)).toHaveAccessibleName("Open New Unread settings")
        expect(editableButtons.at(-1)).toHaveAccessibleName("Open Contacted settings")
    })

    it("opens the drawer when a row is clicked outside its inline controls", () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByLabelText("Stage 2 label"))
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

        fireEvent.click(screen.getByTestId("stage-order-s2"))
        expect(screen.getByRole("dialog", { name: "Contacted" })).toBeInTheDocument()
    })

    it("puts the entity selector, version badge and version history in the page header", async () => {
        render(<PipelinesSettingsPage />)

        const entityGroup = screen.getByRole("group", { name: "Entity" })
        expect(within(entityGroup).getByRole("button", { name: "Surrogates" })).toHaveAttribute(
            "aria-pressed",
            "true",
        )
        expect(screen.getByText("v2")).toBeInTheDocument()
        expect(screen.queryByText("Version History")).not.toBeInTheDocument()
        expect(mockUsePipelineVersions).not.toHaveBeenCalled()

        fireEvent.click(screen.getByRole("button", { name: "Version history" }))

        const sheet = await screen.findByRole("dialog", { name: "Version history" })
        expect(within(sheet).getByText("v2")).toBeInTheDocument()
        expect(within(sheet).getByText("Current")).toBeInTheDocument()
        expect(within(sheet).queryByText("No version history")).not.toBeInTheDocument()
    })

    it("lists v1 as the initial version when no snapshots are stored", async () => {
        currentSurrogatePipeline = { ...pipelineFixture, current_version: 1 }
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Version history" }))

        const sheet = await screen.findByRole("dialog", { name: "Version history" })
        expect(within(sheet).getByText("v1")).toBeInTheDocument()
        expect(within(sheet).getByText("Initial version")).toBeInTheDocument()
    })

    it("shows a version history load error instead of a role message", async () => {
        mockUsePipelineVersions.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new Error("boom"),
            refetch: vi.fn(),
            isFetching: false,
        })
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Version history" }))

        const sheet = await screen.findByRole("dialog", { name: "Version history" })
        expect(within(sheet).getByText("Couldn't load version history")).toBeInTheDocument()
        expect(within(sheet).queryByText(/requires developer role/i)).not.toBeInTheDocument()
    })

    it("shows the denied state and loads nothing without manage_pipelines", () => {
        mockCan.mockReturnValue(false)

        render(<PipelinesSettingsPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Pipelines" })).toBeInTheDocument()
        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(mockUsePipelines).not.toHaveBeenCalled()
        expect(screen.queryByRole("button", { name: "Add Custom Stage" })).not.toBeInTheDocument()
    })

    it("shows a load error instead of an empty editor", () => {
        mockUsePipelines.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new Error("boom"),
            refetch: vi.fn(),
            isFetching: false,
        })
        mockUsePipeline.mockReturnValue({ data: undefined, isLoading: false })

        render(<PipelinesSettingsPage />)

        expect(screen.getByText("Couldn't load the pipeline")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add Custom Stage" })).not.toBeInTheDocument()
    })

    it("labels stage categories and keeps the current category of an unlocked terminal stage", async () => {
        currentSurrogatePipeline = {
            ...pipelineFixture,
            stages: [
                ...pipelineFixture.stages,
                {
                    ...pipelineFixture.stages[1],
                    id: "s5",
                    stage_key: "cold_leads",
                    slug: "cold_leads",
                    label: "Cold Leads",
                    order: 5,
                    stage_type: "terminal" as const,
                },
            ],
        }
        render(<PipelinesSettingsPage />)

        expect(screen.getByRole("combobox", { name: "Stage 2 type" })).toHaveTextContent("Intake")
        expect(within(screen.getByTestId("stage-row-s4")).getByText("Terminal")).toBeInTheDocument()
        const coldLeadsCategory = screen.getByRole("combobox", { name: "Stage 5 type" })
        expect(coldLeadsCategory).toHaveTextContent("Terminal")
        expect(coldLeadsCategory).toBeEnabled()

        fireEvent.mouseDown(coldLeadsCategory)
        const options = await screen.findAllByRole("option")
        expect(options.map((option) => option.textContent)).toEqual(["Intake", "Post-approval", "Terminal"])
        expect(screen.getByRole("option", { name: "Terminal" })).toHaveAttribute("aria-disabled", "true")
    })

    it("opens every stage setting in the stage drawer", async () => {
        render(<PipelinesSettingsPage />)

        expect(screen.queryByText("Behavior preset")).not.toBeInTheDocument()
        expect(screen.queryByText("Journey: Application & Intake")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Open Contacted settings" }))

        const drawer = screen.getByRole("dialog", { name: "Contacted" })
        for (const label of [
            "Label",
            "Slug",
            "Stage key",
            "Type",
            "Color",
            "Position",
            "Behavior preset",
            "Integration bucket",
            "Pause behavior",
            "Terminal outcome",
            "Suggestion profile",
            "Analytics bucket",
            "Journey milestones",
            "Analytics funnel",
        ]) {
            expect(within(drawer).getAllByText(label).length).toBeGreaterThan(0)
        }
        expect(within(drawer).getByText("2 of 4")).toBeInTheDocument()
        expect(within(drawer).getByRole("checkbox", { name: "Eligible for matching" })).toHaveAttribute(
            "aria-disabled",
            "true",
        )
        expect(within(drawer).getByRole("checkbox", { name: "Counts as contacted" })).not.toHaveAttribute(
            "aria-disabled",
        )
        expect(within(drawer).getByRole("checkbox", { name: "Require reason on enter" })).not.toHaveAttribute(
            "aria-disabled",
        )
        expect(within(drawer).getByText("3 active surrogates")).toBeInTheDocument()
        expect(within(drawer).getByText("Journey: Application & Intake")).toBeInTheDocument()
        expect(within(drawer).getByRole("combobox", { name: /journey milestones for contacted/i })).toHaveTextContent(
            "Application & Intake",
        )
        expect(within(drawer).getByRole("switch", { name: "Analytics funnel" })).toBeChecked()
        expect(within(drawer).getByRole("button", { name: "Duplicate" })).toBeInTheDocument()
        expect(within(drawer).getByRole("button", { name: "Remove" })).toBeInTheDocument()

        fireEvent.click(within(drawer).getByRole("button", { name: "Done" }))
        await waitFor(() => {
            expect(screen.queryByRole("dialog", { name: "Contacted" })).not.toBeInTheDocument()
        })
    })

    it("keeps the drawer on its stage when refreshed data assigns new database IDs", () => {
        const view = render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Open Contacted settings" }))
        expect(screen.getByRole("dialog", { name: "Contacted" })).toBeInTheDocument()

        currentSurrogatePipeline = {
            ...pipelineFixture,
            current_version: 3,
            stages: pipelineFixture.stages.map((stage) => ({
                ...stage,
                id: `refreshed-${stage.id}`,
            })),
        }
        view.rerender(<PipelinesSettingsPage />)

        expect(screen.getByRole("dialog", { name: "Contacted" })).toBeInTheDocument()
        expect(screen.getByText("Behavior preset")).toBeInTheDocument()
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

    it("truncates the mapped stage chip and keeps the overflow count visible", () => {
        currentSurrogatePipeline = {
            ...pipelineFixture,
            feature_config: {
                ...pipelineFixture.feature_config,
                journey: {
                    ...pipelineFixture.feature_config.journey,
                    milestones: [
                        {
                            ...pipelineFixture.feature_config.journey.milestones[0],
                            mapped_stage_keys: ["new_unread", "contacted", "on_hold", "lost"],
                        },
                    ],
                },
            },
        }

        render(<PipelinesSettingsPage />)

        const milestoneRow = screen
            .getByRole("button", { name: /edit details for application & intake/i })
            .closest(".rounded-xl") as HTMLElement
        const labels = within(milestoneRow).getByText("New Unread, Contacted")
        expect(labels).toHaveClass("truncate")
        expect(labels.parentElement).toHaveClass("max-w-full")
        expect(labels.parentElement?.parentElement).toHaveClass("min-w-0")
        expect(labels.nextElementSibling).toHaveTextContent("+2")
    })

    it("keeps journey milestone details expanded across equivalent pipeline refreshes", () => {
        const view = render(<PipelinesSettingsPage />)

        fireEvent.click(
            screen.getByRole("button", { name: /edit details for application & intake/i }),
        )
        expect(
            screen.getByRole("button", { name: /hide details for application & intake/i }),
        ).toHaveAttribute("aria-expanded", "true")

        currentSurrogatePipeline = {
            ...pipelineFixture,
            current_version: 3,
            feature_config: {
                ...pipelineFixture.feature_config,
                journey: {
                    ...pipelineFixture.feature_config.journey,
                    milestones: pipelineFixture.feature_config.journey.milestones.map(
                        (milestone) => ({ ...milestone }),
                    ),
                },
            },
        }
        view.rerender(<PipelinesSettingsPage />)

        expect(
            screen.getByRole("button", { name: /hide details for application & intake/i }),
        ).toHaveAttribute("aria-expanded", "true")
        expect(
            screen.getByLabelText("Application & Intake includes New Unread"),
        ).toBeInTheDocument()
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
        fireEvent.change(screen.getByDisplayValue("New Stage"), {
            target: { value: "Matching Review" },
        })
        fireEvent.change(screen.getByDisplayValue("custom_stage"), {
            target: { value: "matching_review" },
        })

        const saveBar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(saveBar).getByText("1 unsaved change")).toBeInTheDocument()
        fireEvent.click(within(saveBar).getByRole("button", { name: "Save changes" }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })

        assert.isDefined(mockApplyPipelineDraft.mock.calls[0])
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

    it("focuses the new stage label after Add Custom Stage", () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))

        const newLabel = screen.getByDisplayValue("New Stage")
        expect(newLabel).toHaveFocus()
    })

    it("shows an inline error for an empty label and blocks Save", () => {
        render(<PipelinesSettingsPage />)

        const labelInput = screen.getByLabelText("Stage 2 label") as HTMLInputElement
        fireEvent.change(labelInput, { target: { value: " " } })

        expect(labelInput).toHaveAttribute("aria-invalid", "true")
        expect(screen.getByText("Enter a stage label.")).toBeInTheDocument()
        const saveBar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(saveBar).getByRole("button", { name: "Save changes" })).toBeDisabled()

        labelInput.blur()
        fireEvent.click(within(saveBar).getByRole("button", { name: "1 error" }))
        expect(labelInput).toHaveFocus()
    })

    it("keeps system stages locked after Reset to Default", async () => {
        mockUseRecommendedPipelineDraft.mockResolvedValue({
            data: {
                name: pipelineFixture.name,
                stages: pipelineFixture.stages.map((stage) => ({
                    id: null,
                    stage_key: stage.stage_key,
                    slug: stage.slug,
                    label: stage.label,
                    color: stage.color,
                    order: stage.order,
                    stage_type: stage.stage_type,
                    is_active: true,
                    semantics: stage.semantics,
                })),
                feature_config: pipelineFixture.feature_config,
            },
        })
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /reset to default/i }))

        await waitFor(() => {
            expect(mockUseRecommendedPipelineDraft).toHaveBeenCalled()
        })
        await waitFor(() => {
            expect(screen.getByRole("button", { name: /reset to default/i })).toBeEnabled()
        })
        expect(within(screen.getAllByTestId(/^stage-row-/)[0] as HTMLElement).queryByRole("textbox")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /remove new unread/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /remove lost/i })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: /remove contacted/i })).toBeInTheDocument()
        expect(screen.getAllByLabelText("System stage")).toHaveLength(3)
    })

    it("assigns an intake preset color to new custom stages instead of gray", () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))
        fireEvent.click(screen.getByRole("button", { name: "Open New Stage settings" }))

        expect(screen.getByLabelText("New Stage color hex")).toHaveValue(stageDisplayColor("#14b8a6"))
    })

    it("recolors draft stages from stage keywords while the user is naming them", () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))
        fireEvent.change(screen.getByDisplayValue("New Stage"), {
            target: { value: "Pending-DocuSign" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Open Pending-DocuSign settings" }))

        expect(screen.getByLabelText("Pending-DocuSign color hex")).toHaveValue(stageDisplayColor("#f59e0b"))
    })

    it("assigns a post-approval preset color when adding a custom intended-parent stage", async () => {
        mockUsePipelines.mockImplementation(() => ({
            data: [intendedParentPipelineFixture],
            isLoading: false,
        }))
        mockUsePipeline.mockImplementation(() => ({
            data: intendedParentPipelineFixture,
            isLoading: false,
        }))
        mockUsePipelineDependencyGraph.mockImplementation(() => ({
            data: intendedParentDependencyGraphFixture,
            isLoading: false,
        }))
        mockUsePipelineChangePreview.mockImplementation((_id: string | null, draft: unknown) => ({
            data: draft ? intendedParentPreviewFixture : null,
            isLoading: false,
        }))

        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))
        fireEvent.click(screen.getByRole("button", { name: "Open New Stage settings" }))

        expect(screen.getByLabelText("New Stage color hex")).toHaveValue(stageDisplayColor("#4f46e5"))
    })

    it("labels intended-parent record remap reasons", () => {
        mockUsePipelines.mockImplementation(() => ({
            data: [intendedParentPipelineFixture],
            isLoading: false,
        }))
        mockUsePipeline.mockImplementation(() => ({
            data: intendedParentPipelineFixture,
            isLoading: false,
        }))
        mockUsePipelineDependencyGraph.mockImplementation(() => ({
            data: intendedParentDependencyGraphFixture,
            isLoading: false,
        }))
        mockUsePipelineChangePreview.mockImplementation((_id: string | null, draft: unknown) => ({
            data: draft
                ? {
                      ...intendedParentPreviewFixture,
                      required_remaps: [
                          {
                              stage_key: "secondary_review",
                              label: "Secondary Review",
                              surrogate_count: 1,
                              reasons: ["records", "workflows"],
                          },
                      ],
                  }
                : null,
            isLoading: false,
        }))

        vi.useFakeTimers()
        try {
            render(<PipelinesSettingsPage />)

            fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))
            act(() => {
                vi.advanceTimersByTime(1200)
            })

            expect(
                screen.getByText("Secondary Review: Records, Workflow references"),
            ).toBeInTheDocument()
            expect(screen.queryByText(/records, workflows/)).not.toBeInTheDocument()
        } finally {
            vi.useRealTimers()
        }
    })

    it("rehydrates saved gray custom stages with suggested colors", () => {
        const colorizedPipelineFixture = {
            ...pipelineFixture,
            stages: [
                pipelineFixture.stages[0],
                pipelineFixture.stages[1],
                {
                    id: "gray-stage",
                    stage_key: "pending_docusign",
                    slug: "pending_docusign",
                    label: "Pending-DocuSign",
                    color: "#6B7280",
                    order: 3,
                    stage_type: "post_approval" as const,
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
                        analytics_bucket: "under_review",
                        suggestion_profile_key: "under_review_followup",
                        requires_reason_on_enter: false,
                    },
                },
                ...pipelineFixture.stages.slice(2).map((stage, index) => ({
                    ...stage,
                    order: index + 4,
                })),
            ],
        }
        const colorizedDependencyGraphFixture = {
            ...dependencyGraphFixture,
            stages: colorizedPipelineFixture.stages.map((stage) => ({
                stage_id: stage.id,
                stage_key: stage.stage_key,
                slug: stage.slug,
                label: stage.label,
                category: stage.stage_type,
                stage_type: stage.stage_type,
                is_active: stage.is_active,
                surrogate_count: 0,
                journey_milestone_slugs: [],
                analytics_funnel: false,
                intelligent_suggestion_rules: [],
                integration_refs: [],
                campaign_refs: [],
                workflow_refs: [],
                role_visibility_roles: [],
                role_mutation_roles: [],
            })),
        }
        const colorizedPreviewFixture = {
            ...previewFixture,
            dependency_graph: colorizedDependencyGraphFixture,
        }

        mockUsePipelines.mockImplementation(() => ({
            data: [colorizedPipelineFixture],
            isLoading: false,
        }))
        mockUsePipeline.mockImplementation(() => ({
            data: colorizedPipelineFixture,
            isLoading: false,
        }))
        mockUsePipelineDependencyGraph.mockImplementation(() => ({
            data: colorizedDependencyGraphFixture,
            isLoading: false,
        }))
        mockUsePipelineChangePreview.mockImplementation((_id: string | null, draft: unknown) => ({
            data: draft ? colorizedPreviewFixture : null,
            isLoading: false,
        }))

        render(<PipelinesSettingsPage />)
        fireEvent.click(screen.getByRole("button", { name: "Open Pending-DocuSign settings" }))

        expect(screen.getByLabelText("Pending-DocuSign color hex")).toHaveValue(stageDisplayColor("#f59e0b"))
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
            ] satisfies [PipelineStage, PipelineStage, PipelineStage, PipelineStage, PipelineStage],
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
        mockUseRecommendedPipelineDraft.mockResolvedValue({ data: recommendedResetDraft })

        const consoleError = vi.spyOn(console, "error").mockImplementation(() => {})

        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /reset to default/i }))

        await waitFor(() => {
            expect(mockUseRecommendedPipelineDraft).toHaveBeenCalledWith("p1", "surrogate")
        })
        await waitFor(() => {
            expect(screen.getByDisplayValue("Application Submitted")).toBeInTheDocument()
        })

        fireEvent.click(screen.getByRole("button", { name: /save changes/i }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })

        assert.isDefined(mockApplyPipelineDraft.mock.calls[0])
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

        fireEvent.change(screen.getByLabelText("Stage 2 label"), {
            target: { value: "Contacted Updated" },
        })

        expect(screen.getByRole("region", { name: "Unsaved changes" })).toBeInTheDocument()
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

        assert.isDefined(mockApplyPipelineDraft.mock.calls[0])
        const call = mockApplyPipelineDraft.mock.calls[0][0]
        expect(call.data.remaps).toEqual([
            {
                removed_stage_key: "contacted",
                target_stage_key: "new_unread",
            },
        ])
    })

    it("requires and preselects a remap target when removing pre-qualified with integration dependencies", async () => {
        const preQualifiedPipeline = buildPreQualifiedPipelineFixture()
        const preQualifiedDependencyGraph = buildPreQualifiedDependencyGraphFixture(preQualifiedPipeline)
        const preQualifiedPreview = {
            ...previewFixture,
            impact_areas: ["analytics", "integrations", "journey", "ui_gating"],
            dependency_graph: preQualifiedDependencyGraph,
        }
        mockUsePipelines.mockReturnValue({
            data: [preQualifiedPipeline],
            isLoading: false,
        })
        mockUsePipeline.mockReturnValue({
            data: preQualifiedPipeline,
            isLoading: false,
        })
        mockUsePipelineDependencyGraph.mockReturnValue({
            data: preQualifiedDependencyGraph,
            isLoading: false,
        })
        mockUsePipelineChangePreview.mockImplementation((_id: string | null, draft: unknown) => ({
            data: draft ? preQualifiedPreview : null,
            isLoading: false,
        }))

        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: /remove pre-qualified/i }))
        const dialog = screen.getByRole("dialog")

        expect(within(dialog).getByText(/55 active surrogates/i)).toBeInTheDocument()
        expect(within(dialog).getByText(/integration mappings/i)).toBeInTheDocument()
        expect(within(dialog).getByText(/remap target is required/i)).toBeInTheDocument()
        expect(within(dialog).getByRole("combobox", { name: "Remap target stage" })).toHaveTextContent(
            "Application Submitted",
        )

        fireEvent.mouseDown(within(dialog).getByRole("combobox", { name: "Remap target stage" }))
        expect(screen.queryByRole("option", { name: "No remap" })).not.toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole("button", { name: /confirm removal/i }))
        fireEvent.click(screen.getByRole("button", { name: /save changes/i }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })

        assert.isDefined(mockApplyPipelineDraft.mock.calls[0])
        const call = mockApplyPipelineDraft.mock.calls[0][0]
        expect(call.data.remaps).toEqual([
            {
                removed_stage_key: "pre_qualified",
                target_stage_key: "application_submitted",
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

        fireEvent.click(screen.getByRole("button", { name: "Version history" }))
        fireEvent.click(await screen.findByRole("button", { name: /restore/i }))

        await waitFor(() => {
            expect(mockRollbackPipeline).toHaveBeenCalledWith({
                id: "p1",
                version: 1,
                entityType: "surrogate",
            })
        })
    })

    it("switches to intended-parent scope from the header entity selector and hides surrogate-only editors", async () => {
        render(<PipelinesSettingsPage />)

        const entityGroup = screen.getByRole("group", { name: "Entity" })
        fireEvent.click(within(entityGroup).getByRole("button", { name: "Intended Parents" }))

        expect(mockUsePipelines).toHaveBeenLastCalledWith("intended_parent")
        expect(within(entityGroup).getByRole("button", { name: "Intended Parents" })).toHaveAttribute(
            "aria-pressed",
            "true",
        )
        expect(screen.queryByText("Journey Mapping")).not.toBeInTheDocument()
        expect(screen.queryByText("Analytics Funnel")).not.toBeInTheDocument()

        expect(screen.queryByRole("columnheader", { name: "Journey milestone" })).not.toBeInTheDocument()
        expect(screen.getByRole("columnheader", { name: "Records" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Open Ready to Match settings" }))

        const drawer = screen.getByRole("dialog", { name: "Ready to Match" })
        expect(within(drawer).getByText("2 records")).toBeInTheDocument()
        expect(within(drawer).queryByText("Integration bucket")).not.toBeInTheDocument()
        expect(within(drawer).queryByText("Suggestion profile")).not.toBeInTheDocument()
        expect(within(drawer).queryByText("Analytics bucket")).not.toBeInTheDocument()
        expect(within(drawer).queryByText("Journey and funnel")).not.toBeInTheDocument()
    })

    it("offers no pause behavior for intended parent stages and keeps the reason requirement", () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Open Contacted settings" }))
        expect(screen.getByText("Pause behavior")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Done" }))

        const entityGroup = screen.getByRole("group", { name: "Entity" })
        fireEvent.click(within(entityGroup).getByRole("button", { name: "Intended Parents" }))
        fireEvent.click(screen.getByRole("button", { name: "Open Ready to Match settings" }))

        expect(screen.queryByText("Pause behavior")).not.toBeInTheDocument()
        expect(screen.queryByRole("combobox", { name: /pause behavior/i })).not.toBeInTheDocument()
        expect(screen.getByRole("checkbox", { name: /require reason on enter/i })).toBeInTheDocument()
    })

    it("exposes separately configurable egg- and sperm-donor pipelines", async () => {
        render(<PipelinesSettingsPage />)

        const entityGroup = screen.getByRole("group", { name: "Entity" })
        const eggDonors = within(entityGroup).getByRole("button", { name: "Egg Donors" })
        const spermDonors = within(entityGroup).getByRole("button", { name: "Sperm Donors" })

        fireEvent.click(eggDonors)

        expect(mockUsePipelines).toHaveBeenLastCalledWith("egg_donor")
        expect(eggDonors).toHaveAttribute("aria-pressed", "true")
        expect(screen.queryByText("Journey Mapping")).not.toBeInTheDocument()
        expect(screen.queryByText("Analytics Funnel")).not.toBeInTheDocument()

        fireEvent.click(spermDonors)

        expect(mockUsePipelines).toHaveBeenLastCalledWith("sperm_donor")
        expect(spermDonors).toHaveAttribute("aria-pressed", "true")
        expect(eggDonors).toHaveAttribute("aria-pressed", "false")
    })

    it("labels the seeded behavior of unlocked post-approval default stages instead of Unknown option", () => {
        const medicalClearance = STAGE_DEFS.find((stage) => stage.stageKey === "medical_clearance_passed")
        assert.isDefined(medicalClearance)
        currentSurrogatePipeline = {
            ...pipelineFixture,
            stages: [
                ...pipelineFixture.stages,
                {
                    id: "s-medical",
                    stage_key: medicalClearance.stageKey,
                    slug: medicalClearance.slug,
                    label: medicalClearance.label,
                    color: medicalClearance.color,
                    order: pipelineFixture.stages.length + 1,
                    stage_type: "post_approval" as const,
                    is_active: true,
                    is_locked: false,
                    system_role: null,
                    lock_reason: null,
                    locked_fields: [],
                    semantics: DEFAULT_STAGE_SEMANTICS_BY_KEY[medicalClearance.stageKey],
                },
            ],
        } as Pipeline
        render(<PipelinesSettingsPage />)

        expect(within(screen.getByTestId("stage-row-s-medical")).getByText("Matched")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Open Medical Clearance Passed settings" }))

        const drawer = screen.getByRole("dialog", { name: "Medical Clearance Passed" })
        const preset = within(drawer).getByRole("combobox", { name: /behavior preset for medical clearance passed/i })
        expect(preset).toHaveTextContent("Matched")
        expect(preset).not.toHaveTextContent("Unknown option")
    })

    it("saves the darkened display color when a light color is picked", async () => {
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Open Contacted settings" }))
        const drawer = screen.getByRole("dialog", { name: "Contacted" })
        expect(within(drawer).getByLabelText("Contacted color hex")).toHaveValue(stageDisplayColor("#06b6d4"))

        fireEvent.change(within(drawer).getByLabelText("Contacted color"), { target: { value: "#fde68a" } })

        const saved = stageDisplayColor("#fde68a")
        expect(saved).not.toBe("#FDE68A")
        expect(within(drawer).getByLabelText("Contacted color hex")).toHaveValue(saved)
        expect(within(drawer).getByText("#FDE68A")).toBeInTheDocument()
        expect(within(drawer).getByText(saved)).toBeInTheDocument()

        fireEvent.click(within(drawer).getByRole("button", { name: "Done" }))
        await waitFor(() => {
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
        })
        fireEvent.click(within(screen.getByRole("region", { name: "Unsaved changes" })).getByRole("button", { name: "Save changes" }))

        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })
        const call = mockApplyPipelineDraft.mock.calls[0]?.[0]
        expect(
            call.data.stages.find((stage: { stage_key?: string }) => stage.stage_key === "contacted")?.color,
        ).toBe(saved)
    })

    it("shows the preview impact areas in the save bar", () => {
        vi.useFakeTimers()
        render(<PipelinesSettingsPage />)

        fireEvent.change(screen.getByLabelText("Stage 2 label"), { target: { value: "Contacted Updated" } })
        act(() => {
            vi.advanceTimersByTime(1200)
        })

        const saveBar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(saveBar).getByText(/^Impact/)).toBeInTheDocument()
        expect(within(saveBar).getByText("UI gating and actions")).toBeInTheDocument()
        vi.useRealTimers()
    })

    it("lists stages on phones and opens a full-screen stage page", () => {
        mockIsMobile.mockReturnValue(true)
        render(<PipelinesSettingsPage />)

        expect(screen.queryByRole("table")).not.toBeInTheDocument()
        const list = screen.getByRole("list", { name: "Stages" })
        fireEvent.click(within(list).getByRole("button", { name: /contacted/i }))

        expect(screen.getByRole("heading", { level: 2, name: "Contacted" })).toBeInTheDocument()
        expect(screen.queryByRole("list", { name: "Stages" })).not.toBeInTheDocument()
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
        fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Reached" } })

        expect(screen.getByRole("region", { name: "Unsaved changes" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Back to stages" }))
        expect(within(screen.getByRole("list", { name: "Stages" })).getByRole("button", { name: /reached/i })).toBeInTheDocument()
    })

    it("moves focus into the phone stage page and back to the stage row", () => {
        mockIsMobile.mockReturnValue(true)
        render(<PipelinesSettingsPage />)

        const contactedRow = within(screen.getByRole("list", { name: "Stages" })).getByRole("button", { name: /contacted/i })
        contactedRow.focus()
        fireEvent.click(contactedRow)
        expect(screen.getByRole("heading", { level: 2, name: "Contacted" })).toHaveFocus()

        fireEvent.click(screen.getByRole("button", { name: "Back to stages" }))
        expect(within(screen.getByRole("list", { name: "Stages" })).getByRole("button", { name: /contacted/i })).toHaveFocus()

        fireEvent.click(screen.getByRole("button", { name: "Add Custom Stage" }))
        expect(screen.getByDisplayValue("New Stage")).toHaveFocus()

        fireEvent.click(screen.getByRole("button", { name: "Back to stages" }))
        expect(within(screen.getByRole("list", { name: "Stages" })).getByRole("button", { name: /new stage/i })).toHaveFocus()
    })

    it("opens the phone stage with a field error and focuses the field from the save bar", () => {
        mockIsMobile.mockReturnValue(true)
        render(<PipelinesSettingsPage />)

        fireEvent.click(within(screen.getByRole("list", { name: "Stages" })).getByRole("button", { name: /contacted/i }))
        fireEvent.change(screen.getByLabelText("Label"), { target: { value: " " } })
        fireEvent.click(screen.getByRole("button", { name: "Back to stages" }))

        const saveBar = screen.getByRole("region", { name: "Unsaved changes" })
        fireEvent.click(within(saveBar).getByRole("button", { name: "1 error" }))

        const labelInput = screen.getByLabelText("Label")
        expect(labelInput).toHaveAttribute("aria-invalid", "true")
        expect(labelInput).toHaveFocus()
    })

    it("returns to the phone stage list and focuses server validation errors from the save bar", () => {
        vi.useFakeTimers()
        mockIsMobile.mockReturnValue(true)
        const validationError = "Custom stages must stay after the first protected stage."
        mockUsePipelineChangePreview.mockImplementation((_id: string | null, draft: unknown) => ({
            data: draft ? { ...previewFixture, validation_errors: [validationError] } : null,
            isLoading: false,
        }))
        render(<PipelinesSettingsPage />)

        fireEvent.click(within(screen.getByRole("list", { name: "Stages" })).getByRole("button", { name: /contacted/i }))
        fireEvent.click(screen.getByRole("button", { name: "Move Contacted up" }))
        act(() => {
            vi.advanceTimersByTime(1200)
        })

        const saveBar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(saveBar).getByRole("button", { name: "Save changes" })).toBeDisabled()
        fireEvent.click(within(saveBar).getByRole("button", { name: "1 error" }))

        expect(screen.getByRole("list", { name: "Stages" })).toBeInTheDocument()
        expect(screen.getByText(validationError)).toBeInTheDocument()
        expect(document.getElementById(IMPACT_PREVIEW_ID)).toHaveFocus()
        vi.useRealTimers()
    })

    it("reorders unlocked stages on phones with up and down buttons", async () => {
        mockIsMobile.mockReturnValue(true)
        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Reorder" }))

        expect(screen.getByRole("heading", { level: 2, name: "Reorder stages" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Move New Unread up" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Move Contacted down" }))
        fireEvent.click(screen.getByRole("button", { name: "Done" }))

        const labels = within(screen.getByRole("list", { name: "Stages" }))
            .getAllByRole("button")
            .map((button) => button.textContent ?? "")
        expect(labels.findIndex((text) => text.includes("Contacted"))).toBe(2)
        fireEvent.click(within(screen.getByRole("region", { name: "Unsaved changes" })).getByRole("button", { name: "Save changes" }))
        await waitFor(() => {
            expect(mockApplyPipelineDraft).toHaveBeenCalled()
        })
    })
})
