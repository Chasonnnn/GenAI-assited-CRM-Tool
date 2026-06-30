import { describe, it, expect } from "vitest"
import { existsSync, readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"

function readSource(pathFromWebRoot: string): string {
    return readFileSync(join(process.cwd(), pathFromWebRoot), "utf8")
}

function sourceExists(pathFromWebRoot: string): boolean {
    return existsSync(join(process.cwd(), pathFromWebRoot))
}

function stripTemplateLiteralBodies(source: string): string {
    let stripped = ""
    let inTemplateLiteral = false
    let escaped = false

    for (const char of source) {
        if (!inTemplateLiteral) {
            stripped += char
            if (char === "`") {
                inTemplateLiteral = true
            }
            continue
        }

        if (escaped) {
            stripped += char === "\n" ? "\n" : " "
            escaped = false
            continue
        }

        if (char === "\\") {
            stripped += " "
            escaped = true
            continue
        }

        if (char === "`") {
            stripped += char
            inTemplateLiteral = false
            continue
        }

        stripped += char === "\n" ? "\n" : " "
    }

    return stripped
}

function expectTypeOrInterfaceNotExported(source: string, typeName: string): void {
    expect(source, typeName).not.toContain(`export interface ${typeName} {`)
    expect(source, typeName).not.toContain(`export type ${typeName} =`)
}

function readApiModuleSources(): Array<{ path: string; source: string }> {
    const apiDir = join(process.cwd(), "lib/api")
    const sources: Array<{ path: string; source: string }> = []

    for (const fileName of readdirSync(apiDir)) {
        if (!fileName.endsWith(".ts") || fileName === "index.ts") continue

        const path = `lib/api/${fileName}`
        sources.push({ path, source: readSource(path) })
    }

    return sources
}

describe("React regression guards (source)", () => {
    it("uses stable IDs for editable automation rows", () => {
        const source = readSource("app/(app)/automation/page.client.tsx")

        expect(source).toContain("key={condition.clientId}")
        expect(source).toContain("key={action.clientId}")
        expect(source).not.toMatch(/conditions\.map\(\(condition, index\) => \(\s*<Card key=\{index\}>/m)
        expect(source).not.toMatch(/actions\.map\(\(action, index\) => \(\s*<Card key=\{index\}>/m)
    })

    it("keeps automation route search param parsing in the server wrapper", () => {
        const source = readSource("app/(app)/automation/page.tsx")

        expect(source).toContain('import AutomationPageClient from "./page.client"')
        expect(source).not.toContain("useSearchParams")
        expect(source).toContain("<AutomationPageClient")
    })

    it("uses stable IDs for platform workflow template rows", () => {
        const source = readSource("app/ops/templates/workflows/[id]/page.client.tsx")

        expect(source).toContain('from "@/components/automation/workflow-editor/shared"')
        expect(source).toContain("type EditableCondition,")
        expect(source).toContain("type EditableAction,")
        expect(source).toContain("key={condition.clientId}")
        expect(source).toContain("key={action.clientId}")
        expect(source).not.toMatch(/conditions\.map\(\(condition, index\) => \(\s*<Card key=\{`condition-\$\{index\}`\}>/m)
        expect(source).not.toMatch(/actions\.map\(\(action, index\) => \(\s*<Card key=\{`action-\$\{index\}`\}>/m)
    })

    it("keeps platform workflow save and publish compiler-compatible", () => {
        const source = readSource("app/ops/templates/workflows/[id]/page.client.tsx")

        expect(source).not.toContain("finally")
        expect(source).toContain('toast.success("Template saved")')
        expect(source).toContain('toast.success("Template published")')
    })

    it("does not suppress exhaustive deps in MassEditStageModal and handles late stage load", () => {
        const source = readSource("components/surrogates/MassEditStageModal.tsx")

        expect(source).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(source).toContain("const defaultTargetStageId = React.useMemo")
        expect(source).toContain("if (!open || targetStageId || !defaultTargetStageId) return")
        expect(source).toContain("const previewSignature = React.useMemo")
        expect(source).toContain("previewState?.signature === previewSignature")
        expect(source).toContain("function massEditStageReducer")
        expect(source).toContain("const [state, dispatch] = React.useReducer(")
        expect(source).toContain("massEditStageReducer,")
        expect(source).not.toContain("setStatesInput")
        expect(source).not.toContain("setPreviewState")
        expect(source).not.toContain("setPreview(null)")
    })

    it("derives open alert count instead of storing duplicate state", () => {
        const source = readSource("app/ops/agencies/[orgId]/page.client.tsx")

        expect(source).toContain("const openAlertCount = orgAlerts.filter")
        expect(source).not.toContain("const [openAlertCount, setOpenAlertCount] = useState")
    })

    it("uses reducer-based local state in CSVUpload", () => {
        const source = readSource("components/import/CSVUpload.tsx")

        expect(source).toContain("const [state, dispatch] = useReducer")
        expect(source).toContain("function csvUploadReducer(")
    })

    it("keeps DateTimePicker draft state and default month hydration-safe", () => {
        const source = readSource("components/ui/date-time-picker.tsx")

        expect(source).toContain("function getDraftFromValue(")
        expect(source).toContain("setDraft(getDraftFromValue(value))")
        expect(source).not.toContain("React.useState<Date | undefined>(value)")
        expect(source).not.toContain(
            "React.useEffect(() => {\n        if (!open) return\n        setDraft(getDraftFromValue(value))"
        )
        expect(source).not.toContain("defaultMonth={draftDate || new Date()}")
    })

    it("keeps calendar RTL class names compiler-friendly", () => {
        const source = readSource("components/ui/calendar.tsx")

        expect(source).toContain('"rtl:**:[.rdp-button\\\\_next>svg]:rotate-180"')
        expect(source).toContain('"rtl:**:[.rdp-button\\\\_previous>svg]:rotate-180"')
        expect(source).not.toContain("String.raw`rtl:**:[.rdp-button\\_")
    })

    it("keeps browser notification permission initialization compiler-friendly", () => {
        const source = readSource("app/(app)/settings/notifications/page.tsx")

        expect(source).toContain("function getBrowserNotificationPermission")
        expect(source).toContain("useState(getBrowserNotificationPermission)")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("finally")
    })

    it("keeps ThemeToggle out of document-driven view transitions", () => {
        const source = readSource("components/theme-toggle.tsx")

        expect(source).not.toContain("document.startViewTransition")
        expect(source).not.toContain("document.documentElement.style.setProperty")
    })

    it("keeps RichTextPreview hydration-safe without mount-only state", () => {
        const source = readSource("components/rich-text-preview.tsx")

        expect(source).not.toContain("const [mounted")
        expect(source).not.toContain("setMounted(true)")
        expect(source).not.toContain("useEditor")
        expect(source).toContain("TrustedSanitizedHtmlContent")
    })

    it("keeps interview comment anchor highlighting single-pass", () => {
        const source = readSource("components/surrogates/interviews/InterviewComments/index.tsx")

        expect(source).toContain("EXISTING_COMMENT_ID_REGEX")
        expect(source).not.toContain('result.includes(`data-comment-id="${note.comment_id}"`)')
        expect(source).not.toMatch(/for \(const note of notes\)[\s\S]*new RegExp/)
    })

    it("keeps interview comment context compiler-friendly", () => {
        const source = readSource("components/surrogates/interviews/InterviewComments/context.tsx")

        expect(source).toContain("function resolveMutationResult")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("export function getMinSidebarHeight")
        expect(source).not.toContain("finally")
        expect(source).not.toMatch(/try \{\s+await onAddNote/)
    })

    it("keeps interview tab context compiler-friendly", () => {
        const source = readSource("components/surrogates/interviews/InterviewTab/context.tsx")

        expect(source).toContain("function buildInterviewFormState")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("finally")
        expect(source).not.toContain('if (dialog.type === "editor")')
    })

    it("uses Set membership for attachment upload extension validation", () => {
        const source = readSource("components/FileUploadZone.tsx")

        expect(source).toContain("const ALLOWED_EXTENSION_SET = new Set")
        expect(source).toContain("ALLOWED_EXTENSION_SET.has(ext)")
        expect(source).toContain("uploadAcceptedFilesSequentially")
        expect(source).not.toContain("ALLOWED_EXTENSIONS.includes(ext)")
        expect(source).not.toContain("for (const file of acceptedFiles)")
    })

    it("keeps palette search and stage keyword matching efficient", () => {
        const paletteSource = readSource("components/forms/FormBuilderPalette.tsx")
        const stageColorSource = readSource("lib/pipeline-stage-colors.ts")
        const pipelineRemapSource = readSource("lib/pipeline-reset-remaps.ts")

        expect(paletteSource).toContain("escapeRegExp")
        expect(paletteSource).toContain("searchPattern.test")
        expect(paletteSource).not.toContain(".toLowerCase().indexOf(normalizedSearch)")
        expect(stageColorSource).toContain("text.includes(keyword)")
        expect(stageColorSource).not.toContain("text.indexOf(keyword)")
        expect(pipelineRemapSource).toContain("for (const candidate of candidates)")
        expect(pipelineRemapSource).not.toMatch(/candidates\s*\.filter\(\(candidate\) => candidate\.stage_key\)\s*\.map/)
    })

    it("batches support-session popup styles", () => {
        const source = readSource("components/ops/agencies/SupportSessionDialog.tsx")

        expect(source).toContain("supportSessionReducer")
        expect(source).toContain("useReducer")
        expect(source).toContain("applyPopupStyles")
        expect(source).toContain(".style.cssText")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("finally")
        expect(source).not.toContain(".style.fontSize")
        expect(source).not.toContain(".style.opacity")
        expect(source).not.toContain(".style.padding")
        expect(source).not.toContain(".style.margin")
    })

    it("keeps dashboard KPI chart code split and private", () => {
        const source = readSource("app/(app)/dashboard/components/kpi-card.tsx")

        expect(source).toContain('import dynamic from "next/dynamic"')
        expect(source).not.toContain('from "recharts"')
        expect(source).not.toContain("KPICardSkeleton")
    })

    it("keeps dashboard distribution charts code split from Recharts", () => {
        const sources = [
            readSource("app/(app)/dashboard/components/stage-chart.tsx"),
            readSource("app/(app)/dashboard/components/trend-chart.tsx"),
        ]

        for (const source of sources) {
            expect(source).toContain('import dynamic from "next/dynamic"')
            expect(source).toContain('import("recharts")')
            expect(source).not.toContain('from "recharts"')
            expect(source).not.toContain('from "@/components/ui/chart"')
        }
    })

    it("keeps report chart surfaces code split from Recharts", () => {
        const sources = [
            readSource("components/reports/TeamPerformanceChart.tsx"),
            readSource("components/reports/MetaSpendDashboard.tsx"),
            readSource("app/(app)/reports/components/ReportsChartsGrid.tsx"),
        ]

        for (const source of sources) {
            expect(source).toContain('import dynamic from "next/dynamic"')
            expect(source).toContain('import("recharts")')
            expect(source).not.toContain('from "recharts"')
            expect(source).not.toContain('from "@/components/ui/chart"')
        }
    })

    it("uses Next Image for journey, AI studio, and platform branding images", () => {
        const sources = [
            readSource("components/surrogates/journey/JourneyPrintView.tsx"),
            readSource("components/surrogates/journey/MilestoneImageSelector.tsx"),
            readSource("components/surrogates/journey/JourneyMilestoneCard.tsx"),
            readSource("app/(app)/ai-studio/page.tsx"),
            readSource("app/ops/templates/system/[systemKey]/page.client.tsx"),
        ]

        for (const source of sources) {
            expect(source).toContain('import Image from "next/image"')
            expect(stripTemplateLiteralBodies(source)).not.toMatch(/^\s*<img\b/m)
        }
    })

    it("keeps AI Studio settings and reference images compiler-friendly", () => {
        const source = readSource("app/(app)/ai-studio/page.tsx")

        expect(source).toContain("function buildSettingsFormState")
        expect(source).toContain("const openSettingsDialog =")
        expect(source).not.toContain("useEffect(() =>")
        expect(source).not.toContain("useMemo(")
        expect(source).not.toContain("finally")
    })

    it("builds journey timeline milestone metadata without mutating a global counter", () => {
        const source = readSource("components/surrogates/journey/JourneyTimeline.tsx")

        expect(source).toContain("nextIndex")
        expect(source).not.toContain("let globalIndex")
        expect(source).not.toContain("globalIndex++")
    })

    it("keeps surrogate journey tab compiler-friendly", () => {
        const source = readSource("components/surrogates/journey/SurrogateJourneyTab.tsx")

        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("finally")
    })

    it("keeps milestone image selection draft state compiler-friendly", () => {
        const source = readSource("components/surrogates/journey/MilestoneImageSelector.tsx")

        expect(source).toContain("type ImageSelectionState")
        expect(source).toContain("useQueries")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("finally")
        expect(source).not.toContain("setSelectedId(currentAttachmentId)")
    })

    it("keeps sessions revoke handlers compiler-friendly", () => {
        const source = readSource("app/(app)/settings/sessions/page.tsx")

        expect(source).toContain("setRevokingSessionId(null)")
        expect(source).not.toContain("finally")
    })

    it("keeps surrogate application form-link defaults compiler-friendly", () => {
        const source = readSource("components/surrogates/SurrogateApplicationTab.tsx")

        expect(source).toContain('aria-label="Upload application file"')
        expect(source).not.toContain("setSelectedTemplateId(emailTemplates[0]?.id")
        expect(source).not.toContain("setSelectedIntakeLinkId(sendableIntakeLinks[0]?.id")
        expect(source).not.toContain("setUploadFieldKey(fileFields[0]?.key")
        expect(source).not.toContain("finally")
    })

    it("keeps surrogate overview inline editors compiler-friendly", () => {
        const source = readSource("components/surrogates/detail/tabs/SurrogateOverviewTab.tsx")

        expect(source).not.toContain("React.useEffect")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("finally")
    })

    it("imports the API client directly from leaf API modules", () => {
        for (const { path, source } of readApiModuleSources()) {
            expect(source, path).not.toMatch(/from ['"]\.\/index['"]/)
            expect(source, path).not.toMatch(/from ['"]@\/lib\/api['"]/)
        }
    })

    it("keeps route client components on a single public export style", () => {
        const source = readSource("app/(app)/surrogates/page.client.tsx")

        expect(source).toContain("export function SurrogatesPageClient")
        expect(source).not.toContain("export default SurrogatesPageClient")
    })

    it("does not show assignee filters to intake users", () => {
        const source = readSource("app/(app)/surrogates/page.client.tsx")

        expect(source).not.toContain("useAccessibleSurrogateOwners")
        expect(source).not.toContain("canUseIntakePoolFilter")
        expect(source).toContain("const canFilterByAssignee = canUseOrgAssigneeFilter")
        expect(source).toContain("getAssigneeFilterLabel(value, assigneeFilterOptions)")
        expect(source).not.toContain("getAssigneeFilterLabel(ownerFilter, assignees)")
    })

    it("does not expose intake pool grants in team settings", () => {
        const source = readSource("app/(app)/settings/team/members/[id]/page.client.tsx")

        expect(source).not.toContain("useIntakePoolGrants")
        expect(source).not.toContain("useCreateIntakePoolGrant")
        expect(source).not.toContain("useRevokeIntakePoolGrant")
        expect(source).not.toContain("Intake Pool Access")
    })

    it("keeps test-only factories and interview internals private", () => {
        const handlersSource = readSource("tests/mocks/handlers.ts")
        const interviewWrapperSource = readSource("components/surrogates/interviews/SurrogateInterviewTab.tsx")
        const interviewApiSource = readSource("lib/api/interviews.ts")

        expect(handlersSource).not.toContain("export const mockSurrogate")
        expect(handlersSource).not.toContain("export const mockUser")
        expect(handlersSource).not.toContain("export const mockPermission")
        expect(interviewWrapperSource).not.toContain("useInterviewTab,")
        expect(interviewWrapperSource).not.toContain("type DialogState")
        expect(interviewWrapperSource).not.toContain("type UploadState")
        expect(interviewWrapperSource).not.toContain("type FormState")
        expect(interviewApiSource).not.toContain("export type TranscriptionStatus")
    })

    it("keeps unused task and stage helper exports out of public modules", () => {
        const taskTypesSource = readSource("lib/types/task.ts")
        const taskApiSource = readSource("lib/api/tasks.ts")
        const stageContextSource = readSource("lib/surrogate-stage-context.ts")
        const generatedStagesSource = readSource("lib/constants/stages.generated.ts")

        expect(taskTypesSource).toContain("export type { TaskListItem }")
        expect(taskTypesSource).not.toContain("export type TaskType")
        expect(taskTypesSource).not.toContain("TaskRead")
        expect(taskTypesSource).not.toContain("TaskListResponse")
        expect(taskTypesSource).not.toContain("TaskListParams")
        expect(taskTypesSource).not.toContain("TaskCreatePayload")
        expect(taskTypesSource).not.toContain("TaskUpdatePayload")
        expect(taskTypesSource).not.toContain("TASK_TYPE_CONFIG")
        expect(taskApiSource).not.toContain("export type TaskType")
        expect(stageContextSource).not.toContain("export function roleRuleMatchesStage")
        expect(stageContextSource).not.toContain("export function getStageSemanticKey")
        expect(generatedStagesSource).not.toContain("export type RoleStageRule")
        expect(generatedStagesSource).not.toContain("ROLE_STAGE_VISIBILITY")
        expect(generatedStagesSource).not.toContain("ROLE_STAGE_MUTATION")
    })

    it("keeps unused appointment override web wrappers out of public modules", () => {
        const appointmentApiSource = readSource("lib/api/appointments.ts")
        const appointmentHooksSource = readSource("lib/hooks/use-appointments.ts")

        expect(appointmentApiSource).not.toContain("export interface AvailabilityOverride")
        expect(appointmentApiSource).not.toContain("export interface AvailabilityOverrideCreate")
        expect(appointmentApiSource).not.toContain("export function getAvailabilityOverrides")
        expect(appointmentApiSource).not.toContain("export function createAvailabilityOverride")
        expect(appointmentApiSource).not.toContain("export function deleteAvailabilityOverride")
        expect(appointmentHooksSource).not.toContain("useAvailabilityOverrides")
        expect(appointmentHooksSource).not.toContain("useCreateAvailabilityOverride")
        expect(appointmentHooksSource).not.toContain("useDeleteAvailabilityOverride")
    })

    it("keeps unused public form and analytics API helpers private", () => {
        const formsApiSource = readSource("lib/api/forms.ts")
        const analyticsApiSource = readSource("lib/api/analytics.ts")

        expect(formsApiSource).not.toContain("deleteSharedPublicFormDraft")
        expect(analyticsApiSource).not.toContain("exportAnalyticsPDF")
        expect(analyticsApiSource).not.toContain("export interface ActivityFeedItem")
        expect(analyticsApiSource).not.toContain("export interface SpendSyncStatus")
    })

    it("keeps nested form API subtype aliases private", () => {
        const source = readSource("lib/api/forms.ts")
        const privateSubtypeNames = [
            "FormStatus",
            "FormSubmissionStatus",
            "FormLinkMode",
            "SharedSubmissionOutcome",
            "EmbedHealthCheckStatus",
            "EmbedHealthStatus",
            "ConditionOperator",
            "TableColumnType",
            "SharedDraftLookupStatus",
            "SharedDraftMatchReason",
        ]

        for (const typeName of privateSubtypeNames) {
            expect(source).not.toContain(`export type ${typeName}`)
        }
        expect(source).not.toContain("export interface FormPage")
        expect(source).not.toContain("export interface FormEmbedConsentRead")
        expect(source).not.toContain("export interface FormEmbedHealthCheckRead")
    })

    it("keeps nested platform template and campaign API types private", () => {
        const source = readSource("lib/api/platform.ts")

        expect(source).not.toContain("export interface PlatformSystemEmailCampaignTarget")
        expect(source).not.toContain("export interface PlatformSystemEmailCampaignFailure")
        expect(source).not.toContain("export type TemplateStatus")
        expect(source).not.toContain("export interface PlatformEmailTemplateDraft")
        expect(source).not.toContain("export interface PlatformFormTemplateDraft")
        expect(source).not.toContain("export interface PlatformWorkflowTemplateDraft")
    })

    it("keeps nested permissions API response types private", () => {
        const source = readSource("lib/api/permissions.ts")

        expect(source).not.toContain("export interface PermissionOverride")
        expect(source).not.toContain("export interface RolePermission")
    })

    it("keeps form mapping options on a direct endpoint request", () => {
        const source = readSource("lib/api/forms.ts")

        expect(source).toContain('api.get<unknown>("/forms/mapping-options")')
        expect(source).not.toContain("const endpointCandidates")
        expect(source).not.toContain("for (const endpoint of endpointCandidates)")
    })

    it("keeps submission mutation hooks on static API imports", () => {
        const source = readSource("lib/hooks/use-forms.ts")

        expect(source).toContain("updateSubmissionAnswers,")
        expect(source).toContain("uploadSubmissionFile,")
        expect(source).toContain("deleteSubmissionFile,")
        expect(source).not.toContain("await import('@/lib/api/forms')")
    })

    it("keeps unused email template version helpers out of public modules", () => {
        const apiSource = readSource("lib/api/email-templates.ts")
        const hookSource = readSource("lib/hooks/use-email-templates.ts")

        expect(apiSource).not.toContain("export interface EmailTemplateVersion")
        expect(apiSource).not.toContain("export async function getTemplateVersions")
        expect(apiSource).not.toContain("export async function rollbackTemplate")
        expect(hookSource).not.toContain("useTemplateVersions")
        expect(hookSource).not.toContain("useRollbackTemplate")
    })

    it("keeps unused UI subcomponent exports out of public modules", () => {
        const carouselSource = readSource("components/ui/carousel.tsx")
        const chartSource = readSource("components/ui/chart.tsx")
        const fieldSource = readSource("components/ui/field.tsx")
        const selectSource = readSource("components/ui/select.tsx")
        const tabsSource = readSource("components/ui/tabs.tsx")
        const badgeSource = readSource("components/ui/badge.tsx")
        const dialogSource = readSource("components/ui/dialog.tsx")
        const tableSource = readSource("components/ui/table.tsx")
        const scrollAreaSource = readSource("components/ui/scroll-area.tsx")
        const avatarSource = readSource("components/ui/avatar.tsx")
        const dropdownSource = readSource("components/ui/dropdown-menu.tsx")
        const alertDialogSource = readSource("components/ui/alert-dialog.tsx")
        const sheetSource = readSource("components/ui/sheet.tsx")
        const calendarSource = readSource("components/ui/calendar.tsx")
        const popoverSource = readSource("components/ui/popover.tsx")
        const progressSource = readSource("components/ui/progress.tsx")
        const commandSource = readSource("components/ui/command.tsx")
        const inputGroupSource = readSource("components/ui/input-group.tsx")

        expect(carouselSource).not.toContain("CarouselContent")
        expect(carouselSource).not.toContain("CarouselItem")
        expect(carouselSource).not.toContain("CarouselPrevious")
        expect(carouselSource).not.toContain("CarouselNext")
        expect(carouselSource).not.toContain("useCarousel")
        expect(carouselSource).not.toContain("type CarouselApi,")
        expect(chartSource).not.toMatch(/export \{[\s\S]*ChartStyle/)
        expect(fieldSource).not.toContain("FieldLegend")
        expect(fieldSource).not.toContain("FieldSeparator")
        expect(fieldSource).not.toContain("FieldSet")
        expect(fieldSource).not.toContain("FieldContent")
        expect(fieldSource).not.toContain("FieldTitle")
        expect(selectSource).not.toContain("SelectLabel")
        expect(selectSource).not.toContain("SelectSeparator")
        expect(tabsSource).not.toMatch(/export \{[\s\S]*tabsListVariants/)
        expect(badgeSource).not.toMatch(/export \{[\s\S]*badgeVariants/)
        expect(dialogSource).not.toMatch(/export \{[\s\S]*DialogOverlay/)
        expect(dialogSource).not.toMatch(/export \{[\s\S]*DialogPortal/)
        expect(tableSource).not.toContain("TableFooter")
        expect(tableSource).not.toContain("TableCaption")
        expect(scrollAreaSource).not.toMatch(/export \{[\s\S]*ScrollBar/)
        expect(avatarSource).not.toContain("AvatarGroup")
        expect(avatarSource).not.toContain("AvatarGroupCount")
        expect(avatarSource).not.toContain("AvatarBadge")
        expect(dropdownSource).not.toContain("DropdownMenuPortal")
        expect(dropdownSource).not.toContain("DropdownMenuCheckboxItem")
        expect(dropdownSource).not.toContain("DropdownMenuRadioGroup")
        expect(dropdownSource).not.toContain("DropdownMenuRadioItem")
        expect(dropdownSource).not.toContain("DropdownMenuShortcut")
        expect(alertDialogSource).not.toMatch(/export \{[\s\S]*AlertDialogOverlay/)
        expect(alertDialogSource).not.toMatch(/export \{[\s\S]*AlertDialogPortal/)
        expect(sheetSource).not.toContain("SheetTrigger")
        expect(sheetSource).not.toContain("SheetClose")
        expect(sheetSource).not.toContain("SheetFooter")
        expect(calendarSource).not.toMatch(/export \{[\s\S]*CalendarDayButton/)
        expect(popoverSource).not.toContain("PopoverDescription")
        expect(popoverSource).not.toContain("PopoverHeader")
        expect(popoverSource).not.toContain("PopoverTitle")
        expect(progressSource).not.toMatch(/export \{[\s\S]*ProgressTrack/)
        expect(progressSource).not.toMatch(/export \{[\s\S]*ProgressIndicator/)
        expect(progressSource).not.toContain("ProgressLabel")
        expect(progressSource).not.toContain("ProgressValue")
        expect(commandSource).not.toContain("CommandSeparator")
        expect(inputGroupSource).not.toContain("InputGroupButton")
        expect(inputGroupSource).not.toContain("InputGroupText")
        expect(inputGroupSource).not.toContain("InputGroupInput")
        expect(inputGroupSource).not.toContain("InputGroupTextarea")
    })

    it("keeps workflow editor field sets and multiselect private", () => {
        const source = readSource("components/automation/workflow-editor/shared.tsx")

        expect(source).not.toContain("export const BOOLEAN_FIELDS")
        expect(source).not.toContain("export const NUMBER_FIELDS")
        expect(source).not.toContain("export const DATE_FIELDS")
        expect(source).not.toContain("export function WorkflowMultiSelect")
    })

    it("keeps unused UI primitive inventory out of the bundle", () => {
        const unusedPrimitives = [
            "aspect-ratio",
            "breadcrumb",
            "button-group",
            "combobox",
            "context-menu",
            "drawer",
            "hover-card",
            "input-otp",
            "item",
            "kbd",
            "menubar",
            "native-select",
            "navigation-menu",
            "pagination",
            "resizable",
            "sidebar",
            "slider",
        ]

        for (const primitive of unusedPrimitives) {
            expect(sourceExists(`components/ui/${primitive}.tsx`), primitive).toBe(false)
        }
    })

    it("keeps task due category internals private", () => {
        const source = readSource("lib/utils/task-due.ts")

        expect(source).not.toContain("export function isOverdue")
        expect(source).not.toContain("export function isDueToday")
        expect(source).not.toContain("export function isDueTomorrow")
        expect(source).not.toContain("export function isDueThisWeek")
    })

    it("keeps pipeline response subtype aliases private", () => {
        const source = readSource("lib/api/pipelines.ts")

        expect(source).not.toContain("export type TerminalOutcome")
        expect(source).not.toContain("export type IntegrationBucket")
        expect(source).not.toContain("export interface JourneyMilestoneDefinition")
        expect(source).not.toContain("export interface JourneyPhaseDefinition")
        expect(source).not.toContain("export interface PipelineDraftStage")
        expect(source).not.toContain("export interface PipelineVersion")
        expect(source).not.toContain("export interface PipelineVersionsResponse")
    })

    it("keeps surrogate detail layout context internals private", () => {
        const clientSource = readSource("components/surrogates/detail/SurrogateDetailLayoutClient.tsx")
        const indexSource = readSource("components/surrogates/detail/SurrogateDetailLayout/index.tsx")
        const contextSource = readSource("components/surrogates/detail/SurrogateDetailLayout/context.tsx")

        expect(clientSource).not.toContain("useSurrogateDetailLayout")
        expect(indexSource).not.toContain("useSurrogateDetailLayout")
        expect(indexSource).not.toContain("SurrogateDetailLayoutContextValue")
        expect(contextSource).not.toContain("export function useSurrogateDetailLayout")
        expect(contextSource).not.toContain("export type SurrogateDetailLayoutContextValue")
        expect(contextSource).not.toContain("export interface SurrogateDetailDataContextValue")
        expect(contextSource).not.toContain("export interface SurrogateDetailTabsContextValue")
        expect(contextSource).not.toContain("export interface SurrogateDetailDialogContextValue")
        expect(contextSource).not.toContain("export interface SurrogateDetailQueueContextValue")
        expect(contextSource).not.toContain("export interface SurrogateDetailZoomContextValue")
        expect(contextSource).not.toContain("export interface SurrogateDetailActionsContextValue")
        expect(contextSource).toContain("const { push, replace } = useRouter()")
        expect(contextSource).not.toContain("const { get, toString } = searchParams")
        expect(contextSource).toContain("searchParams.toString()")
        expect(contextSource).toContain('searchParams.get("return_to")')
        expect(contextSource).not.toContain("const router = useRouter()")
        expect(contextSource).not.toContain("router.push")
        expect(contextSource).not.toContain("router.replace")
        expect(contextSource).not.toContain("[defaultPipeline?.feature_config, stageOptions, user?.role]")
        expect(contextSource).toContain("[defaultPipeline?.feature_config, stageOptions, user]")
    })

    it("keeps narrow utility API internals private", () => {
        const csrfSource = readSource("lib/csrf.ts")
        const platformSource = readSource("lib/api/platform.ts")
        const matchStageSource = readSource("lib/match-pipeline-stage-utils.ts")
        const matchStatusSource = readSource("lib/match-status-definitions.ts")
        const signatureSource = readSource("lib/api/signature.ts")
        const usStatesSource = readSource("lib/constants/us-states.ts")

        expect(csrfSource).not.toContain("export function getCsrfToken")
        expect(csrfSource).not.toContain("export { CSRF_HEADER }")
        expect(platformSource).not.toContain("revokeSupportSession")
        expect(platformSource).not.toContain("updateOrganization")
        expect(matchStageSource).not.toContain("export function getEligibleForMatchingStages")
        expect(matchStatusSource).not.toContain("export const MATCH_STATUS_BY_VALUE")
        expect(matchStatusSource).not.toContain("export function getMatchStatusDefinition")
        expect(matchStatusSource).not.toContain("export const MATCH_STATUS_OPTIONS")
        expect(signatureSource).not.toContain("export interface SignatureTemplate")
        expect(usStatesSource).not.toContain("export type USStateCode")
    })

    it("keeps integration test wrapper internals private", () => {
        const source = readSource("tests/utils/integration-wrapper.tsx")

        expect(source).not.toContain("export function createTestQueryClient")
        expect(source).not.toContain("export function IntegrationWrapper")
        expect(source).not.toContain("export { renderWithProviders as render }")
    })

    it("keeps component-local and form utility types private", () => {
        const heightSource = readSource("lib/height.ts")
        const builderDocumentSource = readSource("lib/forms/form-builder-document.ts")
        const appLinkSource = readSource("components/app-link.tsx")
        const versionHistorySource = readSource("components/version-history-modal.tsx")

        expect(heightSource).not.toContain("export function parseHeightFt")
        expect(builderDocumentSource).not.toContain("export type BuilderShowIfOperator")
        expect(appLinkSource).not.toContain("export type AppLinkProps")
        expect(versionHistorySource).not.toContain("export interface VersionItem")
    })

    it("keeps intended-parent option defaults private", () => {
        const trustFundingSource = readSource("lib/trust-funding-status.ts")
        const maritalStatusSource = readSource("lib/intended-parent-marital-status.ts")

        expect(trustFundingSource).not.toContain("export const DEFAULT_TRUST_FUNDING_STATUS_OPTIONS")
        expect(trustFundingSource).not.toContain("export type TrustFundingStatusOption")
        expect(maritalStatusSource).not.toContain("export const MARITAL_STATUS_VALUES")
        expect(maritalStatusSource).not.toContain("export type MaritalStatusOption")
        expect(maritalStatusSource).not.toContain("export const DEFAULT_MARITAL_STATUS_OPTIONS")
    })

    it("keeps schedule parser stream internals private", () => {
        const source = readSource("lib/api/schedule-parser.ts")

        expect(source).not.toContain("export interface ParseScheduleResponse")
        expect(source).not.toContain("export interface BulkTaskItem")
        expect(source).not.toContain("export interface BulkTaskCreateResponse")
        expect(source).not.toContain("export async function streamParseSchedule")
    })

    it("keeps the shared API client on a single default export", () => {
        const source = readSource("lib/api.ts")

        expect(source).toContain("const api =")
        expect(source).not.toContain("export const api =")
    })

    it("keeps journey API endpoints on named exports only", () => {
        const source = readSource("lib/api/journey.ts")

        expect(source).not.toContain("export default {")
    })

    it("keeps hook query key factories private", () => {
        const privateKeyFactories = [
            ["lib/hooks/use-ai-studio.ts", "aiStudioKeys"],
            ["lib/hooks/use-ai.ts", "aiKeys"],
            ["lib/hooks/use-analytics.ts", "analyticsKeys"],
            ["lib/hooks/use-appointments.ts", "bookingPreviewKeys"],
            ["lib/hooks/use-appointments.ts", "calendarKeys"],
            ["lib/hooks/use-audit.ts", "auditKeys"],
            ["lib/hooks/use-campaigns.ts", "campaignKeys"],
            ["lib/hooks/use-dashboard.ts", "dashboardKeys"],
            ["lib/hooks/use-email-templates.ts", "emailTemplateKeys"],
            ["lib/hooks/use-import.ts", "importKeys"],
            ["lib/hooks/use-interviews.ts", "interviewKeys"],
            ["lib/hooks/use-journey.ts", "journeyKeys"],
            ["lib/hooks/use-matches.ts", "matchEventKeys"],
            ["lib/hooks/use-meta-crm-dataset.ts", "metaCrmDatasetKeys"],
            ["lib/hooks/use-meta-oauth.ts", "metaOAuthKeys"],
            ["lib/hooks/use-metadata.ts", "metadataKeys"],
            ["lib/hooks/use-mfa.ts", "mfaKeys"],
            ["lib/hooks/use-notes.ts", "noteKeys"],
            ["lib/hooks/use-notifications.ts", "notificationKeys"],
            ["lib/hooks/use-ops.ts", "opsKeys"],
            ["lib/hooks/use-pipelines.ts", "pipelineKeys"],
            ["lib/hooks/use-platform-templates.ts", "platformTemplateKeys"],
            ["lib/hooks/use-profile.ts", "profileKeys"],
            ["lib/hooks/use-queues.ts", "queueKeys"],
            ["lib/hooks/use-resend.ts", "resendKeys"],
            ["lib/hooks/use-sessions.ts", "avatarKeys"],
            ["lib/hooks/use-sessions.ts", "sessionKeys"],
            ["lib/hooks/use-signature.ts", "signatureKeys"],
            ["lib/hooks/use-status-change-requests.ts", "statusChangeRequestKeys"],
            ["lib/hooks/use-surrogate-emails.ts", "surrogateEmailKeys"],
            ["lib/hooks/use-system.ts", "systemKeys"],
            ["lib/hooks/use-tickets.ts", "ticketKeys"],
            ["lib/hooks/use-user-integrations.ts", "integrationKeys"],
            ["lib/hooks/use-workflows.ts", "workflowKeys"],
        ]

        for (const [path, keyFactory] of privateKeyFactories) {
            expect(readSource(path), keyFactory).not.toContain(`export const ${keyFactory}`)
        }
    })

    it("keeps unused import hook response type re-exports private", () => {
        const source = readSource("lib/hooks/use-import.ts")

        expect(source).not.toContain("ImportSubmitResponse")
        expect(source).not.toContain("ImportApprovalResponse")
    })

    it("keeps unused user integration hook response type re-exports private", () => {
        const source = readSource("lib/hooks/use-user-integrations.ts")
        const unusedResponseTypes = [
            "IntegrationStatus",
            "ZoomStatusResponse",
            "CreateMeetingResponse",
            "SendZoomInviteResponse",
            "GoogleCalendarStatusResponse",
            "GoogleCalendarSyncResponse",
        ]

        for (const typeName of unusedResponseTypes) {
            expect(source).not.toContain(typeName)
        }
    })

    it("keeps unused match hook response type re-exports private", () => {
        const source = readSource("lib/hooks/use-matches.ts")

        expect(source).not.toContain("MatchListResponse")
        expect(source).not.toContain("MatchStatsResponse")
        expect(source).not.toContain("MatchRead")
        expect(source).not.toContain("export type { MatchEventCreate")
        expect(source).not.toContain("MatchEventRead")
        expect(source).not.toContain("MatchEventType")
        expect(source).not.toContain("MatchEventPersonType")
    })

    it("keeps label map internals private", () => {
        const surrogateFieldLabelsSource = readSource("lib/constants/surrogate-field-labels.ts")
        const usStatesSource = readSource("lib/constants/us-states.ts")

        expect(surrogateFieldLabelsSource).not.toContain("export const SURROGATE_FIELD_LABELS")
        expect(usStatesSource).not.toContain("export function getStateLabel")
    })

    it("keeps unused note payload aliases out of the public API", () => {
        const notesApiSource = readSource("lib/api/notes.ts")
        const noteTypesSource = readSource("lib/types/note.ts")

        expect(notesApiSource).not.toContain("NoteCreatePayload")
        expect(noteTypesSource).not.toContain("NoteCreatePayload")
    })

    it("keeps internal presentation and template aliases private", () => {
        const outcomeSource = readSource("lib/surrogate-outcome-presentation.ts")
        const templateVariableSource = readSource("lib/types/template-variable.ts")

        expect(outcomeSource).not.toContain("export type OutcomeTone")
        expect(templateVariableSource).not.toContain("export type TemplateVariableValueType")
    })

    it("keeps API payload subtype aliases private", () => {
        const aiStudioSource = readSource("lib/api/ai-studio.ts")
        const workflowMetricsSource = readSource("lib/api/workflow-metrics.ts")
        const surrogateEmailsSource = readSource("lib/api/surrogate-emails.ts")
        const surrogatesApiSource = readSource("lib/api/surrogates.ts")

        expect(aiStudioSource).not.toContain("export type AIStudioDraftStatus")
        expect(workflowMetricsSource).not.toContain("export type WorkflowMetricEventType")
        expect(surrogateEmailsSource).not.toContain("export interface SurrogateEmailTicketItem")
        expect(surrogatesApiSource).not.toContain("export interface SurrogateMassEditStagePreviewItem")
        expect(surrogatesApiSource).not.toContain("export interface SurrogateMassEditStageApplyFailure")
        expect(surrogatesApiSource).not.toContain("export interface SurrogateMassEditArchiveApplyFailure")
    })

    it("keeps ticket API response subtypes private", () => {
        const source = readSource("lib/api/tickets.ts")
        const privateTicketTypes = [
            "TicketLinkStatus",
            "TicketListItem",
            "TicketMessageAttachment",
            "TicketMessageOccurrence",
            "TicketMessage",
            "TicketEvent",
            "TicketNote",
            "TicketSurrogateCandidate",
            "TicketDetailResponse",
            "TicketListResponse",
            "TicketSendResult",
            "TicketSendIdentity",
            "TicketSendIdentityResponse",
        ]

        for (const typeName of privateTicketTypes) {
            expectTypeOrInterfaceNotExported(source, typeName)
        }
    })

    it("keeps system and Meta OAuth internal types private", () => {
        const systemSource = readSource("lib/api/system.ts")
        const metaOAuthSource = readSource("lib/api/meta-oauth.ts")

        expect(systemSource).not.toContain("export interface SystemHealth")
        expect(metaOAuthSource).not.toContain("export type ErrorCategory")
    })

    it("keeps unused Meta OAuth single-connection helpers out of public modules", () => {
        const apiSource = readSource("lib/api/meta-oauth.ts")
        const hookSource = readSource("lib/hooks/use-meta-oauth.ts")

        expect(apiSource).not.toContain("export async function getMetaConnection(")
        expect(apiSource).not.toContain("export function connectionNeedsReauth(")
        expect(hookSource).not.toContain("export function useMetaConnection(")
        expect(hookSource).not.toContain("export function useMetaAvailableAssets(")
    })

    it("keeps Meta CRM dataset response subtypes private", () => {
        const source = readSource("lib/api/meta-crm-dataset.ts")
        const privateDatasetTypes = [
            "MetaCrmDatasetSettings",
            "UpdateMetaCrmDatasetSettingsRequest",
            "MetaCrmDatasetOutboundTestRequest",
            "MetaCrmDatasetOutboundTestResponse",
            "MetaCrmDatasetEventStatus",
            "MetaCrmDatasetEvent",
            "MetaCrmDatasetEventsResponse",
            "MetaCrmDatasetEventsSummary",
        ]

        for (const typeName of privateDatasetTypes) {
            expectTypeOrInterfaceNotExported(source, typeName)
        }
    })

    it("keeps Zapier API response subtypes private", () => {
        const source = readSource("lib/api/zapier.ts")
        const hookSource = readSource("lib/hooks/use-zapier.ts")
        const privateZapierTypes = [
            "ZapierSettings",
            "ZapierInboundWebhook",
            "RotateZapierSecretResponse",
            "ZapierOutboundSettingsRequest",
            "ZapierTestLeadRequest",
            "ZapierTestLeadResponse",
            "ZapierInboundWebhookCreateRequest",
            "ZapierInboundWebhookCreateResponse",
            "ZapierOutboundTestRequest",
            "ZapierOutboundTestResponse",
            "ZapierOutboundEventStatus",
            "ZapierOutboundEventsResponse",
            "ZapierOutboundEventsSummary",
            "ZapierFieldPasteRequest",
        ]

        for (const typeName of privateZapierTypes) {
            expectTypeOrInterfaceNotExported(source, typeName)
        }
        expect(source).not.toContain("export async function rotateZapierSecret")
        expect(hookSource).not.toContain("export function useRotateZapierSecret")
    })

    it("keeps MFA API response shapes private", () => {
        const source = readSource("lib/api/mfa.ts")
        const privateResponses = [
            "MFAStatus",
            "TOTPSetupResponse",
            "TOTPSetupCompleteResponse",
            "RecoveryCodesResponse",
            "MFAVerifyResponse",
            "MFACompleteResponse",
            "DuoStatus",
            "DuoInitiateResponse",
            "DuoCallbackResponse",
        ]

        for (const responseName of privateResponses) {
            expect(source).not.toContain(`export interface ${responseName}`)
        }
    })

    it("keeps unused MFA setup and health helpers out of public modules", () => {
        const apiSource = readSource("lib/api/mfa.ts")
        const hookSource = readSource("lib/hooks/use-mfa.ts")

        expect(apiSource).not.toContain("export function setupTOTP")
        expect(apiSource).not.toContain("export function verifyTOTPSetup")
        expect(apiSource).not.toContain("export function verifyMFACode")
        expect(apiSource).not.toContain("export function checkDuoHealth")
        expect(apiSource).not.toContain("interface TOTPSetupResponse")
        expect(apiSource).not.toContain("interface TOTPSetupCompleteResponse")
        expect(apiSource).not.toContain("interface MFAVerifyResponse")
        expect(hookSource).not.toContain("export function useSetupTOTP")
        expect(hookSource).not.toContain("export function useVerifyTOTPSetup")
        expect(hookSource).not.toContain("export function useVerifyMFACode")
    })

    it("keeps intended-parent subtype aliases private", () => {
        const source = readSource("lib/types/intended-parent.ts")
        const privateAliases = ["IntendedParentStatus", "EmbryoEggSource", "EmbryoSpermSource"]

        for (const aliasName of privateAliases) {
            expect(source).not.toContain(`export type ${aliasName}`)
        }
    })

    it("keeps public embed field visibility filtering single pass", () => {
        const source = readSource("app/embed/forms/[slug]/page.client.tsx")

        expect(source).toContain("const renderableFields = React.useMemo")
        expect(source).not.toContain("pages.flatMap((page) => page.fields).filter")
        expect(source).not.toMatch(/visibleFields\s*\.filter\(\(field\) => field\.type !== "file"\)\s*\.map/)
    })

    it("keeps public embed origin and session state compiler-friendly", () => {
        const source = readSource("app/embed/forms/[slug]/page.client.tsx")

        expect(source).toContain("type EmbedBootstrapState")
        expect(source).toContain("type EmbedSessionState")
        expect(source).not.toContain("setParentOrigin")
        expect(source).not.toContain("setSessionToken")
        expect(source).not.toContain("sessionTokenRef")
        expect(source).not.toContain("finally")
    })

    it("batches independent profile hidden-field saves", () => {
        const source = readSource("components/surrogates/profile/ProfileCard/context.tsx")

        expect(source).toContain("await Promise.all(")
        expect(source).not.toMatch(/for \(const fieldKey of hiddenDiff\)[\s\S]*await toggleHiddenMutation\.mutateAsync/)
    })

    it("keeps profile card provider state compiler-friendly", () => {
        const source = readSource("components/surrogates/profile/ProfileCard/context.tsx")

        expect(source).toContain("type ProfileEditableState")
        expect(source).toContain("function createProfileEditableState")
        expect(source).toContain("if (profileState.profileKey !== activeProfileKey)")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("finally")
        expect(source).not.toContain("setBaselineOverrides")
        expect(source).not.toContain("setBaselineHidden")
        expect(source).not.toContain("setSectionOpen(initialState)")
    })

    it("keeps hosted intake field visibility filtering single pass", () => {
        const source = readSource("app/intake/[slug]/page.client.tsx")

        expect(source).toContain("function getVisibleFieldGroups")
        expect(source).toContain("const standardFields: FormField[] = []")
        expect(source).toContain("const visibleReviewPages = pages.map")
        expect(source).toContain("const currentVisibleFields = currentPage")
        expect(source).not.toContain("page.fields.filter((field) => field.type !== \"file\").map")
        expect(source).not.toContain("page.fields\n                                                .filter")
        expect(source).not.toContain("currentPage.fields.filter")
        expect(source).not.toContain("currentPage.fields\n                                    .filter")
    })

    it("keeps hosted intake draft and resume state compiler-friendly", () => {
        const source = readSource("app/intake/[slug]/page.client.tsx")

        expect(source).toContain("type DraftSessionState")
        expect(source).not.toContain("setDraftSessionId")
        expect(source).not.toContain("setDraftSessionExists")
        expect(source).not.toContain('throw new Error("Invalid form payload")')
        expect(source).not.toContain("finally")
        expect(source).not.toContain("if (currentStep > steps.length)")
    })

    it("keeps dashboard URL filter sync in one reducer update", () => {
        const source = readSource("app/(app)/dashboard/context/dashboard-filters.tsx")

        expect(source).toContain("type DashboardFiltersAction")
        expect(source).toContain("function dashboardFiltersReducer")
        expect(source).toMatch(/dispatchFilters\(\{\s*type: "syncFromUrl"/)
        expect(source).not.toContain("setDateRangeState")
        expect(source).not.toContain("setCustomRangeState")
        expect(source).not.toContain("setAssigneeIdState")
    })

    it("avoids flatMap as a filter-map in form and campaign list normalization", () => {
        const formsApiSource = readSource("lib/api/forms.ts")
        const shareDialogSource = readSource("components/forms/builder/ShareApplicationDialog.tsx")
        const templateBuilderSource = readSource("lib/forms/use-template-form-builder-page.ts")
        const automationBuilderSource = readSource("lib/forms/use-automation-form-builder-page.ts")
        const campaignSource = readSource("app/(app)/automation/campaigns/page.tsx")
        const attachmentsSource = readSource("components/email/EmailAttachmentsPanel.tsx")
        const embedSource = readSource("app/embed/forms/[slug]/page.client.tsx")

        expect(formsApiSource).not.toContain("rawOptions.flatMap((raw) => {")
        expect(shareDialogSource).not.toContain(".flatMap((value) => {")
        expect(templateBuilderSource).not.toContain(".flatMap((entry) => {")
        expect(automationBuilderSource).not.toContain(".flatMap((entry) => {")
        expect(campaignSource).not.toContain("selectedStages.flatMap((stageId) => {")
        expect(campaignSource).not.toContain("selectedStates.flatMap((stateCode) => {")
        expect(attachmentsSource).not.toContain("uploadResults.flatMap(")
        expect(embedSource).not.toContain("pages.flatMap((page) => page.fields.filter")
    })

    it("uses indexed lookups for campaign selected filter labels", () => {
        const source = readSource("app/(app)/automation/campaigns/page.tsx")

        expect(source).toContain("function getStageIdsByPredicate")
        expect(source).toContain("const stageLabelById = new Map<string, string>(")
        expect(source).toContain("const stateLabelByCode = new Map<string, string>(")
        expect(source).not.toMatch(/stageOptions\s*\.filter\([\s\S]*?\)\s*\.map\(\(stage\) => stage\.id\)/)
        expect(source).not.toContain("stageOptions.find((stage) => stage.id === stageId)")
        expect(source).not.toContain("US_STATES.find((state) => state.value === stateCode)")
    })

    it("builds form builder mappings in a single pass", () => {
        const source = readSource("lib/forms/form-builder-document.ts")

        expect(source).toContain("const mappings: { field_key: string; surrogate_field: string }[] = []")
        expect(source).not.toMatch(/page\.fields\s*\.filter\(\(field\) => field\.surrogateFieldMapping\)\s*\.map/)
    })

    it("uses stable keys for report chart cells and parser warnings", () => {
        const teamChartSource = readSource("components/reports/TeamPerformanceChart.tsx")
        const metaSpendSource = readSource("components/reports/MetaSpendDashboard.tsx")
        const scheduleParserSource = readSource("components/ai/ScheduleParserDialog.tsx")

        expect(teamChartSource).toContain("userId: user.user_id")
        expect(teamChartSource).toContain("key={entry.userId}")
        expect(teamChartSource).not.toContain("key={`cell-${index}`}")
        expect(metaSpendSource).toContain("breakdownValue: item.breakdown_value")
        expect(metaSpendSource).toContain("platformKey: item.platform")
        expect(metaSpendSource).not.toContain("Cell key={index}")
        expect(scheduleParserSource).toContain("getWarningKey")
        expect(scheduleParserSource).not.toContain("key={i}")
    })

    it("keeps parser success actions and team chart legend polished", () => {
        const teamChartSource = readSource("components/reports/TeamPerformanceChart.tsx")
        const scheduleParserSource = readSource("components/ai/ScheduleParserDialog.tsx")

        expect(teamChartSource).not.toContain("bg-slate-400")
        expect(scheduleParserSource).not.toContain("py-8 space-y-4")
        expect(scheduleParserSource).not.toContain(">Done</Button>")
        expect(scheduleParserSource).toContain(">Close task creator</Button>")
    })

    it("uses stable keys for static loading and recovery-code lists", () => {
        const reportsLoadingSource = readSource("app/(app)/reports/loading.tsx")
        const automationLoadingSource = readSource("app/(app)/automation/loading.tsx")
        const securitySource = readSource("app/(app)/settings/security/page.tsx")
        const recipientPreviewSource = readSource("components/recipient-preview-card.tsx")

        expect(reportsLoadingSource).toContain("REPORTS_CHART_SKELETON_IDS")
        expect(reportsLoadingSource).toContain("REPORTS_METRIC_SKELETON_IDS")
        expect(reportsLoadingSource).not.toContain("key={i}")
        expect(reportsLoadingSource).not.toContain("space-y-0")
        expect(automationLoadingSource).toContain("AUTOMATION_LOADING_CARD_IDS")
        expect(automationLoadingSource).not.toContain("key={i}")
        expect(securitySource).toContain("key={code}")
        expect(securitySource).not.toContain("key={i}")
        expect(recipientPreviewSource).toContain("RECIPIENT_PREVIEW_SKELETON_IDS")
        expect(recipientPreviewSource).not.toContain("key={i}")
    })

    it("uses stable calendar cell keys for public booking dates", () => {
        const source = readSource("components/appointments/PublicBookingPage.tsx")

        expect(source).toContain("cellKey")
        expect(source).toContain("key={day.cellKey}")
        expect(source).not.toContain("key={i}")
    })

    it("uses functional updates for public booking form fields", () => {
        const source = readSource("components/appointments/PublicBookingPage.tsx")

        expect(source).toContain("setFormData((current) => ({ ...current, client_name: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, client_email: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, client_phone: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, client_notes: e.target.value }))")
        expect(source).not.toContain("setFormData({ ...formData")
    })

    it("uses functional updates for appointment type form fields", () => {
        const source = readSource("components/appointments/AppointmentSettings.tsx")

        expect(source).toContain("setFormData((current) => ({ ...current, name: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, description: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, duration_minutes: parseInt(v) }))")
        expect(source).toContain("setFormData((current) => ({ ...current, buffer_after_minutes: parseInt(v) }))")
        expect(source).toContain("setFormData((current) => ({ ...current, meeting_location: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, dial_in_number: e.target.value }))")
        expect(source).toContain("setFormData((current) => ({ ...current, auto_approve: checked }))")
        expect(source).not.toContain("setFormData({ ...formData")
    })

    it("keeps appointment settings availability updates batched and single-pass", () => {
        const source = readSource("components/appointments/AppointmentSettings.tsx")

        expect(source).toContain("type AvailabilityRuleDraft =")
        expect(source).toContain("type AvailabilityRulesState =")
        expect(source).toContain("const [availabilityState, setAvailabilityState] = useState<AvailabilityRulesState>")
        expect(source).toContain("const rulesByDay = new Map")
        expect(source).toContain("setAvailabilityState((current) => {")
        expect(source).toContain("const enabledRules: Array<{ day_of_week: number; start_time: string; end_time: string }> = []")
        expect(source).toContain("for (const rule of localRules)")
        expect(source).toContain("const selectedModes = new Set(formData.meeting_modes)")
        expect(source).toContain("for (const option of MEETING_MODE_OPTIONS)")
        expect(source).not.toContain("const [localRules, setLocalRules]")
        expect(source).not.toContain("const [timezone, setTimezone]")
        expect(source).not.toContain("const [hasChanges, setHasChanges]")
        expect(source).not.toMatch(/localRules\s*\.filter\(\(r\) => r\.enabled\)\s*\.map/)
        expect(source).not.toMatch(/MEETING_MODE_OPTIONS\.map\(\(option\) => option\.value\)\.filter/)
    })

    it("derives public booking confirmation state from the response", () => {
        const source = readSource("components/appointments/PublicBookingPage.tsx")

        expect(source).toContain("if (confirmation && selectedType && selectedSlot)")
        expect(source).not.toContain("const [isConfirmed")
        expect(source).not.toContain("setIsConfirmed")
    })

    it("uses gap spacing for match dialog radio rows", () => {
        const addTaskSource = readSource("components/matches/AddTaskDialog.tsx")
        const uploadFileSource = readSource("components/matches/UploadFileDialog.tsx")

        expect(addTaskSource).not.toContain("flex items-center space-x-2")
        expect(uploadFileSource).not.toContain("flex items-center space-x-2")
        expect(addTaskSource).toContain("flex items-center gap-2")
        expect(uploadFileSource).toContain("flex items-center gap-2")
    })

    it("uses reducer state for the match task form", () => {
        const source = readSource("components/matches/AddTaskDialog.tsx")

        expect(source).toContain("useReducer")
        expect(source).toContain("taskFormReducer")
        expect(source).not.toContain("useState")
    })

    it("uses gap spacing for CSV validation option rows", () => {
        const source = readSource("components/import/CSVUpload.tsx")

        expect(source).not.toContain("flex items-start space-x-3")
        expect(source).toContain("flex items-start gap-3 rounded-md border border-border p-3")
    })

    it("uses immutable sorting in the team performance table", () => {
        const source = readSource("components/reports/TeamPerformanceTable.tsx")

        expect(source).toContain("data.toSorted(")
        expect(source).not.toContain("[...data].sort(")
    })

    it("uses immutable sorting in report chart and stage modals", () => {
        const teamChartSource = readSource("components/reports/TeamPerformanceChart.tsx")
        const massEditSource = readSource("components/surrogates/MassEditStageModal.tsx")
        const bulkChangeSource = readSource("components/surrogates/BulkChangeStageModal.tsx")
        const changeStageSource = readSource("components/surrogates/ChangeStageModal.tsx")

        expect(teamChartSource).toContain(".toSorted((a, b) => b.conversion_rate - a.conversion_rate)")
        expect(massEditSource).toContain(".toSorted((a, b) => a.order - b.order)")
        expect(bulkChangeSource).toContain(".toSorted((a, b) => a.order - b.order)")
        expect(changeStageSource).toContain(".toSorted((a, b) => a.order - b.order)")
        expect(teamChartSource).not.toContain(".sort((a, b) => b.conversion_rate - a.conversion_rate)")
        expect(massEditSource).not.toContain(".sort((a, b) => a.order - b.order)")
        expect(bulkChangeSource).not.toContain(".sort((a, b) => a.order - b.order)")
        expect(changeStageSource).not.toContain(".sort((a, b) => a.order - b.order)")
    })

    it("keeps bulk stage change reset logic in event handlers", () => {
        const source = readSource("components/surrogates/BulkChangeStageModal.tsx")

        expect(source).toContain("const handleOpenChange =")
        expect(source).toContain("setTargetStageId(\"\")")
        expect(source).not.toContain("React.useEffect")
    })

    it("uses immutable sorting in unified calendar derived lists", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")

        expect(source).toContain(".toSorted((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))")
        expect(source).toContain(".toSorted((a, b) => {")
        expect(source).not.toContain(".sort((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))")
        expect(source).not.toContain(".sort((a, b) => {")
    })

    it("resets unified calendar appointment detail draft state by keying the dialog", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")

        expect(source).toContain("appointmentDetailDialogKey")
        expect(source).toContain("useState(() => appointment?.surrogate_id ?? null)")
        expect(source).toContain("useState(() => appointment?.intended_parent_id ?? null)")
        expect(source).not.toMatch(/useEffect\(\(\) => \{[\s\S]*setSelectedSurrogateId\(appointment\.surrogate_id\)[\s\S]*\}, \[appointment, open\]\)/)
        expect(source).not.toMatch(/useEffect\(\(\) => \{[\s\S]*setSelectedIpId\(appointment\.intended_parent_id\)[\s\S]*\}, \[appointment, open\]\)/)
        expect(source).not.toMatch(/useEffect\(\(\) => \{[\s\S]*setShowLinkSection\(false\)[\s\S]*\}, \[appointment, open\]\)/)
        expect(source).not.toMatch(/useEffect\(\(\) => \{[\s\S]*setLogOutcomeOpen\(false\)[\s\S]*\}, \[appointment, open\]\)/)
    })

    it("uses immutable sorting for stage and intake link ordering", () => {
        const intendedParentStageSource = readSource("lib/intended-parent-stage-utils.ts")
        const formBuilderSource = readSource("lib/forms/use-automation-form-builder-page.ts")
        const surrogateActivitySource = readSource("components/surrogates/ActivityTimeline.tsx")
        const intendedParentActivitySource = readSource("components/intended-parents/IntendedParentActivityTimeline.tsx")

        expect(intendedParentStageSource).toContain("resolved.toSorted(")
        expect(formBuilderSource).toContain("intakeLinks.toSorted(")
        expect(surrogateActivitySource).toContain("history.toSorted(")
        expect(surrogateActivitySource).toContain("stageHistory.toSorted(")
        expect(intendedParentActivitySource).toContain("history.toSorted(")
        expect(intendedParentActivitySource).toContain("stageHistory.toSorted(")
        expect(intendedParentStageSource).not.toContain("[...resolved].sort(")
        expect(formBuilderSource).not.toContain("[...intakeLinks].sort(")
        expect(surrogateActivitySource).not.toContain("[...history].sort(")
        expect(surrogateActivitySource).not.toContain("[...stageHistory].sort(")
        expect(intendedParentActivitySource).not.toContain("[...history].sort(")
        expect(intendedParentActivitySource).not.toContain("[...stageHistory].sort(")
    })

    it("uses single-pass list normalization for workflow and form option lists", () => {
        const workflowSharedSource = readSource("components/automation/workflow-editor/shared.tsx")
        const formBuilderSource = readSource("components/forms/builder/FormBuilderWorkspace.tsx")
        const automationFormBuilderSource = readSource("lib/forms/use-automation-form-builder-page.ts")

        expect(workflowSharedSource).toContain("function toTrimmedList")
        expect(workflowSharedSource).toContain("function splitCommaList")
        expect(workflowSharedSource).toContain("return values.flatMap(")
        expect(workflowSharedSource).toContain("return value.split(\",\").flatMap(")
        expect(workflowSharedSource).toContain("const selectedLabels = options.flatMap(")
        expect(formBuilderSource).toContain(".split(\",\")")
        expect(formBuilderSource).toContain(".flatMap((entry) => {")
        expect(workflowSharedSource).not.toMatch(/\.map\(\(item\) => String\(item\)\.trim\(\)\)\.filter\(Boolean\)/)
        expect(workflowSharedSource).not.toMatch(/\.map\(\(item\) => item\.trim\(\)\)\s*\.filter\(Boolean\)/)
        expect(workflowSharedSource).not.toMatch(/\.map\(\(value\) => value\.trim\(\)\)\s*\.filter\(Boolean\)/)
        expect(workflowSharedSource).not.toMatch(/\.filter\(\(option\) => selectedValues\.has\(option\.value\)\)\s*\.map/)
        expect(formBuilderSource).not.toMatch(/\.map\(\(entry\) => entry\.trim\(\)\)\s*\.filter\(Boolean\)/)
        expect(automationFormBuilderSource).not.toMatch(/\.filter\(\(option\) => option\.is_critical\)\s*\.map/)
    })

    it("keeps surrogate card, task calendar, and CSV derived lists single pass", () => {
        const medicalInsuranceSource = readSource("components/surrogates/CombinedMedicalInsuranceCard.tsx")
        const taskCalendarSource = readSource("components/surrogates/SurrogateTasksCalendar.tsx")
        const csvUploadSource = readSource("components/import/CSVUpload.tsx")
        const metaMappingSource = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")

        expect(medicalInsuranceSource).not.toContain("finally")
        expect(medicalInsuranceSource).not.toContain("useEffect")
        expect(medicalInsuranceSource).not.toContain("useMemo")
        expect(medicalInsuranceSource).not.toMatch(/SECTION_CONFIGS\.filter\([\s\S]*?\)\.map\(/)
        expect(medicalInsuranceSource).not.toMatch(/SECTION_CONFIGS\.filter\([\s\S]*?\)\s*\.filter\(/)
        expect(taskCalendarSource).toContain("const orphanedCompletedTasks = useMemo")
        expect(taskCalendarSource).not.toContain("tasks.filter(t => t.is_completed).map")
        expect(csvUploadSource).not.toMatch(/const unmatched = mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
        expect(csvUploadSource).not.toMatch(/new Set\(\s*mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
        expect(metaMappingSource).not.toMatch(/const unmatched = mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
        expect(metaMappingSource).not.toMatch(/new Set\(\s*mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
    })

    it("uses single-pass activity timeline list derivation", () => {
        const source = readSource("components/surrogates/ActivityTimeline.tsx")

        expect(source).toContain("formatContactMethods")
        expect(source).toContain("const overdueTasks: TaskListItem[] = []")
        expect(source).toContain("for (const task of tasks)")
        expect(source).not.toMatch(/\.map\(\(method\) => String\(method\)\)\s*\.map/)
        expect(source).not.toMatch(/tasks\s*\.filter\(\(task\) => !task\.is_completed && task\.due_date\)\s*\.map/)
        expect(source).not.toMatch(/overdue\.sort\(sortByDueDate\)\.map/)
        expect(source).not.toMatch(/upcoming\.sort\(sortByDueDate\)\.map/)
    })

    it("uses single-pass intended-parent clinic section derivation", () => {
        const source = readSource("components/intended-parents/IntendedParentClinicCard.tsx")

        expect(source).toContain("const sectionsWithData: MedicalSectionKey[] = []")
        expect(source).toContain("const visibleSections: SectionConfig[] = []")
        expect(source).not.toMatch(/SECTION_CONFIGS\.filter\([\s\S]*\)\.map\(\(section\) => section\.key\)/)
        expect(source).not.toMatch(/SECTION_CONFIGS\.filter\(\(section\) => visibleKeys\.has\(section\.key\)\)\.filter/)
        expect(source).not.toContain("finally")
        expect(source).not.toContain("useMemo")
    })

    it("keeps pregnancy tracker embryo-stage saves compiler-compatible", () => {
        const source = readSource("components/surrogates/PregnancyTrackerCard.tsx")

        expect(source).toContain('aria-label="Edit due date"')
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("finally")
        expect(source).not.toContain("useMemo")
    })

    it("keeps surrogate header export compiler-compatible", () => {
        const source = readSource("components/surrogates/detail/SurrogateDetailLayout/HeaderActions.tsx")

        expect(source).not.toContain("finally")
    })

    it("keeps auth provider fetch and mount flow compiler-compatible", () => {
        const source = readSource("lib/auth-context.tsx")

        expect(source).toContain("function shouldSkipAuthFetch()")
        expect(source).toContain("useState(() => !shouldSkipAuthFetch())")
        expect(source).toContain("window.setTimeout")
        expect(source).not.toContain("finally")
        expect(source).not.toContain("void fetchUser();")
    })

    it("keeps invite acceptance fetch compiler-compatible", () => {
        const source = readSource("app/invite/[id]/page.client.tsx")

        expect(source).not.toContain("finally")
    })

    it("uses single-pass filtered display lists for dashboard and campaign details", () => {
        const stageChartSource = readSource("app/(app)/dashboard/components/stage-chart.tsx")
        const campaignDetailSource = readSource("app/(app)/automation/campaigns/[id]/page.client.tsx")

        expect(stageChartSource).toContain("const stageLinkEntries = chartData.flatMap(")
        expect(stageChartSource).toContain("stageLinkEntries.map((entry) => (")
        expect(campaignDetailSource).toContain("function toSelectedStringSet")
        expect(campaignDetailSource).toContain("function getSelectedLabels")
        expect(campaignDetailSource).toContain("options.flatMap((option) => (")
        expect(stageChartSource).not.toMatch(/chartData\s*\.filter\(\(entry\) => entry\.stage_id\)\s*\.map/)
        expect(campaignDetailSource).not.toMatch(/\.filter\([^)]*rawStageFilters\.includes[\s\S]*?\.map/)
        expect(campaignDetailSource).not.toMatch(/US_STATES\.filter\([^)]*stateFilters\.includes[\s\S]*?\.map/)
    })

    it("hoists Meta spend dashboard number formatters", () => {
        const source = readSource("components/reports/MetaSpendDashboard.tsx")

        expect(source).toContain("const USD_INTEGER_FORMATTER = new Intl.NumberFormat")
        expect(source).toContain("const INTEGER_FORMATTER = new Intl.NumberFormat")
        expect(source).toContain("return USD_INTEGER_FORMATTER.format(value)")
        expect(source).toContain("return INTEGER_FORMATTER.format(value)")
        expect(source).toContain("Loading…")
        expect(source).not.toContain("return new Intl.NumberFormat")
        expect(source).not.toContain("Loading...")
    })

    it("uses gap spacing for integrations provider radio rows", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")

        expect(source).toContain("flex items-center gap-2")
        expect(source).toContain("flex flex-row items-center justify-between gap-y-0 pb-3")
        expect(source).not.toContain("flex items-center space-x-2")
        expect(source).not.toContain("flex flex-row items-center justify-between space-y-0 pb-3")
    })

    it("uses plain punctuation in integrations setup copy", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")

        expect(source).toContain("Uses Workload Identity Federation, no long-lived keys stored.")
        expect(source).toContain("New Webhook Secret (copy now, shown once):")
        expect(source).not.toContain("Uses Workload Identity Federation—no long-lived keys stored.")
        expect(source).not.toContain("New Webhook Secret (copy now — shown once):")
    })

    it("keeps Zapier integration drafts compiler-friendly", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")

        expect(source).toContain("type ZapierWebhookDraftState")
        expect(source).toContain("function createZapierWebhookDraftState")
        expect(source).toContain("type ZapierOutboundDraftState")
        expect(source).toContain("function createZapierOutboundDraftState")
        expect(source).toContain("function getErrorMessage")
        expect(source).toContain("function copyToClipboard")
        expect(source).toContain("const activeFieldPasteWebhookId =")
        expect(source).toContain("const activeTestFormId =")
        expect(source).not.toContain("setLabelDrafts(drafts)")
        expect(source).not.toContain("setWebhookSecrets((prev) => {\n            const next: Record<string, string> = {}")
        expect(source).not.toContain("setFieldPasteWebhookId('')")
        expect(source).not.toContain("setOutboundUrl(settings.outbound_webhook_url || '')")
        expect(source).not.toContain("setTestFormId(nextFormId)")
        expect(source).not.toContain('role="textbox"')
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("finally")
    })

    it("keeps AI chat message state compiler-friendly", () => {
        const source = readSource("components/ai/AIChatPanel.tsx")

        expect(source).toContain("type PanelMessageState")
        expect(source).toContain("function createConversationKey")
        expect(source).toContain("function createPanelMessageState")
        expect(source).toContain("const currentContext =")
        expect(source).not.toContain("const [messages, setMessages]")
        expect(source).not.toContain("setMessages(")
        expect(source).not.toContain("useEffect(() => {\n        if (isStreaming) return")
        expect(source).not.toContain("prevContextRef")
        expect(source).not.toContain("useEffect(() => {\n        const prev =")
        expect(source).not.toContain("finally")
    })

    it("uses gap spacing for report summary card headers", () => {
        const source = readSource("app/(app)/reports/page.tsx")

        expect(source).toContain("flex flex-row items-center justify-between gap-y-0 pb-2")
        expect(source).toContain("Loading campaigns…")
        expect(source).toContain("Exporting…")
        expect(source).not.toContain("flex flex-row items-center justify-between space-y-0 pb-2")
        expect(source).not.toContain("Loading campaigns...")
        expect(source).not.toContain("Exporting...")
    })

    it("keeps reports PDF export compiler-compatible", () => {
        const source = readSource("app/(app)/reports/page.tsx")

        expect(source).not.toContain("finally")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("const formatTokens =")
        expect(source).not.toContain("const isPerformanceMode =")
        expect(source).not.toContain("const formatShortDate =")
    })

    it("uses gap spacing for alert summary card headers", () => {
        const source = readSource("app/(app)/settings/alerts/page.tsx")

        expect(source).toContain("flex flex-row items-center justify-between gap-y-0 pb-2")
        expect(source).not.toContain("flex flex-row items-center justify-between space-y-0 pb-2")
    })

    it("uses gap spacing for ops metric card headers", () => {
        const source = readSource("app/ops/page.client.tsx")

        expect(source).toContain("flex flex-row items-center justify-between gap-y-0 pb-2")
        expect(source).not.toContain("flex flex-row items-center justify-between space-y-0 pb-2")
    })

    it("uses gap spacing for Meta connection and AI builder empty states", () => {
        const metaSource = readSource("app/(app)/settings/integrations/meta/page.client.tsx")
        const aiBuilderSource = readSource("app/(app)/automation/ai-builder/page.client.tsx")

        expect(metaSource).toContain("flex flex-row items-center justify-between gap-y-0")
        expect(metaSource).not.toContain("flex flex-row items-center justify-between space-y-0")
        expect(aiBuilderSource).toContain("flex flex-col items-center text-center gap-y-4")
        expect(aiBuilderSource).not.toContain("flex flex-col items-center text-center space-y-4")
    })

    it("uses warm neutral field-library colors instead of default slate text tokens", () => {
        const source = readSource("components/forms/builder/FieldLibrarySheet.tsx")

        expect(source).toContain("text-stone-900")
        expect(source).toContain("text-stone-950")
        expect(source).toContain("placeholder:text-stone-400")
        expect(source).toContain("const visibleSections: LibrarySection[] = []")
        expect(source).toContain("visibleSections.push")
        expect(source).toContain("searchPattern.test")
        expect(source).not.toContain("text-slate-")
        expect(source).not.toContain("placeholder:text-slate-")
        expect(source).not.toContain(".includes(normalizedSearch)")
        expect(source).not.toContain(".indexOf(normalizedSearch)")
        expect(source).not.toContain("return sourceGroups\n            .map")
    })

    it("uses project theme tokens instead of default indigo accents", () => {
        const aiBuilderSource = readSource("app/(app)/automation/ai-builder/page.client.tsx")
        const integrationsSource = readSource("app/(app)/settings/integrations/page.tsx")

        expect(aiBuilderSource).not.toContain("indigo-")
        expect(integrationsSource).not.toContain("indigo-")
    })

    it("documents the generic label accessibility lint boundary", () => {
        const source = readSource("components/ui/label.tsx")

        expect(source).toContain("return React.createElement(")
        expect(source).toContain('"label",')
        expect(source).toContain("forwards htmlFor and children from call sites")
    })

    it("keeps version history payload previews outside render", () => {
        const source = readSource("components/version-history-modal.tsx")

        expect(source).toContain("function getPayloadPreview(")
        expect(source).toContain("getPayloadPreview(entityType, v.payload)")
        expect(source).not.toContain("const renderPayloadPreview =")
    })

    it("uses functional editing rule draft updates", () => {
        const source = readSource("app/(app)/settings/intelligent-suggestions-section.tsx")

        expect(source).toContain("setEditingRuleDraft((currentDraft) =>")
        expect(source).not.toContain("setEditingRuleDraft({ ...editingRuleDraft")
    })

    it("keeps intelligent suggestion settings compiler-friendly", () => {
        const source = readSource("app/(app)/settings/intelligent-suggestions-section.tsx")

        expect(source).toContain("const normalizedNewRuleDraft =")
        expect(source).toContain("window.setTimeout(() => void loadSettings(), 0)")
        expect(source).not.toContain("finally")
        expect(source).not.toContain("useEffect(() => {\n    void loadSettings()")
        expect(source).not.toContain(
            "setNewRuleDraft((previous) => (previous ? { ...previous, stage_slug: normalizedStage } : previous))",
        )
    })

    it("keeps settings profile and organization branding state compiler-friendly", () => {
        const source = readSource("app/(app)/settings/page.tsx")

        expect(source).toContain("type ProfileDraftState")
        expect(source).toContain("type OrgBrandingDraftState")
        expect(source).toContain("function createProfileDraftState")
        expect(source).toContain("function createOrgBrandingDraftState")
        expect(source).toContain("function formatSessionDate")
        expect(source).toContain("function getSessionDeviceIcon")
        expect(source).toContain("useOrgSettings")
        expect(source).toContain('aria-label="Organization logo upload"')
        expect(source).toContain('aria-label="Primary color"')
        expect(source).toContain('aria-label="Profile photo upload"')
        expect(source).not.toContain("setProfileForm")
        expect(source).not.toContain("setOrgDefaults")
        expect(source).not.toContain("loadOrgSettings")
        expect(source).not.toContain("const formatDate =")
        expect(source).not.toContain("const getDeviceIcon =")
        expect(source).not.toContain("initialized")
        expect(source).not.toContain("finally")
        expect(source).not.toContain("useMemo")
    })

    it("resets intended-parent trust drafts from edit events, not prop-sync effects", () => {
        const source = readSource("components/intended-parents/TrustInfoCard.tsx")

        expect(source).toContain("const openAddressEditor = () => {")
        expect(source).toContain("const openNotesEditor = () => {")
        expect(source).not.toContain("React.useEffect(() => {\n        setDraft(buildAddressDraft(intendedParent))")
        expect(source).not.toContain("React.useEffect(() => {\n        setDraft(value ?? \"\")")
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("finally")
    })

    it("resets surrogate edit select state by remounting dialog content", () => {
        const source = readSource("components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx")

        expect(source).toContain("key={surrogate.id}")
        expect(source).not.toContain("React.useEffect(() => {\n        setValue(defaultValue ?? \"\")")
    })

    it("uses named task list components instead of render functions", () => {
        const source = readSource("components/tasks/TasksListView.tsx")

        expect(source).toContain("function TaskListItemRow(")
        expect(source).toContain("function TaskDueSection(")
        expect(source).not.toContain("const renderTaskItem =")
        expect(source).not.toContain("const renderSection =")
    })

    it("uses a named intake review value component instead of a render function", () => {
        const source = readSource("app/intake/[slug]/page.client.tsx")

        expect(source).toContain("function ReviewValue(")
        expect(source).not.toContain("const renderReviewValue =")
    })

    it("creates recurring tasks through the batch task mutation", () => {
        const tasksPageSource = readSource("app/(app)/tasks/page.client.tsx")
        const surrogateTasksSource = readSource("app/(app)/surrogates/[id]/tasks/page.tsx")
        const taskHookSource = readSource("lib/hooks/use-tasks.ts")

        expect(tasksPageSource).toContain("const createTaskBatch = useCreateTaskBatch()")
        expect(surrogateTasksSource).toContain("const createTaskBatchMutation = useCreateTaskBatch()")
        expect(tasksPageSource).toContain("createTaskBatch.mutateAsync(")
        expect(surrogateTasksSource).toContain("createTaskBatchMutation.mutateAsync(")
        expect(tasksPageSource).not.toContain("for (const date of dates) {\n            await createTask.mutateAsync")
        expect(surrogateTasksSource).not.toContain("for (const date of dates) {\n            await createTaskMutation.mutateAsync")
        expect(taskHookSource).not.toContain(".map((task) => task.surrogate_id)")
    })

    it("uses plain punctuation for Meta asset detail labels", () => {
        const source = readSource("app/(app)/settings/integrations/meta/page.client.tsx")

        expect(source).toContain("{` (${account.name})`}")
        expect(source).toContain("{` (${page.name})`}")
        expect(source).toContain("{`${conflict.id}: connected by ${conflict.connected_by_meta_user || \"Unknown\"}`}")
        expect(source).not.toContain("— {account.name}")
        expect(source).not.toContain("— {page.name}")
        expect(source).not.toContain("{conflict.id} — connected by")
    })

    it("uses named empty-state labels instead of dash placeholders in form tables", () => {
        const matchesSource = readSource("app/(app)/intended-parents/matches/page.client.tsx")
        const metaFormsSource = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")
        const intakeSource = readSource("app/intake/[slug]/page.client.tsx")
        const csvSource = readSource("components/import/CSVUpload.tsx")

        expect(matchesSource).toContain('<span className="text-muted-foreground">No stage</span>')
        expect(metaFormsSource).toContain('<span className="text-xs text-muted-foreground">No custom field</span>')
        expect(metaFormsSource).toContain('<span className="text-muted-foreground">Empty</span>')
        expect(intakeSource).toContain('<span className="text-stone-400">No answer</span>')
        expect(csvSource).toContain('<span className="text-xs text-muted-foreground">No custom field</span>')
        expect(csvSource).toContain('<span className="text-muted-foreground">Empty</span>')
        expect(matchesSource).not.toContain('<span className="text-muted-foreground">—</span>')
        expect(metaFormsSource).not.toContain('<span className="text-xs text-muted-foreground">—</span>')
        expect(metaFormsSource).not.toContain('<span className="text-muted-foreground">—</span>')
        expect(intakeSource).not.toContain('<span className="text-stone-400">—</span>')
        expect(csvSource).not.toContain('<span className="text-xs text-muted-foreground">—</span>')
        expect(csvSource).not.toContain('<span className="text-muted-foreground">—</span>')
    })

    it("uses typographic ellipses in the AI builder", () => {
        const source = readSource("app/(app)/automation/ai-builder/page.client.tsx")

        expect(source).toContain("Generating…")
        expect(source).toContain("Saving…")
        expect(source).toContain("Loading variables…")
        expect(source).toContain("follow-up task for next week…")
        expect(source).toContain("just submitted their form…")
        expect(source).toContain('suggestion.slice(0, 50) + "…"')
        expect(source).not.toContain("Generating...")
        expect(source).not.toContain("Saving...")
        expect(source).not.toContain("Loading variables...")
        expect(source).not.toContain("follow-up task for next week...")
        expect(source).not.toContain("just submitted their form...")
        expect(source).not.toContain('suggestion.slice(0, 50) + "..."')
    })

    it("uses typographic ellipses for operational loading labels", () => {
        const welcomeSource = readSource("app/(app)/welcome/page.tsx")
        const ticketDetailSource = readSource("app/(app)/tickets/[ticketId]/page.tsx")
        const tasksListSource = readSource("components/tasks/TasksListView.tsx")
        const publishDialogSource = readSource("components/ops/templates/PublishDialog.tsx")

        expect(welcomeSource).toContain("Saving…")
        expect(ticketDetailSource).toContain("Loading ticket…")
        expect(ticketDetailSource).toContain("'Saving…'")
        expect(ticketDetailSource).toContain("'Updating link…'")
        expect(ticketDetailSource).toContain("'Sending…'")
        expect(tasksListSource).toContain("Completing…")
        expect(publishDialogSource).toContain("Loading organizations…")
        expect(welcomeSource).not.toContain("finally")
        expect(welcomeSource).not.toContain("Saving...")
        expect(ticketDetailSource).not.toContain("Loading ticket...")
        expect(ticketDetailSource).not.toContain("'Saving...'")
        expect(ticketDetailSource).not.toContain("'Updating link...'")
        expect(ticketDetailSource).not.toContain("'Sending...'")
        expect(tasksListSource).not.toContain("Completing...")
        expect(publishDialogSource).not.toContain("Loading organizations...")
    })

    it("keeps ops alert actions compiler-compatible", () => {
        const source = readSource("app/ops/alerts/page.client.tsx")

        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("finally")
    })

    it("keeps smaller ops pages compiler-compatible", () => {
        const opsDashboardSource = readSource("app/ops/page.client.tsx")
        const newAgencySource = readSource("app/ops/agencies/new/page.client.tsx")

        expect(opsDashboardSource).not.toContain("finally")
        expect(newAgencySource).toContain("function generateSlug(name: string)")
        expect(newAgencySource).not.toContain("const generateSlug =")
        expect(newAgencySource).not.toContain("finally")
    })

    it("destructures navigation methods in smaller operational pages", () => {
        const appLinkSource = readSource("components/app-link.tsx")
        const opsLayoutSource = readSource("app/ops/layout.tsx")
        const newAgencySource = readSource("app/ops/agencies/new/page.client.tsx")
        const welcomeSource = readSource("app/(app)/welcome/page.tsx")
        const ticketsSource = readSource("app/(app)/tickets/page.tsx")
        const unassignedPageSource = readSource("app/(app)/surrogates/unassigned/page.tsx")
        const unassignedSource = readSource("app/(app)/surrogates/unassigned/page.client.tsx")

        expect(appLinkSource).toContain("const { push, replace: replaceRoute } = useRouter()")
        expect(appLinkSource).toContain("replaceRoute(targetHref")
        expect(appLinkSource).toContain("push(targetHref")
        expect(opsLayoutSource).toContain("const { replace } = useRouter()")
        expect(opsLayoutSource).toContain("replace('/mfa')")
        expect(opsLayoutSource).toContain("replace('/ops/login')")
        expect(opsLayoutSource).toContain("[replace, isLoginPage]")
        expect(opsLayoutSource).toContain("const [opsLayoutState, dispatchOpsLayout] = useReducer(opsLayoutReducer")
        expect(opsLayoutSource).toContain("type: 'loaded'")
        expect(opsLayoutSource).toContain("dispatchOpsLayout({ type: 'redirecting' })")
        expect(opsLayoutSource).not.toContain("setOpsLayoutState")
        expect(opsLayoutSource).not.toContain("const [user, setUser] = useState")
        expect(opsLayoutSource).not.toContain("const [isLoading, setIsLoading] = useState")
        expect(opsLayoutSource).not.toContain("const [openAlertCount, setOpenAlertCount] = useState")
        expect(newAgencySource).toContain("const { push } = useRouter()")
        expect(newAgencySource).toContain("push(`/ops/agencies/${result.org.id}`)")
        expect(newAgencySource).toContain("push('/ops/agencies')")
        expect(welcomeSource).toContain("const { push, replace } = useRouter()")
        expect(welcomeSource).toContain('push("/dashboard")')
        expect(welcomeSource).toContain('replace("/dashboard")')
        expect(welcomeSource).toContain("[user, replace]")
        expect(ticketsSource).toContain("const { push } = useRouter()")
        expect(ticketsSource).toContain("push(`/tickets/${result.ticket_id}`)")
        expect(unassignedSource).toContain("const { push, replace } = useRouter()")
        expect(unassignedPageSource).toContain("searchParams: Promise<Record<string, SearchParamValue>>")
        expect(unassignedSource).toContain("initialSearchParams")
        expect(unassignedSource).toContain('replace("/surrogates")')
        expect(unassignedSource).toContain("push(`/surrogates/${surrogateId}`)")
        expect(unassignedSource).not.toContain("finally")
        expect(unassignedSource).not.toContain("useCallback")
        expect(welcomeSource).not.toContain("const router = useRouter()")
        expect(welcomeSource).not.toContain("router.push(")
        expect(welcomeSource).not.toContain("router.replace(")
        expect(ticketsSource).not.toContain("const router = useRouter()")
        expect(ticketsSource).not.toContain("router.push(")
        expect(unassignedSource).not.toContain("const router = useRouter()")
        expect(unassignedSource).not.toContain("useSearchParams")
        expect(unassignedSource).not.toContain("router.push(")
        expect(unassignedSource).not.toContain("router.replace(")
        expect(appLinkSource).not.toContain("const router = useRouter()")
        expect(appLinkSource).not.toContain("router.push(")
        expect(appLinkSource).not.toContain("router.replace(")
        expect(opsLayoutSource).not.toContain("const router = useRouter()")
        expect(opsLayoutSource).not.toContain("router.replace(")
        expect(newAgencySource).not.toContain("const router = useRouter()")
        expect(newAgencySource).not.toContain("router.push(")
    })

    it("destructures router navigation methods in routed filter pages", () => {
        const tasksSource = readSource("app/(app)/tasks/page.client.tsx")
        const intendedParentsSource = readSource("app/(app)/intended-parents/page.client.tsx")
        const matchesSource = readSource("app/(app)/intended-parents/matches/page.client.tsx")
        const dashboardFiltersSource = readSource("app/(app)/dashboard/context/dashboard-filters.tsx")
        const metaSource = readSource("app/(app)/settings/integrations/meta/page.client.tsx")
        const metaMappingSource = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")

        expect(tasksSource).toContain("const { replace } = useRouter()")
        expect(intendedParentsSource).toContain("const { replace } = useRouter()")
        expect(matchesSource).toContain("const { replace } = useRouter()")
        expect(dashboardFiltersSource).toContain("const { push, replace } = useRouter()")
        expect(metaSource).toContain("const { push } = useRouter()")
        expect(metaMappingSource).toContain("const { push } = useRouter()")

        for (const source of [
            tasksSource,
            intendedParentsSource,
            matchesSource,
            dashboardFiltersSource,
            metaSource,
            metaMappingSource,
        ]) {
            expect(source).not.toContain("const router = useRouter()")
            expect(source).not.toContain("router.push(")
            expect(source).not.toContain("router.replace(")
        }
    })

    it("destructures remaining router navigation methods", () => {
        const opsAgencySource = readSource("app/ops/agencies/[orgId]/page.client.tsx")
        const opsWorkflowSource = readSource("app/ops/templates/workflows/[id]/page.client.tsx")
        const aiBuilderSource = readSource("app/(app)/automation/ai-builder/page.client.tsx")
        const teamMemberSource = readSource("app/(app)/settings/team/members/[id]/page.client.tsx")
        const matchTabSource = readSource("app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabState.ts")

        expect(opsAgencySource).toContain("const { push } = useRouter()")
        expect(opsWorkflowSource).toContain("const { push, replace } = useRouter()")
        expect(aiBuilderSource).toContain("const { push } = useRouter()")
        expect(teamMemberSource).toContain("const { push } = useRouter()")
        expect(matchTabSource).toContain("const { replace } = useRouter()")

        for (const source of [
            opsAgencySource,
            opsWorkflowSource,
            aiBuilderSource,
            teamMemberSource,
            matchTabSource,
        ]) {
            expect(source).not.toContain("const router = useRouter()")
            expect(source).not.toContain("router.push(")
            expect(source).not.toContain("router.replace(")
        }
    })

    it("keeps Tasks page focus coordination out of render state", () => {
        const source = readSource("app/(app)/tasks/page.client.tsx")

        expect(source).toContain("const handledFocusRef = useRef<FocusTarget | null>(null)")
        expect(source).toContain("handledFocusRef.current === focusTarget")
        expect(source).toContain("handledFocusRef.current = focusTarget")
        expect(source).not.toContain("const [pendingFocus, setPendingFocus]")
        expect(source).not.toContain("const pendingFocus =")
        expect(source).not.toContain("setPendingFocus(")
    })

    it("keeps task edit modal draft state compiler-friendly", () => {
        const source = readSource("components/tasks/TaskEditModal.tsx")

        expect(source).toContain("type TaskEditDraft")
        expect(source).toContain("function createTaskEditDraft")
        expect(source).toContain("if (draft.taskId !== activeTaskId)")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("finally")
        expect(source).not.toContain("setTitle")
        expect(source).not.toContain("setDescription")
        expect(source).not.toContain("setTaskType")
        expect(source).not.toContain("setDueDate")
        expect(source).not.toContain("setDueTime")
    })

    it("keeps automation and AI derived lists single pass", () => {
        const emailTemplatesSource = readSource("app/(app)/automation/email-templates/page.tsx")
        const aiBuilderSource = readSource("app/(app)/automation/ai-builder/page.client.tsx")
        const aiAssistantSource = readSource("app/(app)/ai-assistant/page.tsx")

        expect(emailTemplatesSource).toContain("const requiredVariableNames = React.useMemo(() => {")
        expect(emailTemplatesSource).toContain("for (const variable of templateVariables) {")
        expect(emailTemplatesSource).not.toContain("templateVariables.filter((variable) => variable.required).map")

        expect(aiBuilderSource).toContain("const requiredTemplateVariableNames = useMemo(() => {")
        expect(aiBuilderSource).toContain("for (const variable of templateVariableCatalog) {")
        expect(aiBuilderSource).toContain("const workflowActionDetails = Object.entries(action).flatMap")
        expect(aiBuilderSource).not.toContain("templateVariableCatalog.filter((variable) => variable.required).map")
        expect(aiBuilderSource).not.toContain(".filter(([k]) => k !== \"action_type\")")

        expect(aiAssistantSource).toContain("for (const entry of parsed) {")
        expect(aiAssistantSource).toContain("for (const msg of rawMessages) {")
        expect(aiAssistantSource).not.toContain("return parsed\n            .filter")
        expect(aiAssistantSource).not.toContain("const messages: Message[] = rawMessages\n                    .filter")
    })

    it("keeps pipeline, surrogate, and intended-parent derived lists single pass", () => {
        const pipelinesSource = readSource("app/(app)/settings/pipelines/page.tsx")
        const surrogatesSource = readSource("app/(app)/surrogates/page.client.tsx")
        const intendedParentTimelineSource = readSource("components/intended-parents/IntendedParentActivityTimeline.tsx")

        expect(pipelinesSource).toContain("const remapped: string[] = []")
        expect(pipelinesSource).toContain("const neighborColors = new Set<string>()")
        expect(pipelinesSource).toContain("const mappedLabels: string[] = []")
        expect(pipelinesSource).toContain("const selectedLabels: string[] = []")
        expect(pipelinesSource).toContain("const nextStages: EditableStage[] = []")
        expect(pipelinesSource).not.toContain(".map((value) => (value === removedStageKey ? targetStageKey ?? null : value))")
        expect(pipelinesSource).not.toContain(".filter((stage) => milestone.mapped_stage_keys.includes(stage.stageKey))")
        expect(pipelinesSource).not.toContain(".map((activeStage) => activeStage.stage_key)\n                                        .filter")
        expect(pipelinesSource).not.toContain("current.stages\n                .filter")

        expect(surrogatesSource).toContain("key !== \"intelligent_any\" &&")
        expect(surrogatesSource).not.toContain(".filter(([key]) => key !== \"intelligent_any\")\n        .filter")

        expect(intendedParentTimelineSource).toContain("const overdue: PendingTaskEntry[] = []")
        expect(intendedParentTimelineSource).toContain("const upcoming: PendingTaskEntry[] = []")
        expect(intendedParentTimelineSource).not.toContain("const pending = tasks\n            .filter")
        expect(intendedParentTimelineSource).not.toContain("const overdue = pending.filter")
        expect(intendedParentTimelineSource).not.toContain("const upcoming = pending.filter")
    })

    it("uses functional trigger-config updates in workflow template editing", () => {
        const source = readSource("app/ops/templates/workflows/[id]/page.client.tsx")

        expect(source).toContain("type TriggerConfigSetter = Dispatch<SetStateAction<JsonObject>>")
        expect(source).toContain("setTriggerConfig((current) => ({")
        expect(source).toContain("const currentFields = Array.isArray(current.fields)")
        expect(source).not.toContain("setTriggerConfig({ ...triggerConfig")
    })

    it("uses stable content-derived keys in the AI builder", () => {
        const source = readSource("app/(app)/automation/ai-builder/page.client.tsx")

        expect(source).toContain("function getStableKeyedItems")
        expect(source).toContain("function getWorkflowMessageKey")
        expect(source).toContain("function getWorkflowConditionKey")
        expect(source).toContain("function getWorkflowActionKey")
        expect(source).toContain("key={suggestion}")
        expect(source).toContain("key={key}")
        expect(source).toContain("position + 1")
        expect(source).toContain("getStableKeyedItems(workflowErrors, getWorkflowMessageKey)")
        expect(source).toContain("getStableKeyedItems(workflowWarnings, getWorkflowMessageKey)")
        expect(source).toContain("getStableKeyedItems(generatedWorkflow.conditions, getWorkflowConditionKey)")
        expect(source).toContain("getStableKeyedItems(generatedWorkflow.actions, getWorkflowActionKey)")
        expect(source).not.toContain("key={getWorkflowMessageKey(error)}")
        expect(source).not.toContain("key={getWorkflowMessageKey(warning)}")
        expect(source).not.toContain("key={getWorkflowConditionKey(cond)}")
        expect(source).not.toContain("key={getWorkflowActionKey(action)}")
        expect(source).not.toContain("key={i}")
        expect(source).not.toContain("key={index}")
    })

    it("uses stable keys in the dashboard stage chart", () => {
        const source = readSource("app/(app)/dashboard/components/stage-chart.tsx")

        expect(source).toContain("const STAGE_CHART_SKELETON_KEYS")
        expect(source).toContain("const { push } = useRouter()")
        expect(source).toContain("key={rowKey}")
        expect(source).toContain("key={line}")
        expect(source).toContain('key={`${entry.stage_id ?? "grouped"}:${entry.status}`}')
        expect(source).not.toContain("const router = useRouter()")
        expect(source).not.toContain("router.push(")
        expect(source).not.toContain("key={i}")
        expect(source).not.toContain("key={index}")
        expect(source).not.toContain("key={`${line}-${index}`}")
        expect(source).not.toContain("key={`cell-${index}`}")
    })

    it("builds dashboard and campaign display lists in a single pass", () => {
        const stageChartSource = readSource("app/(app)/dashboard/components/stage-chart.tsx")
        const campaignDetailSource = readSource("app/(app)/automation/campaigns/[id]/page.client.tsx")

        expect(stageChartSource).toContain("const stageLinkEntries = chartData.flatMap(")
        expect(campaignDetailSource).toContain("function toSelectedStringSet")
        expect(campaignDetailSource).toContain("function getSelectedLabels")
        expect(campaignDetailSource).toContain("return options.flatMap(")
        expect(stageChartSource).not.toMatch(/chartData\s*\.filter\(\(entry\) => entry\.stage_id\)\s*\.map/)
        expect(campaignDetailSource).not.toMatch(/\.filter\(\(stage\) => rawStageFilters\.includes\(stage\.id\)\)\s*\.map/)
        expect(campaignDetailSource).not.toMatch(/US_STATES\.filter\(\(state\) => stateFilters\.includes\(state\.value\)\)\s*\.map/)
    })

    it("uses subtle calendar accents and descriptive event handlers", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")

        expect(source).toContain("shadow-[inset_3px_0_0_rgb(168_85_247)]")
        expect(source).toContain("const openGoogleCalendarEvent = () =>")
        expect(source).toContain("onClick={openGoogleCalendarEvent}")
        expect(source).toContain("Saving…")
        expect(source).not.toContain("border-l-4 border-purple-500")
        expect(source).not.toContain("border-l-4 border-slate-400")
        expect(source).not.toContain("const handleClick = () =>")
        expect(source).not.toContain("onClick={handleClick}")
        expect(source).not.toContain("Saving...")
    })

    it("keeps AppSidebar state and nav rendering compiler-friendly", () => {
        const source = readSource("components/app-sidebar.tsx")

        expect(source).toContain("appSidebarReducer")
        expect(source).toContain("SidebarNavLink")
        expect(source).toContain("activeTab: null")
        expect(source).toContain('{ type: "setActiveTab"')
        expect(source).not.toContain("useSearchParams")
        expect(source).not.toContain("const activeTab = readCurrentTabParam()")
        expect(source).not.toContain("renderNavLink")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("setAutomationOpen(true)")
        expect(source).not.toContain("setSettingsOpen(true)")
        expect(source).not.toContain("setTasksOpen(true)")
    })

    it("keeps pending interview comment quote styling subtle", () => {
        const source = readSource("components/surrogates/interviews/InterviewComments/PendingCommentInput.tsx")

        expect(source).not.toContain("border-l-")
        expect(source).not.toContain("Add your comment...")
    })

    it("uses typographic ellipses in user-facing loading and placeholder copy", () => {
        const sources = [
            "components/appointments/AppointmentsList.tsx",
            "components/tasks/TasksListView.tsx",
            "app/(app)/welcome/page.tsx",
            "app/(app)/tasks/page.client.tsx",
            "app/(app)/automation/email-templates/page.tsx",
            "app/(app)/tickets/page.tsx",
            "components/import/CSVUpload.tsx",
            "app/(app)/tickets/[ticketId]/page.tsx",
            "components/forms/builder/AutomationFormSettingsPanel.tsx",
            "components/forms/builder/AutomationFormSubmissionsPanel.tsx",
            "tests/integration/permissions.integration.test.tsx",
            "app/(app)/surrogates/[id]/emails/page.tsx",
            "components/surrogates/journey/MilestoneImageSelector.tsx",
            "components/ops/templates/PublishDialog.tsx",
            "app/intake/[slug]/page.client.tsx",
            "app/(app)/surrogates/unassigned/page.client.tsx",
            "app/(app)/intended-parents/matches/page.client.tsx",
            "app/ops/templates/workflows/[id]/page.client.tsx",
            "app/(app)/intended-parents/page.client.tsx",
        ].map(readSource)

        const userFacingThreeDotCopy = [
            "Adding...",
            "Approving...",
            "Claiming...",
            "Completing...",
            "Loading...",
            "Loading application form...",
            "Loading available slots...",
            "Loading candidates...",
            "Loading contacts...",
            "Loading emails...",
            "Loading organizations...",
            "Loading submission history...",
            "Loading tasks...",
            "Loading template...",
            "Loading ticket...",
            "Loading tickets...",
            "Loading unassigned cases...",
            "Loading variables...",
            "Preparing shared link...",
            "Processing CSV...",
            "Restoring...",
            "Saving...",
            "Select...",
            "Sending...",
            "Submitting...",
            "Updating link...",
            "[Your email content here...",
            "Search case or IP name...",
            "Search name, number, email, phone...",
            "Search organizations...",
            "Workflow template name...",
            "Write your email content here...",
            "Paste or edit the HTML for this template...",
            "Why this match was resolved...",
            "Enter reason for cancellation...",
        ]

        for (const source of sources) {
            for (const copy of userFacingThreeDotCopy) {
                expect(source).not.toContain(copy)
            }
        }
    })

    it("memoizes production date-time formatters instead of rebuilding them per call", () => {
        const unifiedCalendarSource = readSource("components/appointments/UnifiedCalendar.tsx")
        const publicBookingSource = readSource("components/appointments/PublicBookingPage.tsx")
        const activityTimelineSource = readSource("components/surrogates/ActivityTimeline.tsx")
        const aiStudioSource = readSource("app/(app)/ai-studio/page.tsx")
        const unassignedSource = readSource("app/(app)/surrogates/unassigned/page.client.tsx")
        const activityTimelineTestSource = readSource("tests/activity-timeline.test.tsx")
        const dateRangePickerTestSource = readSource("tests/date-range-picker.test.tsx")
        const dateKeysSource = readSource("lib/utils/date-keys.ts")
        const formattersSource = readSource("lib/formatters.ts")

        expect(unifiedCalendarSource).toContain("clientDateFormatter = useMemo(")
        expect(unifiedCalendarSource).toContain("clientTimeFormatter = useMemo(")
        expect(unifiedCalendarSource).not.toMatch(/new Intl\.DateTimeFormat/)
        expect(publicBookingSource).toContain("function useBookingDateTimeFormatters")
        expect(publicBookingSource).toContain("timeFormatter = useMemo(")
        expect(publicBookingSource).toContain("dateFormatter = useMemo(")
        expect(publicBookingSource).not.toMatch(/new Intl\.DateTimeFormat/)
        expect(activityTimelineSource).toContain("const activityTimestampFormatter = new Intl.DateTimeFormat")
        expect(aiStudioSource).toContain("const draftDateFormatter = new Intl.DateTimeFormat")
        expect(unassignedSource).toContain("const unassignedDateFormatter = new Intl.DateTimeFormat")
        expect(activityTimelineTestSource).toContain("const activityTimestampFormatterForTest = new Intl.DateTimeFormat")
        expect(dateRangePickerTestSource).toContain("const shortDateFormatter = new Intl.DateTimeFormat")
        expect(dateKeysSource).toContain('const formatter = Intl.DateTimeFormat("en-CA", {')
        expect(formattersSource).toContain("const formatter = Intl.DateTimeFormat(undefined, options)")
        expect(activityTimelineSource).not.toMatch(/function formatActivityTimestamp[\s\S]*new Intl\.DateTimeFormat/)
        expect(aiStudioSource).not.toMatch(/function formatDraftDate[\s\S]*new Intl\.DateTimeFormat/)
        expect(unassignedSource).not.toMatch(/function formatDate[\s\S]*new Intl\.DateTimeFormat/)
        expect(activityTimelineTestSource).not.toMatch(/function formatActivityTimestampForTest[\s\S]*new Intl\.DateTimeFormat/)
        expect(dateRangePickerTestSource).not.toMatch(/const shortDateLabel = \(date: Date\) =>\s*new Intl\.DateTimeFormat/)
    })

    it("keeps production timestamp rendering out of JSX-time Date construction", () => {
        const teamPerformanceSource = readSource("components/reports/TeamPerformanceTable.tsx")
        const emailTemplatesSource = readSource("app/(app)/automation/email-templates/page.tsx")
        const ticketDetailSource = readSource("app/(app)/tickets/[ticketId]/page.tsx")
        const dateRangePickerSource = readSource("components/ui/date-range-picker.tsx")
        const integrationsSource = readSource("app/(app)/settings/integrations/page.tsx")
        const commentCardSource = readSource("components/surrogates/interviews/CommentCard.tsx")
        const unifiedCalendarSource = readSource("components/appointments/UnifiedCalendar.tsx")
        const changeStageSource = readSource("components/surrogates/ChangeStageModal.tsx")

        expect(teamPerformanceSource).not.toContain("new Date(asOf).toLocaleString()")
        expect(emailTemplatesSource).not.toContain("new Date(template.updated_at).toLocaleDateString()")
        expect(ticketDetailSource).not.toContain("new Date(note.created_at).toLocaleString()")
        expect(ticketDetailSource).not.toContain("new Date(message.date_header).toLocaleString()")
        expect(dateRangePickerSource).not.toContain("defaultMonth={localRange.from || new Date()}")
        expect(dateRangePickerSource).not.toContain("setCalendarDefaultMonth")
        expect(dateRangePickerSource).not.toContain("React.useMemo(")
        expect(integrationsSource).not.toContain("new Date(googleLastSyncAt).toLocaleString()")
        expect(commentCardSource).not.toContain("formatDistanceToNow(new Date(")
        expect(unifiedCalendarSource).not.toContain("format(new Date(2000, 0, 1, hour),")
        expect(unifiedCalendarSource).not.toContain("onClick={() => setCurrentDate(new Date())}")
        expect(changeStageSource).not.toContain("date > new Date()")
        expect(changeStageSource).not.toContain("startOfDay(new Date())")
        expect(changeStageSource).not.toContain("defaultMonth={selectedDate || new Date()}")
        expect(changeStageSource).not.toContain("defaultMonth={interviewDate || new Date()}")
    })

    it("keeps the date-range picker URL harness selection in one state update", () => {
        const source = readSource("tests/date-range-picker.test.tsx")

        expect(source).toContain("const [selection, setSelection] = useState")
        expect(source).not.toContain("const [dateRange, setDateRange] = useState")
        expect(source).not.toContain("const [customRange, setCustomRange] = useState<CustomRange>(initialCustomRange)")
    })

    it("keeps InlineDateField draft state tied to edit lifecycle", () => {
        const source = readSource("components/inline-date-field.tsx")

        expect(source).toContain("inlineDateFieldReducer")
        expect(source).toContain('type: "startEdit"')
        expect(source).not.toMatch(/useEffect\(\(\) => \{\s*setEditValue\(value \|\| ""\)/)
    })

    it("keeps InlineEditField draft state tied to edit lifecycle", () => {
        const source = readSource("components/inline-edit-field.tsx")

        expect(source).toContain("inlineEditFieldReducer")
        expect(source).toContain('type: "startEdit"')
        expect(source).not.toMatch(/useEffect\(\(\) => \{\s*setEditValue\(value \|\| ""\)/)
    })

    it("delegates match detail tab rendering to a dedicated component", () => {
        const source = readSource("app/(app)/intended-parents/matches/[id]/page.client.tsx")

        expect(source).toContain('import { MatchDetailOverviewTabs } from "./components/MatchDetailOverviewTabs"')
        expect(source).toContain("<MatchDetailOverviewTabs")
        expect(source).not.toContain('variant={activeTab === "notes" ? "secondary" : "ghost"}')
    })
})
