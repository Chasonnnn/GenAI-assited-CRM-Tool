import { describe, it, expect } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

function readSource(pathFromWebRoot: string): string {
    return readFileSync(join(process.cwd(), pathFromWebRoot), "utf8")
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

    it("does not suppress exhaustive deps in MassEditStageModal and handles late stage load", () => {
        const source = readSource("components/surrogates/MassEditStageModal.tsx")

        expect(source).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(source).toContain("const defaultTargetStageId = React.useMemo")
        expect(source).toContain("if (!open || targetStageId || !defaultTargetStageId) return")
    })

    it("derives open alert count instead of storing duplicate state", () => {
        const source = readSource("app/ops/agencies/[orgId]/page.client.tsx")

        expect(source).toContain("const openAlertCount = useMemo(")
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
        expect(source).not.toContain("React.useState<Date | undefined>(value)")
        expect(source).not.toContain("defaultMonth={draftDate || new Date()}")
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
        expect(source).not.toContain(".style.fontSize")
        expect(source).not.toContain(".style.opacity")
        expect(source).not.toContain(".style.padding")
        expect(source).not.toContain(".style.margin")
    })

    it("uses stable slider thumb keys", () => {
        const source = readSource("components/ui/slider.tsx")

        expect(source).toContain("thumbKeys")
        expect(source).not.toContain("key={index}")
    })

    it("keeps dashboard KPI chart code split and private", () => {
        const source = readSource("app/(app)/dashboard/components/kpi-card.tsx")

        expect(source).toContain('import dynamic from "next/dynamic"')
        expect(source).not.toContain('from "recharts"')
        expect(source).not.toContain("KPICardSkeleton")
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

    it("uses gap spacing for report summary card headers", () => {
        const source = readSource("app/(app)/reports/page.tsx")

        expect(source).toContain("flex flex-row items-center justify-between gap-y-0 pb-2")
        expect(source).toContain("Loading campaigns…")
        expect(source).toContain("Exporting…")
        expect(source).not.toContain("flex flex-row items-center justify-between space-y-0 pb-2")
        expect(source).not.toContain("Loading campaigns...")
        expect(source).not.toContain("Exporting...")
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
        expect(source).toContain("key={rowKey}")
        expect(source).toContain("key={line}")
        expect(source).toContain('key={`${entry.stage_id ?? "grouped"}:${entry.status}`}')
        expect(source).not.toContain("key={i}")
        expect(source).not.toContain("key={index}")
        expect(source).not.toContain("key={`${line}-${index}`}")
        expect(source).not.toContain("key={`cell-${index}`}")
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
