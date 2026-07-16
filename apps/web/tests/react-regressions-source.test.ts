import { describe, it, expect } from "vitest"
import { existsSync, readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"

function readSource(pathFromWebRoot: string): string {
    return readFileSync(join(process.cwd(), pathFromWebRoot), "utf8")
}

function readExportedFunctionSource(source: string, functionName: string): string {
    const start = source.indexOf(`export function ${functionName}`)
    expect(start, functionName).toBeGreaterThanOrEqual(0)

    const nextExport = source.indexOf("\nexport function ", start + 1)
    return nextExport === -1 ? source.slice(start) : source.slice(start, nextExport)
}

function readFunctionSource(source: string, functionName: string): string {
    const start = source.indexOf(`function ${functionName}`)
    expect(start, functionName).toBeGreaterThanOrEqual(0)

    const nextFunction = source.indexOf("\nfunction ", start + 1)
    const nextExport = source.indexOf("\nexport function ", start + 1)
    const nextDefaultExport = source.indexOf("\nexport default function ", start + 1)
    const nextMarkers = [nextFunction, nextExport, nextDefaultExport].filter((index) => index > start)
    const end = nextMarkers.length ? Math.min(...nextMarkers) : source.length
    return source.slice(start, end)
}

function findOpeningTags(source: string, tagName: string): string[] {
    return Array.from(source.matchAll(new RegExp(`<${tagName}\\b[\\s\\S]*?/>`, "g"))).map(
        (match) => match[0]
    )
}

function expectKeyAfterLastSpread(source: string, tagName: string, keyAttribute: string): void {
    const matchingTags = findOpeningTags(source, tagName).filter(
        (tag) => tag.includes(keyAttribute) && tag.includes("{...")
    )
    expect(matchingTags.length, `${tagName} ${keyAttribute}`).toBeGreaterThan(0)

    for (const tag of matchingTags) {
        expect(tag.lastIndexOf(keyAttribute), tag).toBeGreaterThan(tag.lastIndexOf("{..."))
    }
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

    it("keeps automation page option derivations compiler-friendly", () => {
        const source = readSource("app/(app)/automation/page.client.tsx")

        expect(source).not.toContain("useMemo")
        expect(source).toContain("function parseServerErrors")
        expect(source).toContain("function getActionValidationError")
        expect(source).toContain(
            "return { ...state, conditionLogic: action.value, serverErrors: [] }"
        )
        expect(source).toContain("workflowName: action.value, serverErrors: []")
        expect(source).not.toContain('type: "clearServerErrors"')
        expect(source).toContain(
            'dispatchWorkflowBuilder({ type: "normalizeTriggerConfig", value: normalized })'
        )
        expect(source).not.toContain(
            "useEffect(() => {\n        if (triggerType !== \"status_changed\""
        )
        expect(source).toContain("editingWorkflow.id === editingWorkflowId")
        expect(source).not.toMatch(/\buseEffect\b/)
        expect(source).not.toContain("const parseServerErrors =")
        expect(source).not.toContain("const getActionValidationError =")
    })

    it("keeps AI builder template derivations compiler-friendly", () => {
        const source = readSource("app/(app)/automation/ai-builder/page.client.tsx")

        expect(source).not.toContain("useMemo")
        expect(source).toContain("function workflowGenerationReducer")
        expect(source).toContain("function templateGenerationReducer")
        expect(source).toContain("const [workflowState, dispatchWorkflow] = useReducer")
        expect(source).toContain("const [templateState, dispatchTemplate] = useReducer")
        expect(source).toContain("const sanitizedTemplateBody = DOMPurify.sanitize(templateBody)")
        expect(source).toContain("const templateVariableNameSet = new Set(templateVariables)")
        expect(source).toContain("const requiredTemplateVariableNames: string[] = []")
        expect(source).toContain("for (const variable of templateVariableCatalog) {")
        expect(source).not.toContain("templateVariables.includes(")
        expect(source).not.toContain("const allowedTemplateVariableNames = useMemo")
        expect(source).not.toContain("const missingRequiredVariables = useMemo")
        expect(source).not.toContain("const unknownTemplateVariables = useMemo")
    })

    it("keeps AI builder rendering split into focused sections", () => {
        const source = readSource("app/(app)/automation/ai-builder/page.client.tsx")
        const pageIndex = source.indexOf("export default function AIWorkflowBuilderPage()")
        const firstHelperIndex = source.indexOf("function AIBuilderHeader")
        const pageSource = source.slice(
            pageIndex,
            firstHelperIndex > pageIndex ? firstHelperIndex : undefined
        )

        expect(pageIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function AIBuilderHeader")
        expect(source).toContain("function PromptComposerCard")
        expect(source).toContain("function WorkflowPreviewCard")
        expect(source).toContain("function EmailTemplatePreviewCard")
        expect(source).toContain("function AIBuilderInfoCard")
        expect(pageSource).not.toContain("Describe Your Workflow")
        expect(pageSource).not.toContain("Generated Workflow Preview")
        expect(pageSource).not.toContain("Template Name")
        expect(pageSource).not.toContain("How It Works")
    })

    it("keeps forms list page sections split into focused helpers", () => {
        const source = readSource("app/(app)/automation/forms/page.tsx")
        const pageSource = readFunctionSource(source, "FormsListPage")

        expect(source).toContain("function FormsPageHeader")
        expect(source).toContain("function FormsPageTabs")
        expect(source).toContain("function FormsGrid")
        expect(source).toContain("function FormCard")
        expect(source).toContain("function FormTemplatesGrid")
        expect(source).toContain("function FormTemplateCard")
        expect(source).toContain("function CreateFormDialog")
        expect(source).toContain("function DeleteFormDialog")
        expect(source).toContain("function ShareFormDialog")
        expect(pageSource).not.toContain("No forms yet")
        expect(pageSource).not.toContain("No templates yet")
        expect(pageSource).not.toContain("Share Application Form")
    })

    it("keeps AI assistant chat helpers compiler-friendly", () => {
        const source = readSource("app/(app)/ai-assistant/page.tsx")

        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).toContain("function createWelcomeMessage")
        expect(source).toContain("function createTimestampId")
        expect(source).toContain("function useAIAssistantHistorySession")
        expect(source).toContain("if (isAuthLoading) return")
        expect(source).toContain("chatStateRef.current = { ...chatStateRef.current, ...payload }")
        expect(source).not.toContain("chatStateRef.current = chatState")
        expect(source).not.toContain(
            "useEffect(() => {\n        chatStateRef.current = chatState"
        )
        expect(source).not.toContain("const currentSession = chatHistory.find")
        expect(source).not.toContain("useEffect(() => {\n        if (isStreaming) return")
        expect(source).not.toContain("`session-${Date.now()}`")
        expect(source).not.toContain("`user-${Date.now()}`")
        expect(source).not.toContain("`assistant-${Date.now()}`")
    })

    it("keeps AI assistant page sections split from the chat controller", () => {
        const source = readSource("app/(app)/ai-assistant/page.tsx")
        const pageSource = readFunctionSource(source, "AIAssistantPage")

        expect(source).toContain("function useAIAssistantChat")
        expect(source).toContain("function AIAssistantHeader")
        expect(source).toContain("function AIAssistantSidebar")
        expect(source).toContain("function AIAssistantChatWindow")
        expect(source).toContain("function AIAssistantMessageList")
        expect(source).toContain("function AIAssistantComposer")
        expect(source).toContain("function ProposedActionList")
        expect(pageSource).not.toContain("Quick Actions")
        expect(pageSource).not.toContain("Chat History")
        expect(pageSource).not.toContain("Proposed Action")
        expect(pageSource).not.toContain("Ask anything")
    })

    it("keeps AI context state updates compiler-friendly", () => {
        const source = readSource("lib/context/ai-context.tsx")
        const hotkeySource = readSource("lib/hooks/use-ai-toggle-hotkey.ts")

        expect(source).toContain("function aiEntityContextReducer")
        expect(source).toContain("const [entityContext, dispatchEntityContext] = useReducer(")
        expect(source).toContain("state.entityId === action.context.entityId")
        expect(source).toContain("const [setContext] = useState(")
        expect(source).toContain("const [clearContext] = useState(")
        expect(source).toContain(
            "}, [canUseAI, clearContext, entityId, entityName, entityType, setContext])"
        )
        expect(source.match(/\buseEffect\(/g)).toHaveLength(1)
        expect(source).toContain("useAIToggleHotkey(canUseAI")
        expect(source).not.toContain('window.addEventListener("keydown"')
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("React.useCallback")
        expect(source).not.toContain("setEntityType")
        expect(source).not.toContain("setEntityId")
        expect(source).not.toContain("setEntityName")
        expect(hotkeySource).toContain("const onToggleEvent = useEffectEvent(onToggle)")
        expect(hotkeySource).toContain('window.addEventListener("keydown", handleKeyDown)')
        expect(hotkeySource).toContain('window.removeEventListener("keydown", handleKeyDown)')
        expect(hotkeySource).toContain("}, [enabled])")
    })

    it("documents intentional exhaustive-deps exceptions with React Doctor rule names", () => {
        const aiAssistantSource = readSource("app/(app)/ai-assistant/page.tsx")
        const dashboardFilterSource = readSource("app/(app)/dashboard/components/dashboard-filter-bar.tsx")
        const intendedParentMatchesSource = readSource("app/(app)/intended-parents/matches/page.client.tsx")
        const intendedParentsSource = readSource("app/(app)/intended-parents/page.client.tsx")
        const surrogatesSource = readSource("app/(app)/surrogates/page.client.tsx")

        for (const source of [
            aiAssistantSource,
            dashboardFilterSource,
            intendedParentMatchesSource,
            intendedParentsSource,
            surrogatesSource,
        ]) {
            expect(source).not.toContain("eslint-disable-next-line react-doctor/exhaustive-deps")
            expect(source).not.toContain("eslint-disable-line react-doctor/exhaustive-deps")
        }
        expect(aiAssistantSource).toContain("oxlint-disable-next-line react-doctor/exhaustive-deps")
        expect(dashboardFilterSource).toContain("oxlint-disable-next-line react-doctor/exhaustive-deps")
        expect(intendedParentMatchesSource).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(intendedParentMatchesSource).not.toContain("oxlint-disable-line react-doctor/exhaustive-deps")
        expect(intendedParentsSource).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(intendedParentsSource).not.toContain("oxlint-disable-line react-doctor/exhaustive-deps")
        expect(surrogatesSource).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(surrogatesSource).not.toContain("oxlint-disable-line react-doctor/exhaustive-deps")
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
        const headerProps = source.slice(
            source.indexOf("type WorkflowTemplateHeaderProps"),
            source.indexOf("function WorkflowTemplateHeader")
        )

        expect(source).not.toContain("finally")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(headerProps).toContain('mode: "new" | "existing"')
        expect(headerProps).toContain('publicationStatus: "published" | "draft"')
        expect(headerProps).toContain('busyAction: "delete" | "save" | "publish" | null')
        expect(headerProps).not.toContain("isPublished: boolean")
        expect(headerProps).not.toContain("isPublishing: boolean")
        expect(source).toContain('toast.success("Template saved")')
        expect(source).toContain('toast.success("Template published")')
    })

    it("owns MassEditStageModal sessions without reset Effects", () => {
        const source = readSource("components/surrogates/MassEditStageModal.tsx")

        expect(source).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(source).toContain("const defaultTargetStageId =")
        expect(source).toContain("function MassEditStageOpenSession(")
        expect(source).toContain("if (!props.open) return null")
        expect(source).toContain("const previewSignature =")
        expect(source).toContain("previewState?.signature === previewSignature")
        expect(source).toContain("function massEditStageReducer")
        expect(source).toContain("const [storedState, dispatch] = React.useReducer(")
        expect(source).toContain("massEditStageReducer,")
        expect(source).not.toContain("React.useEffect")
        expect(source).not.toContain("hasInitializedOpenRef")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).not.toContain("memo(")
        expect(source).not.toContain("setStatesInput")
        expect(source).not.toContain("setPreviewState")
        expect(source).not.toContain("setPreview(null)")
    })

    it("keeps mass edit stage modal sections split into focused render helpers", () => {
        const source = readSource("components/surrogates/MassEditStageModal.tsx")
        const modalSource = readFunctionSource(source, "MassEditStageModal")

        expect(source).toContain("function MassEditBaseFiltersSection")
        expect(source).toContain("function MassEditExtraFiltersSection")
        expect(source).toContain("function MassEditActionSection")
        expect(source).toContain("function MassEditPreviewSection")
        expect(source).toContain("function MassEditFooter")
        expect(modalSource).not.toContain("Filter Logic")
        expect(modalSource).not.toContain("Preview Matches")
        expect(modalSource).not.toContain("Archive action will soft-archive")
    })

    it("derives open alert count instead of storing duplicate state", () => {
        const source = readSource("app/ops/agencies/[orgId]/page.client.tsx")

        expect(source).toContain("const openAlertCount = orgAlerts.filter")
        expect(source).not.toContain("const [openAlertCount, setOpenAlertCount] = useState")
    })

    it("keeps ops agency detail page sections split from the controller", () => {
        const source = readSource("app/ops/agencies/[orgId]/page.client.tsx")
        const pageSource = readFunctionSource(source, "AgencyDetailPage")

        expect(source).toContain("function useAgencyDetailController")
        expect(source).toContain("function AgencyDetailLoadingState")
        expect(source).toContain("function AgencyDetailMissingState")
        expect(source).toContain("function AgencyDetailHeader")
        expect(source).toContain("function AgencyDetailTabContent")
        expect(pageSource).not.toContain("AgencyOverviewTab")
        expect(pageSource).not.toContain("Agency not found")
        expect(pageSource).not.toContain("Subscription Tab")
    })

    it("uses reducer-based local state in CSVUpload", () => {
        const source = readSource("components/import/CSVUpload.tsx")

        expect(source).toContain("const [state, dispatch] = useReducer")
        expect(source).toContain("function csvUploadReducer(")
        expect(source).toContain("function reconcileBackdateCreatedAt(")
        expect(source).not.toMatch(/\buseEffect\b/)
        expect(source).not.toContain("sync_backdate_from_created_at_mapping")
    })

    it("keeps CSV upload rendering split into focused sections", () => {
        const source = readSource("components/import/CSVUpload.tsx")

        expect(source).toContain("function CSVUploadDropzone")
        expect(source).toContain("function CSVPreviewSummaryCard")
        expect(source).toContain("function CSVTemplateAppliedAlert")
        expect(source).toContain("function CSVAiPromptDialog")
        expect(source).toContain("function CSVColumnMappingCard")
        expect(source).toContain("function CSVColumnMappingRow")
        expect(source).toContain("function CSVSamplePreviewCard")
        expect(source).toContain("function CSVImportFooter")
        expect(source).toContain("function CSVImportStatusMessages")
        expect(source).toContain("function CSVValidationDialog")
        expect(source).toContain("<CSVUploadDropzone")
        expect(source).toContain("<CSVColumnMappingCard")
        expect(source).toContain("<CSVValidationDialog")
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
        expect(source).not.toContain("React.useEffect")
        expect(source).not.toContain("const ref = React.useRef<HTMLButtonElement>(null)")
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

    it("keeps RichTextEditor split and free of compiler-obsolete callbacks", () => {
        const source = readSource("components/rich-text-editor.tsx")
        const contentSyncSource = readSource("lib/hooks/use-sync-rich-text-editor-content.ts")

        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useEffect")
        expect(source).toContain("RichTextEditorLoading")
        expect(source).toContain("RichTextEditorToolbar")
        expect(source).toContain("useSyncRichTextEditorContent(editor, content)")
        expect(contentSyncSource).toContain("useEffect(() =>")
        expect(contentSyncSource).toContain("editor.commands.setContent(content)")
        expect(contentSyncSource).toContain("}, [content, editor])")
        expect(source).not.toContain("emoji-picker-react")
        expect(source).not.toContain("BoldIcon")
        expect(source).not.toContain("SmileIcon")
    })

    it("keeps transcript JSON synchronization behind a tested editor boundary", () => {
        const source = readSource("components/surrogates/interviews/TranscriptEditor.tsx")
        const contentSyncSource = readSource("lib/hooks/use-sync-tiptap-json-content.ts")

        expect(source).toContain("useSyncTipTapJsonContent(editor, content)")
        expect(source).not.toContain("useEffect")
        expect(contentSyncSource).toContain("const nextContent = content ?? EMPTY_TIPTAP_DOCUMENT")
        expect(contentSyncSource).toContain("editor.commands.setContent(nextContent)")
        expect(contentSyncSource).toContain("}, [content, editor])")
    })

    it("keeps transcript viewer DOM listeners behind a tested lifecycle boundary", () => {
        const source = readSource("components/surrogates/interviews/TranscriptViewer.tsx")
        const listenerSource = readSource("lib/hooks/use-transcript-viewer-listeners.ts")

        expect(source).toContain("useTranscriptViewerListeners({")
        expect(source).toContain("enabled: Boolean(renderedHtml)")
        expect(source).not.toContain("useEffect")
        expect(listenerSource).toContain("const onMouseUpEvent = useEffectEvent(onMouseUp)")
        expect(listenerSource).toContain('container.addEventListener("mouseup", handleMouseUp)')
        expect(listenerSource).toContain('document.removeEventListener("keydown", handleKeyDown)')
        expect(listenerSource).toContain("}, [containerRef, enabled])")
    })

    it("observes transcript height only while connector lines are visible", () => {
        const source = readSource(
            "components/surrogates/interviews/InterviewComments/ConnectorLines.tsx"
        )
        const observerSource = readSource("lib/hooks/use-observed-scroll-height.ts")

        expect(source).toContain(
            "const connectorVisible = Boolean(activeNoteId || newComment.type === \"pending\")"
        )
        expect(source).toContain(
            "const transcriptHeight = useObservedScrollHeight(transcriptRef, connectorVisible)"
        )
        expect(source).not.toContain("useEffect")
        expect(observerSource).toContain("const resizeObserver = new ResizeObserver(updateHeight)")
        expect(observerSource).toContain("resizeObserver.disconnect()")
        expect(observerSource).toContain("}, [elementRef, enabled])")
    })

    it("keeps safe HTML parsing and sanitization free of manual React memoization", () => {
        const source = readSource("components/safe-html-content.tsx")

        expect(source).toContain("const sanitizedHtml = sanitizeHtml(html)")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).not.toContain("memo(")
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
        const providerSource = readFunctionSource(source, "InterviewTabProvider")

        expect(source).toContain("function buildInterviewFormState")
        expect(source).toContain("function useInterviewDialogFormState")
        expect(source).toContain("function useInterviewAttachmentActions")
        expect(providerSource).toContain("useInterviewDialogFormState()")
        expect(providerSource).toContain("useInterviewAttachmentActions(selectedId)")
        expect(providerSource).not.toContain("const [dialog, setDialog]")
        expect(providerSource).not.toContain("const [upload, setUpload]")
        expect(providerSource).not.toContain("const openEditor =")
        expect(providerSource).not.toContain("const uploadFiles =")
        expect(providerSource).not.toContain("const requestTranscription =")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("finally")
        expect(source).not.toContain('if (dialog.type === "editor")')
        expect(source).toContain("await Promise.all(")
        expect(source).not.toMatch(/for \(const file of Array\.from\(files\)\)[\s\S]*await uploadAttachmentMutation\.mutateAsync/)
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
        expect(source).toContain('width="100%"')
        expect(source).toContain('height="100%"')
        expect(source).not.toContain('from "recharts"')
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("useRef")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("KPICardSkeleton")
    })

    it("lets Recharts own responsive chart sizing without mount state", () => {
        const source = readSource("components/ui/chart.tsx")

        expect(source).toContain('import dynamic from "next/dynamic"')
        expect(source).toContain('import("recharts")')
        expect(source).toContain('width="100%"')
        expect(source).toContain('height="100%"')
        expect(source).toContain("minHeight={1}")
        expect(source).toContain("minWidth={1}")
        expect(source).not.toContain('from "recharts"')
        expect(source).not.toContain("import * as RechartsPrimitive")
        expect(source).not.toContain("React.useState")
        expect(source).not.toContain("setSize")
        expect(source).not.toContain("getBoundingClientRect")
        expect(source).not.toContain("ResizeObserver")
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

    it("keeps dashboard overview derivations compiler-friendly", () => {
        const sources = [
            "app/(app)/dashboard/page.client.tsx",
            "app/(app)/dashboard/components/kpi-cards-section.tsx",
            "app/(app)/dashboard/components/stage-chart.tsx",
            "app/(app)/dashboard/components/trend-chart.tsx",
        ].map(readSource)

        for (const source of sources) {
            expect(source).not.toContain("useMemo")
            expect(source).not.toContain("useCallback")
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

    it("keeps report derived data compiler-friendly", () => {
        const sources = [
            readSource("components/reports/TeamPerformanceChart.tsx"),
            readSource("components/reports/MetaSpendDashboard.tsx"),
            readSource("components/reports/TeamPerformanceTable.tsx"),
        ]

        for (const source of sources) {
            expect(source).not.toContain("useMemo")
        }

        const teamTableSource = sources[2]
        expect(teamTableSource).toContain("function formatDays")
        expect(teamTableSource).toContain("function formatPercent")
        expect(teamTableSource).toContain("function conversionBadgeClass")
        expect(teamTableSource).not.toContain('role="list"')
    })

    it("keeps team performance table sections split into focused render helpers", () => {
        const source = readSource("components/reports/TeamPerformanceTable.tsx")
        const tableSource = readExportedFunctionSource(source, "TeamPerformanceTable")

        expect(source).toContain("function TeamPerformanceStatusCard")
        expect(source).toContain("function TeamPerformanceMobileSummary")
        expect(source).toContain("function TeamPerformanceDesktopTable")
        expect(source).toContain("function TeamPerformanceDesktopDataRow")
        expect(tableSource).not.toContain("<TableHeader>")
        expect(tableSource).not.toContain('aria-label="Team performance mobile summary"')
    })

    it("keeps unified calendar data timezone derivation compiler-friendly", () => {
        const source = readSource("lib/hooks/use-unified-calendar-data.ts")

        expect(source).toContain("function getBrowserTimezone")
        expect(source).toContain("const userTimezone = getBrowserTimezone()")
        expect(source).not.toContain("useMemo")
    })

    it("keeps hook-level socket and stream callbacks compiler-friendly", () => {
        const hookSources = [
            readSource("lib/hooks/use-ai.ts"),
            readSource("lib/hooks/use-browser-notifications.ts"),
            readSource("lib/hooks/use-dashboard-socket.ts"),
            readSource("lib/hooks/use-notification-socket.ts"),
        ]

        for (const source of hookSources) {
            expect(source).not.toContain("useCallback")
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
        const pageSource = readFunctionSource(source, "AIStudioPage")

        expect(source).toContain("function buildSettingsFormState")
        expect(source).toContain("type AIStudioSettingsDialogState")
        expect(source).toContain("function aiStudioSettingsDialogReducer")
        expect(source).toContain("function AIStudioHeader")
        expect(source).toContain("function AIStudioAlerts")
        expect(source).toContain("function AIStudioLoadingShell")
        expect(source).toContain("function DraftGeneratorCard")
        expect(source).toContain("function AIStudioCreateTab")
        expect(source).toContain("function AIStudioGalleryTab")
        expect(source).toContain("function AIStudioSettingsDialog")
        expect(source).toContain("aiStudioSettingsDialogReducer,")
        expect(source).toContain("const openSettingsDialog =")
        expect(pageSource).not.toContain("AI Studio Preview")
        expect(pageSource).not.toContain("Draft generator")
        expect(pageSource).not.toContain("Studio settings")
        expect(source).not.toContain("const [settingsOpen, setSettingsOpen]")
        expect(source).not.toContain("const [settingsApiKey, setSettingsApiKey]")
        expect(source).not.toContain("const [agentsMd, setAgentsMd]")
        expect(source).not.toContain("const [skillsMd, setSkillsMd]")
        expect(source).not.toContain("const [settingsSaved, setSettingsSaved]")
        expect(source).not.toContain("useEffect(() =>")
        expect(source).not.toContain("useMemo(")
        expect(source).not.toContain("finally")
    })

    it("keeps workflow execution details split into focused helpers", () => {
        const source = readSource("app/(app)/automation/executions/page.tsx")
        const pageSource = readFunctionSource(source, "WorkflowExecutionsPage")

        expect(source).toContain("function ExecutionDetailsRow")
        expect(source).toContain("function ExecutionActionsTimeline")
        expect(source).toContain("function ExecutionErrorPanel")
        expect(source).toContain("function ExecutionTriggerEventDetails")
        expect(source).toContain("<ExecutionDetailsRow")
        expect(source).toContain("function WorkflowExecutionsHeader")
        expect(source).toContain("function WorkflowExecutionStatsGrid")
        expect(source).toContain("function WorkflowExecutionFilters")
        expect(source).toContain("function WorkflowExecutionsTable")
        expect(source).toContain("function WorkflowExecutionRetryDialog")
        expect(pageSource).not.toContain("Total 24h")
        expect(pageSource).not.toContain("All Statuses")
        expect(pageSource).not.toContain("Retry workflow execution?")
    })

    it("keeps public booking selection state reducer-driven", () => {
        const source = readSource("components/appointments/PublicBookingPage.tsx")

        expect(source).toContain("type BookingSelectionState")
        expect(source).toContain("function bookingSelectionReducer")
        expect(source).toContain("bookingSelectionReducer,")
        expect(source).not.toContain("const [selectedTypeId, setSelectedTypeId]")
        expect(source).not.toContain("const [selectedDate, setSelectedDate]")
        expect(source).not.toContain("const [selectedSlot, setSelectedSlot]")
        expect(source).not.toContain("const [selectedMeetingMode, setSelectedMeetingMode]")
        expect(source).not.toContain("const [showForm, setShowForm]")
    })

    it("keeps platform system campaign recipients split into focused helpers", () => {
        const source = readSource("app/ops/templates/system/[systemKey]/page.client.tsx")

        expect(source).toContain("function SystemTemplateCampaignRecipients")
        expect(source).toContain("function SystemTemplateCampaignRecipientCard")
        expect(source).toContain("<SystemTemplateCampaignRecipients")
        expect(source).not.toContain("selectedOrgIds.map((orgId) => {")
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
        const tabSource = readExportedFunctionSource(source, "SurrogateApplicationTab")

        expect(source).toContain('aria-label="Upload application file"')
        expect(source).toContain("function SurrogateApplicationLoadingCard")
        expect(source).toContain("function SurrogateApplicationErrorCard")
        expect(source).toContain("function SurrogateApplicationEmptyState")
        expect(source).toContain("function SurrogateApplicationSubmittedView")
        expect(source).toContain("function SurrogateApplicationFieldEditor")
        expect(source).toContain("function SurrogateApplicationFilesCard")
        expect(source).toContain("function SurrogateApplicationReviewDialogs")
        expect(tabSource.split("\n").length).toBeLessThan(300)
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

    it("keeps surrogate list filters derived from URL state", () => {
        const source = readSource("app/(app)/surrogates/page.client.tsx")

        expect(source).toContain("function readSurrogateListUrlState")
        expect(source).toContain("const normalizedSearchParams = getNormalizedSurrogateListSearchParams(searchParams)")
        expect(source).toContain("const listUrlState = readSurrogateListUrlState(normalizedSearchParams, canFilterByAssignee)")
        expect(source).toContain("const searchQuery = searchDraft.query === currentQuery ? searchDraft.value : debouncedSearch")
        expect(source).not.toContain("const [stageFilter, setStageFilter] = useState<string>(urlStage || \"all\")")
        expect(source).not.toContain("const [debouncedSearch, setDebouncedSearch]")
        expect(source).not.toContain("hasSyncedSearchRef")
        expect(source).not.toContain("// Sync debouncedSearch to URL")
        expect(source).not.toContain("// Sync state when URL changes")
        expect(source).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(source).not.toContain("oxlint-disable-line react-doctor/exhaustive-deps")
    })

    it("does not expose intake pool grants in team settings", () => {
        const source = readSource("app/(app)/settings/team/members/[id]/page.client.tsx")

        expect(source).not.toContain("useIntakePoolGrants")
        expect(source).not.toContain("useCreateIntakePoolGrant")
        expect(source).not.toContain("useRevokeIntakePoolGrant")
        expect(source).not.toContain("Intake Pool Access")
    })

    it("uses Sets for team member permission membership checks", () => {
        const source = readSource("app/(app)/settings/team/members/[id]/page.client.tsx")

        expect(source).toContain("const existingOverrideKeys = new Set(existingOverrides)")
        expect(source).toContain("const effectivePermissionKeys = new Set(effectivePermissions)")
        expect(source).toContain("const pendingOverrideRemovals = new Set(pendingOverrides.remove)")
        expect(source).not.toContain("existingOverrides.includes(")
        expect(source).not.toContain("effectivePermissions.includes(")
        expect(source).not.toContain("pendingOverrides.remove.includes(")
    })

    it("keeps team member detail rendering split into focused sections", () => {
        const source = readSource("app/(app)/settings/team/members/[id]/page.client.tsx")
        const pageIndex = source.indexOf("export default function MemberDetailPage()")
        const firstHelperIndex = source.indexOf("function MemberDetailToolbar")
        const pageSource = source.slice(
            pageIndex,
            firstHelperIndex > pageIndex ? firstHelperIndex : undefined
        )

        expect(pageIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function MemberDetailToolbar")
        expect(source).toContain("function MemberProfileCard")
        expect(source).toContain("function PermissionOverridesCard")
        expect(source).toContain("function DangerZoneCard")
        expect(pageSource).not.toContain("Last Login")
        expect(pageSource).not.toContain("Permission Overrides")
        expect(pageSource).not.toContain("Danger Zone")
        expect(pageSource).not.toContain("displayedOverrides.map")
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

    it("keeps import lifecycle cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-import.ts")

        expect(source).not.toContain("function invalidateImportCaches")
        expect(source).not.toContain("invalidateImportCaches(queryClient")

        for (const queryKey of [
            "importKeys.lists()",
            "importKeys.pending()",
            "importKeys.detail(importId)",
            "surrogateKeys.lists()",
            "surrogateKeys.stats()",
            "surrogateKeys.intelligentSummary()",
        ]) {
            expect(source).toContain(`queryKey: ${queryKey}`)
        }
    })

    it("keeps focused AI usage cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-ai.ts")

        for (const functionName of [
            "useSummarizeSurrogate",
            "useDraftEmail",
            "useAnalyzeDashboard",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("invalidateAIUsageCaches(queryClient)")
            expect(functionSource, functionName).toContain("queryKey: aiKeys.usageSummary()")
        }
    })

    it("keeps interview AI usage cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-interviews.ts")

        for (const functionName of [
            "useSummarizeInterview",
            "useSummarizeAllInterviews",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("invalidateAIUsageCaches(queryClient)")
            expect(functionSource, functionName).toContain("queryKey: ['ai', 'usage', 'summary']")
        }
    })

    it("keeps workflow mutation cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-workflows.ts")

        expect(source).not.toContain("function invalidateWorkflowCollectionCaches")
        expect(source).not.toContain("function refreshWorkflowDetailCache")

        for (const functionName of [
            "useUpdateWorkflow",
            "useDeleteWorkflow",
            "useToggleWorkflow",
            "useDuplicateWorkflow",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("invalidateWorkflowCollectionCaches(queryClient)")
            expect(functionSource, functionName).toContain("queryKey: workflowKeys.lists()")
            expect(functionSource, functionName).toContain("queryKey: workflowKeys.stats()")
        }

        for (const [functionName, idExpression] of [
            ["useUpdateWorkflow", "updated.id"],
            ["useToggleWorkflow", "updated.id"],
            ["useDuplicateWorkflow", "created.id"],
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("refreshWorkflowDetailCache(queryClient")
            expect(functionSource, functionName).toContain(`queryClient.setQueryData(workflowKeys.detail(${idExpression})`)
            expect(functionSource, functionName).toContain(`queryKey: workflowKeys.detail(${idExpression})`)
        }

        expect(readExportedFunctionSource(source, "useDeleteWorkflow")).toContain("queryKey: workflowKeys.detail(id)")
    })

    it("keeps email send surrogate cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-email-templates.ts")
        const functionSource = readExportedFunctionSource(source, "useSendEmail")

        expect(source).not.toContain("invalidateSurrogateCrmCaches")
        expect(functionSource).toContain("queryKey: surrogateKeys.activity(variables.surrogate_id)")
        expect(functionSource).toContain("queryKey: surrogateKeys.detail(variables.surrogate_id)")
        expect(functionSource).toContain("queryKey: surrogateKeys.lists()")
        expect(functionSource).toContain("queryKey: ['analytics', 'activity-feed']")
    })

    it("keeps Zoom surrogate cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-user-integrations.ts")

        expect(source).not.toContain("invalidateSurrogateCrmCaches")

        for (const functionName of [
            "useCreateZoomMeeting",
            "useSendZoomInvite",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.activity(")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.detail(")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.lists()")
            expect(functionSource, functionName).toContain("queryKey: ['analytics', 'activity-feed']")
        }
    })

    it("keeps selected surrogate mutation cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-surrogates.ts")

        expect(source).not.toContain("function invalidateSelectedSurrogateMutationCaches")

        for (const functionName of [
            "useBulkAssign",
            "useBulkArchive",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("invalidateSelectedSurrogateMutationCaches(queryClient")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.activity(surrogateId)")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.detail(surrogateId)")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.lists()")
            expect(functionSource, functionName).toContain("queryKey: ['analytics', 'activity-feed']")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.stats()")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.unassignedQueue()")
        }
    })

    it("keeps form mutation cache invalidations visible to React Doctor", () => {
        const source = readSource("lib/hooks/use-forms.ts")

        expect(source).not.toContain("function invalidateFormSubmissionMutationCaches")
        expect(source).not.toContain("function invalidateFormSubmissionFileMutationCaches")

        const sendIntakeLinkSource = readExportedFunctionSource(source, "useSendFormIntakeLink")
        expect(sendIntakeLinkSource).not.toContain("invalidateSurrogateCrmCaches(queryClient")
        expect(sendIntakeLinkSource).toContain("queryKey: surrogateKeys.activity(surrogateId)")
        expect(sendIntakeLinkSource).toContain("queryKey: surrogateKeys.detail(surrogateId)")
        expect(sendIntakeLinkSource).toContain("queryKey: surrogateKeys.lists()")
        expect(sendIntakeLinkSource).toContain("queryKey: ['analytics', 'activity-feed']")

        for (const functionName of [
            "useApproveFormSubmission",
            "useRejectFormSubmission",
            "useResolveSubmissionMatch",
            "useRetrySubmissionMatch",
            "useUpdateSubmissionAnswers",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("invalidateFormSubmissionMutationCaches(queryClient")
            expect(functionSource, functionName).toContain("queryKey: formKeys.submissionLists(submission.form_id)")
            expect(functionSource, functionName).toContain("queryKey: formKeys.surrogateSubmission(submission.form_id, submission.surrogate_id)")
            expect(functionSource, functionName).toContain("queryKey: formKeys.intakeLead(submission.intake_lead_id)")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.activity(submission.surrogate_id)")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.detail(submission.surrogate_id)")
            expect(functionSource, functionName).toContain("queryKey: surrogateKeys.lists()")
            expect(functionSource, functionName).toContain("queryKey: ['analytics', 'activity-feed']")
        }

        for (const functionName of [
            "useUploadSubmissionFile",
            "useDeleteSubmissionFile",
        ]) {
            const functionSource = readExportedFunctionSource(source, functionName)
            expect(functionSource, functionName).not.toContain("invalidateFormSubmissionFileMutationCaches(queryClient")
            expect(functionSource, functionName).toContain("queryKey: formKeys.submissionLists(formId)")
            expect(functionSource, functionName).toContain("queryKey: formKeys.surrogateSubmission(formId, surrogateId)")
        }
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
        expect(avatarSource).not.toContain("function AvatarImage")
        expect(avatarSource).not.toContain("function AvatarFallback")
        expect(readSource("components/ui/collapsible.tsx")).not.toContain("function CollapsibleTrigger")
        expect(readSource("components/ui/collapsible.tsx")).not.toContain("function CollapsibleContent")
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
        expect(popoverSource).not.toContain("function PopoverTrigger")
        expect(popoverSource).not.toContain("function PopoverContent")
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

    it("keeps non-component exports out of component modules", () => {
        const buttonSource = readSource("components/ui/button.tsx")
        const toggleSource = readSource("components/ui/toggle.tsx")
        const timeDisplaySource = readSource("components/ui/time-display.tsx")
        const queryProviderSource = readSource("lib/query-provider.tsx")
        const transcriptEditorSource = readSource("components/surrogates/interviews/TranscriptEditor.tsx")
        const transcriptUtilsSource = readSource("components/surrogates/interviews/transcript-utils.ts")
        const intendedParentFieldsSource = readSource("components/intended-parents/IntendedParentFormFields.tsx")
        const profileCardContextSource = readSource("components/surrogates/profile/ProfileCard/context.tsx")

        expect(buttonSource).not.toContain("export { Button, buttonVariants }")
        expect(toggleSource).not.toContain("export { Toggle, toggleVariants }")
        expect(timeDisplaySource).not.toContain("export function useCurrentMinuteTimestamp")
        expect(timeDisplaySource).not.toContain("export function formatUtcDateLabel")
        expect(queryProviderSource).not.toContain("export function shouldRetryQuery")
        expect(transcriptEditorSource).not.toContain("export { isTranscriptEmpty")
        expect(transcriptUtilsSource).not.toContain("extractCommentIds")
        expect(transcriptUtilsSource).not.toContain("removeCommentFromDoc")
        expect(intendedParentFieldsSource).not.toContain("export const EMPTY_INTENDED_PARENT_FORM_VALUES")
        expect(intendedParentFieldsSource).not.toContain("export function buildIntendedParentCreatePayload")
        expect(intendedParentFieldsSource).not.toContain("export function buildIntendedParentUpdatePayload")
        expect(profileCardContextSource).not.toContain("export const PROFILE_HEADER_NAME_KEY")
        expect(profileCardContextSource).not.toContain("export const PROFILE_HEADER_NOTE_KEY")
        expect(profileCardContextSource).not.toContain("export const PROFILE_CUSTOM_QAS_KEY")
        expect(profileCardContextSource).not.toContain("export function renderProfileTemplate")
    })

    it("keeps the carousel root free of manual React memoization", () => {
        const source = readSource("components/ui/carousel.tsx")

        expect(source).not.toContain("React.useCallback")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain('role="region"')
    })

    it("keeps input group wrappers semantic and compiler-friendly", () => {
        const source = readSource("components/ui/input-group.tsx")

        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("tabIndex={0}")
        expect(source).not.toContain("React.useCallback")
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

    it("keeps unused dependencies out of the web manifest", () => {
        const packageJson = readSource("package.json")

        for (const dependencyName of [
            "@tiptap/extension-underline",
            "html-to-image",
            "input-otp",
            "react-resizable-panels",
            "vaul",
        ]) {
            expect(packageJson, dependencyName).not.toContain(`"${dependencyName}"`)
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
        const providerSource = readFunctionSource(contextSource, "SurrogateDetailLayoutProviderContent")

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
        expect(contextSource).not.toContain("useMemo")
        expect(contextSource).not.toContain("useCallback")
        expect(contextSource).not.toContain("}, [activeDialog]")
        expect(contextSource).toContain("const { push, replace } = useRouter()")
        expect(contextSource).not.toContain("const { get, toString } = searchParams")
        expect(contextSource).toContain("searchParams.toString()")
        expect(contextSource).toContain('searchParams.get("return_to")')
        expect(contextSource).not.toContain("const router = useRouter()")
        expect(contextSource).not.toContain("router.push")
        expect(contextSource).not.toContain("router.replace")
        expect(contextSource).toContain('redirect(getTabUrl("overview") as Route)')
        expect(contextSource).not.toContain("normalizeInvalidTab")
        expect(contextSource).toContain("useTrackSurrogateView(surrogate?.id)")
        expect(contextSource).not.toContain("trackSurrogateViewed(surrogate.id)")
        expect(contextSource).not.toContain("[defaultPipeline?.feature_config, stageOptions, user?.role]")
        expect(contextSource).toContain("function useSurrogateDetailTabNavigation")
        expect(contextSource).toContain("function useSurrogateDetailDataValue")
        expect(contextSource).toContain("function useSurrogateDetailDialogState")
        expect(contextSource).toContain("function useSurrogateDetailZoomValue")
        expect(contextSource).toContain("function useSurrogateDetailActionsValue")
        expect(providerSource.split("\n").length).toBeLessThan(180)
        expect(contextSource).toContain(
            "canRoleAccessStage(user.role, stage, defaultPipeline?.feature_config, false)"
        )
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

    it("keeps public height field prop synchronization render-derived", () => {
        const source = readSource("components/forms/PublicFormFieldRenderer.tsx")

        expect(source).toContain("type HeightDraftSelection")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("setFeetValue(parsedSelection.feet)")
        expect(source).not.toContain("setInchesValue(parsedSelection.inches)")
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

    it("keeps Meta CRM dataset rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")

        expect(source).toContain("function MetaCrmDatasetSettingsFields")
        expect(source).toContain("function MetaCrmDatasetStageMapping")
        expect(source).toContain("function MetaCrmDatasetTestControls")
        expect(source).toContain("<MetaCrmDatasetSettingsFields")
        expect(source).toContain("<MetaCrmDatasetStageMapping")
        expect(source).toContain("<MetaCrmDatasetTestControls")
    })

    it("keeps integrations page rendering split into focused sections", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")
        const pageSource = readFunctionSource(source, "IntegrationsPage")

        expect(source).toContain("function IntegrationsPageHeader")
        expect(source).toContain("function PersonalIntegrationsSection")
        expect(source).toContain("function PersonalIntegrationCard")
        expect(source).toContain("function OrganizationIntegrationsSection")
        expect(source).toContain("function OrganizationIntegrationCard")
        expect(source).toContain("function SystemIntegrationsSection")
        expect(source).toContain("function SystemIntegrationCard")
        expect(source).toContain("function IntegrationsHelpCard")
        expect(source).toContain("function IntegrationConfigurationDialogs")
        expect(pageSource).not.toContain("Personal Integrations")
        expect(pageSource).not.toContain("Organization Integrations")
        expect(pageSource).not.toContain("System Integrations")
        expect(pageSource).not.toContain("Need help?")
    })

    it("keeps AI integration settings rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")
        const sectionSource = readFunctionSource(source, "AIConfigurationSection")

        expect(source).toContain("function AIConfigurationLoadingState")
        expect(source).toContain("function AIConfigurationHeading")
        expect(source).toContain("function AIConsentCard")
        expect(source).toContain("function AISettingsCard")
        expect(source).toContain("function AIProviderField")
        expect(source).toContain("function AIApiKeyField")
        expect(source).toContain("function VertexApiKeySettings")
        expect(source).toContain("function VertexWifSettings")
        expect(source).toContain("function AIModelField")
        expect(source).toContain("function AISaveButton")
        expect(sectionSource).not.toContain("AI Consent Required")
        expect(sectionSource).not.toContain("Vertex AI (WIF)")
        expect(sectionSource).not.toContain("Save AI Configuration")
    })

    it("keeps email integration settings rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")
        const sectionSource = readFunctionSource(source, "EmailConfigurationSection")

        expect(source).toContain("function EmailConfigurationLoadingState")
        expect(source).toContain("function EmailConfigurationHeading")
        expect(source).toContain("function EmailSettingsCard")
        expect(source).toContain("function EmailProviderField")
        expect(source).toContain("function ResendConfigurationFields")
        expect(source).toContain("function ResendApiKeyField")
        expect(source).toContain("function ResendVerifiedDomainBanner")
        expect(source).toContain("function ResendWebhookUrlField")
        expect(source).toContain("function GmailConfigurationFields")
        expect(source).toContain("function EmailSaveButton")
        expect(sectionSource).not.toContain("Resend Configuration")
        expect(sectionSource).not.toContain("Gmail Configuration")
        expect(sectionSource).not.toContain("Save Email Configuration")
    })

    it("keeps Meta configuration rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")
        const sectionSource = readFunctionSource(source, "MetaConfigurationSection")

        expect(source).toContain("function MetaConfigurationLoadingState")
        expect(source).toContain("function MetaConfigurationHeading")
        expect(source).toContain("function LegacyMetaSetupSection")
        expect(source).toContain("function LegacyMetaConnectionsCard")
        expect(source).toContain("function LegacyMetaAdAccountsCard")
        expect(source).toContain("function MetaAdAccountEditDialog")
        expect(source).toContain("function MetaDisconnectDialog")
        expect(sectionSource).not.toContain("Legacy app-based Meta setup")
        expect(sectionSource).not.toContain("Legacy Connections")
        expect(sectionSource).not.toContain("Legacy Ad Accounts + CAPI")
        expect(sectionSource).not.toContain("Edit Ad Account")
        expect(sectionSource).not.toContain("Disconnect Meta account?")
    })

    it("keeps Zapier webhook rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")
        const sectionSource = readFunctionSource(source, "ZapierWebhookSection")

        expect(source).toContain("function ZapierInboundWebhooksCard")
        expect(source).toContain("function ZapierFieldPasteCard")
        expect(source).toContain("function ZapierTestLeadControls")
        expect(source).toContain("function ZapierOutboundSettingsCard")
        expect(source).toContain("function ZapierStageMappingRows")
        expect(source).toContain("function ZapierOutboundTestControls")
        expect(source).toContain("function useZapierWebhookController")
        expect(sectionSource.split("\n").length).toBeLessThan(220)
        expect(sectionSource).not.toContain("Inbound Webhooks")
        expect(sectionSource).not.toContain("Paste Zapier Field List")
        expect(sectionSource).not.toContain("Outbound Stage Events")
        expect(sectionSource).not.toContain("Send Test Event")
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

        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).toContain("const visibleFields: FormField[] = []")
        expect(source).toContain("const renderableFields: FormField[] = []")
        expect(source).not.toContain("pages.flatMap((page) => page.fields).filter")
        expect(source).not.toMatch(/visibleFields\s*\.filter\(\(field\) => field\.type !== "file"\)\s*\.map/)
    })

    it("keeps public embed origin and session state compiler-friendly", () => {
        const source = readSource("app/embed/forms/[slug]/page.client.tsx")
        const sessionHookSource = readSource("lib/hooks/use-embed-form-session-handshake.ts")
        const resizeHookSource = readSource("lib/hooks/use-embed-form-resize-reporting.ts")

        expect(source).toContain("function embedFormReducer")
        expect(source).toContain("const [state, dispatch] = React.useReducer(")
        expect(source).toContain("useEmbedFormSessionHandshake({")
        expect(source).toContain("useEmbedFormResizeReporting(containerRef, parentOrigin)")
        expect(source).not.toContain("React.useEffect")
        expect(source).not.toContain("ResizeObserver")
        expect(source).not.toContain('addEventListener("message"')
        expect(source).not.toContain("React.useState<FormEmbedPublicRead")
        expect(source).not.toContain("React.useState<EmbedSessionState")
        expect(source).not.toContain("React.useState<Answers>")
        expect(source).not.toContain("React.useState<Record<string, boolean>>")
        expect(source).not.toContain("type EmbedSessionState")
        expect(source).not.toContain("setParentOrigin")
        expect(source).not.toContain("setSessionToken")
        expect(source).not.toContain("sessionTokenRef")
        expect(source).not.toContain("finally")
        expect(sessionHookSource).toContain("type EmbedSessionState")
        expect(sessionHookSource).toContain('window.addEventListener("message", onMessage)')
        expect(sessionHookSource).toContain('window.removeEventListener("message", onMessage)')
        expect(sessionHookSource).toContain("window.clearTimeout(fallback)")
        expect(sessionHookSource).toContain("active = false")
        expect(sessionHookSource).toContain("}, [enabled, parentOrigin, slug])")
        expect(resizeHookSource).toContain("new ResizeObserver(sendHeight)")
        expect(resizeHookSource).toContain("observer.disconnect()")
        expect(resizeHookSource).toContain("}, [containerRef, parentOrigin])")
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
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
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
        const componentSource = readFunctionSource(source, "PublicApplicationForm")
        const autosaveSource = readSource("lib/hooks/use-hosted-intake-autosave.ts")

        expect(source).not.toContain("React.useCallback")
        expect(source).toContain("function isDraftValueEmpty")
        expect(source).toContain("function isEmptyValue")
        expect(source).toContain("function isFullNameIdentityField")
        expect(source).toContain("React.useRef<Set<string> | null>(null)")
        expect(source).toContain('React.useRef<Map<string, "no_match" | "match_found"> | null>(null)')
        expect(source).not.toContain("React.useRef<Set<string>>(new Set())")
        expect(source).not.toContain('React.useRef<Map<string, "no_match" | "match_found">>(new Map())')
        expect(source).not.toContain('role="progressbar"')
        expect(source).toContain("type DraftSessionState")
        expect(source).not.toContain("setDraftSession")
        expect(source).not.toContain("setDraftSessionId")
        expect(source).not.toContain("setDraftSessionExists")
        expect(source).not.toContain("skipNextAutosaveRef")
        expect(source).toContain("skipNextAutosave: boolean")
        expect(source).toContain('type: "setSkipNextAutosave"')
        expect(source).toContain("type HostedIntakeBootstrapResult")
        expect(source).toContain("function loadHostedIntakeBootstrap")
        expect(source).toContain("function hostedIntakeReducer")
        expect(source).toContain("const bootstrapQuery = useQuery({")
        expect(source).toContain('queryKey: ["hosted-intake-bootstrap", token]')
        expect(source).toContain("function reconcileHostedIntakeBootstrap(")
        expect(source).toContain("function useHostedIntakeResumeLookup(")
        expect(componentSource).toContain("useHostedIntakeResumeLookup({")
        expect(componentSource).not.toContain("React.useEffect")
        expect(componentSource).not.toContain("resumeLookupTimerRef")
        expect(componentSource).not.toContain("lookupSeqRef")
        expect(source).toContain(
            "const [storedIntakeState, dispatchIntakeState] = React.useReducer("
        )
        expect(source).toContain("draftSession: DraftSessionState")
        expect(source).not.toContain("{ type: \"bootstrapStarted\"; draftSession: DraftSessionState }")
        expect(source).not.toContain("// Validate shared link on mount")
        expect(source).not.toContain("React.useEffect(() => {\n        let cancelled = false")
        expect(source).not.toContain("react-doctor-disable-next-line react-doctor/no-event-handler")
        expect(source).not.toContain("PublicApplicationFormInner")
        expect(source).not.toContain("key={props.slug}")
        expect(source).not.toContain("const [draftSession]")
        expect(source).not.toContain("const [formConfig, setFormConfig]")
        expect(source).not.toContain("const [isLoading, setIsLoading]")
        expect(source).not.toContain("const [formError, setFormError]")
        expect(source).not.toContain("const loadForm = async ()")
        expect(source).not.toContain("setAnswers(restored)")
        expect(source).toContain("useHostedIntakeAutosave({")
        expect(source).not.toContain("autosaveTimerRef")
        expect(autosaveSource).toContain("const onSaveEvent = useEffectEvent(onSave)")
        expect(autosaveSource).toContain("const onSkipNextSaveEvent = useEffectEvent(onSkipNextSave)")
        expect(autosaveSource).toContain("onSkipNextSaveEvent()")
        expect(autosaveSource).toContain("}, [delay, enabled, scopeKey, skipNextSave, trigger])")
        expect(source).not.toContain('throw new Error("Invalid form payload")')
        expect(source).not.toContain("finally")
        expect(source).not.toContain("if (currentStep > steps.length)")
    })

    it("reconciles dashboard URL filters before child queries render", () => {
        const source = readSource("app/(app)/dashboard/context/dashboard-filters.tsx")
        const filterBarSource = readSource("app/(app)/dashboard/components/dashboard-filter-bar.tsx")

        expect(source).toContain("type DashboardFiltersAction")
        expect(source).toContain("function dashboardFiltersReducer")
        expect(source).toContain("function getDashboardFilterSourceKey")
        expect(source).toContain("if (filterState.sourceKey !== filterSourceKey)")
        expect(source).toMatch(/dispatchFilters\(\{\s*type: "syncFromUrl"/)
        expect(source).toContain(
            "filterState.sourceKey === filterSourceKey ? filterState.filters : urlFilters"
        )
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("setDateRangeState")
        expect(source).not.toContain("setCustomRangeState")
        expect(source).not.toContain("setAssigneeIdState")
        expect(source).not.toContain("useCallback")
        expect(filterBarSource).not.toContain("useEffect(()")
        expect(filterBarSource).not.toContain("setAssigneeId(user.user_id)")
    })

    it("contains dashboard mismatch diagnostics in a deduplicated hook", () => {
        const pageSource = readSource("app/(app)/dashboard/page.client.tsx")
        const hookSource = readSource("lib/hooks/use-dashboard-kpi-mismatch-warning.ts")

        expect(pageSource).toContain("useDashboardKpiMismatchWarning({")
        expect(pageSource).not.toContain("useEffect(")
        expect(pageSource).not.toContain('console.warn("[dashboard]')
        expect(hookSource).toContain("const lastWarningKeyRef = useRef<string | null>(null)")
        expect(hookSource).toContain("if (lastWarningKeyRef.current === warningKey) return")
        expect(hookSource).toContain('console.warn("[dashboard] KPI vs distribution mismatch"')
    })

    it("redirects app-shell auth boundaries during render", () => {
        const source = readSource("components/app-shell-client.tsx")
        const authSource = readSource("lib/auth-context.tsx")

        expect(source).toContain('redirect("/login")')
        expect(source).toContain("redirect(getMfaRedirectPath(pathname))")
        expect(source).toContain('redirect("/welcome")')
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("useRouter")
        expect(source).not.toContain("replace(")
        expect(authSource).not.toContain("useRequireAuth")
        expect(authSource).not.toContain("useEffect(()")
    })

    it("redirects signed-out Duo callbacks during render and retains only verification synchronization", () => {
        const pageSource = readSource("app/auth/duo/callback/page.client.tsx")
        const hookSource = readSource("lib/hooks/use-duo-callback-verification.ts")

        expect(pageSource).toContain(
            'redirect(getAuthReturnTo() === "ops" ? "/ops/login" : "/login")'
        )
        expect(pageSource).toContain("useDuoCallbackVerification({")
        expect(pageSource).not.toContain("useEffect")
        expect(pageSource).not.toContain('replace("/ops/login")')
        expect(pageSource).not.toContain('replace("/login")')
        expect(hookSource.match(/useEffect\(\(\) =>/g)).toHaveLength(1)
        expect(hookSource).toContain("verifyDuoCallback(code, state, returnTo)")
        expect(hookSource).toContain("active = false")
        expect(hookSource).toContain("}, [enabled, refreshAuth, replace, returnTo])")
    })

    it("contains unassigned queue view tracking in a named lifecycle hook", () => {
        const pageSource = readSource("app/(app)/surrogates/unassigned/page.client.tsx")
        const hookSource = readSource("lib/hooks/use-track-unassigned-queue-view.ts")

        expect(pageSource).toContain(
            "useTrackUnassignedQueueView(authLoaded && canViewUnassignedQueue)"
        )
        expect(pageSource).not.toContain("useEffect")
        expect(hookSource).toContain("useEffect(() =>")
        expect(hookSource).toContain("trackUnassignedQueueViewed()")
        expect(hookSource).toContain("}, [enabled])")
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

    it("keeps email attachments derived state compiler-friendly", () => {
        const source = readSource("components/email/EmailAttachmentsPanel.tsx")

        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).toContain('aria-label="Choose email attachments to upload"')
    })

    it("keeps email compose dialog derived state compiler-friendly", () => {
        const source = readSource("components/email/EmailComposeDialog.tsx")

        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).toContain("function getHighlightedTemplateParts")
        expect(source).toContain("key={part.key}")
        expect(source).not.toContain("parts.map((part, index)")
        expect(source).not.toContain("const key = `${index}:${part}`")
        expect(source).toContain('role="textbox"')
        expect(source).toContain("contentEditable")
    })

    it("keeps share dialog embed settings render-derived", () => {
        const source = readSource("components/forms/builder/ShareApplicationDialog.tsx")

        expect(source).toContain("function buildEmbedSettingsFromLink")
        expect(source).not.toContain("React.useEffect")
        expect(source).not.toContain("setEmbedSettings(DEFAULT_EMBED_SETTINGS)")
    })

    it("keeps share application dialog tabs split into focused render helpers", () => {
        const source = readSource("components/forms/builder/ShareApplicationDialog.tsx")

        expect(source).toContain("function HostedLinkTabContent")
        expect(source).toContain("function EmbedTabContent")
        expect(source).toContain("function EmbedSettingsPanel")
        expect(source).toContain("function ShareApplicationDialogFooter")
        expect(source).toContain("<HostedLinkTabContent link={selectedQrLink} />")
        expect(source).toContain("<EmbedTabContent")
        expect(source).toContain("<ShareApplicationDialogFooter")
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

    it("uses Sets for campaign selection checkbox membership checks", () => {
        const campaignCreateSource = readSource("app/(app)/automation/campaigns/page.tsx")
        const campaignDetailSource = readSource("app/(app)/automation/campaigns/[id]/page.client.tsx")

        expect(campaignCreateSource).toContain("const selectedStageIdSet = new Set(selectedStages)")
        expect(campaignCreateSource).toContain("const selectedStateCodeSet = new Set(selectedStates)")
        expect(campaignCreateSource).toContain("checked={selectedStageIdSet.has(stage.id)}")
        expect(campaignCreateSource).toContain("checked={selectedStateCodeSet.has(state.value)}")
        expect(campaignCreateSource).not.toContain("checked={selectedStages.includes(stage.id)}")
        expect(campaignCreateSource).not.toContain("checked={selectedStates.includes(state.value)}")

        expect(campaignDetailSource).toContain("const editStageIdSet = new Set(editDraft.stages)")
        expect(campaignDetailSource).toContain("const editStateCodeSet = new Set(editDraft.states)")
        expect(campaignDetailSource).toContain("checked={editStageIdSet.has(stage.id)}")
        expect(campaignDetailSource).toContain("checked={editStateCodeSet.has(state.value)}")
        expect(campaignDetailSource).not.toContain("checked={editStages.includes(stage.id)}")
        expect(campaignDetailSource).not.toContain("checked={editStates.includes(state.value)}")
    })

    it("keeps campaign index rendering split into focused sections", () => {
        const source = readSource("app/(app)/automation/campaigns/page.tsx")

        expect(source).toContain("function CampaignsPageHeader")
        expect(source).toContain("function CampaignsListSection")
        expect(source).toContain("function CampaignCreateWizardDialog")
        expect(source).toContain("function CampaignWizardProgress")
        expect(source).toContain("function CampaignWizardStepContent")
        expect(source).toContain("function CampaignDetailsStep")
        expect(source).toContain("function CampaignTemplateStep")
        expect(source).toContain("function CampaignRecipientsStep")
        expect(source).toContain("function CampaignStateFilterStep")
        expect(source).toContain("function CampaignReviewStep")
        expect(source).toContain("function CampaignRecipientPreviewStep")
        expect(source).toContain("function CampaignScheduleStep")
        expect(source).toContain("function CampaignWizardFooter")
        expect(source).toContain("function CampaignConfirmationDialogs")
        expect(source).toContain("<CampaignsPageHeader")
        expect(source).toContain("<CampaignsListSection")
        expect(source).toContain("<CampaignCreateWizardDialog")
        expect(source).toContain("<CampaignConfirmationDialogs")
    })

    it("uses Set membership for surrogate application multiselect values", () => {
        const source = readSource("components/surrogates/SurrogateApplicationTab.tsx")

        expect(source).toContain("const selectedValueSet = new Set(selectedValues)")
        expect(source).toContain("const checked = selectedValueSet.has(option.value)")
        expect(source).not.toContain("selectedValues.includes(option.value)")
    })

    it("keeps list filters derived from URL state without mirror effects", () => {
        const intendedParentsSource = readSource("app/(app)/intended-parents/page.client.tsx")
        const matchesSource = readSource("app/(app)/intended-parents/matches/page.client.tsx")
        const surrogatesSource = readSource("app/(app)/surrogates/page.client.tsx")
        const debounceSource = readSource("lib/hooks/use-debounced-search-commit.ts")

        expect(intendedParentsSource).toContain("function readIntendedParentListUrlState")
        expect(intendedParentsSource).toContain("useDebouncedSearchCommit(currentQuery)")
        expect(intendedParentsSource).not.toContain("searchDebounceTimerRef")
        expect(intendedParentsSource).not.toContain("useEffect")
        expect(intendedParentsSource).not.toContain("hasSyncedSearchRef")
        expect(intendedParentsSource).not.toContain("setDebouncedSearch")
        expect(intendedParentsSource).not.toContain("[currentQuery]) // oxlint-disable-line react-doctor/exhaustive-deps")

        expect(matchesSource).toContain("function readMatchListUrlState")
        expect(matchesSource).toContain("useDebouncedSearchCommit(currentQuery)")
        expect(matchesSource).not.toContain("searchDebounceTimerRef")
        expect(matchesSource).not.toContain("useEffect")
        expect(matchesSource).not.toContain("hasSyncedSearchRef")
        expect(matchesSource).not.toContain("setDebouncedSearch")
        expect(matchesSource).not.toContain("[currentQuery]) // oxlint-disable-line react-doctor/exhaustive-deps")
        expect(surrogatesSource).toContain("useDebouncedSearchCommit(currentQuery)")
        expect(surrogatesSource).not.toContain("searchDebounceRef")
        expect(surrogatesSource).not.toContain("useEffect")
        expect(debounceSource).toContain("useEffect(() =>")
        expect(debounceSource).toContain("return cancel")
        expect(debounceSource).toContain("}, [scopeKey])")
    })

    it("delegates main matches search timing to the shared debounced value hook", () => {
        const source = readSource("app/(app)/matches/page.tsx")

        expect(source).toContain('import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"')
        expect(source).toContain("const debouncedSearch = useDebouncedValue(search, 300)")
        expect(source).not.toMatch(/\buseEffect\b/)
        expect(source).not.toContain("setDebouncedSearch")
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

    it("keeps handler-only transcript and schedule values out of render state", () => {
        const selectionPopoverSource = readSource("components/surrogates/interviews/SelectionPopover.tsx")
        const scheduleParserSource = readSource("components/ai/ScheduleParserDialog.tsx")

        expect(selectionPopoverSource).toContain("const selectedTextRef = useRef(\"\")")
        expect(selectionPopoverSource).toContain("const selectedRangeRef = useRef<Range | null>(null)")
        expect(selectionPopoverSource).not.toContain("const [selectedText, setSelectedText] = useState")
        expect(selectionPopoverSource).not.toContain("const [selectedRange, setSelectedRange] = useState")

        expect(scheduleParserSource).toContain("const bulkRequestIdRef = useRef<string | null>(null)")
        expect(scheduleParserSource).not.toContain("const [bulkRequestId, setBulkRequestId] = useState")
        expect(scheduleParserSource).toContain("function makeScheduleParserId()")
        expect(scheduleParserSource).not.toContain("const makeId = () =>")
        expect(scheduleParserSource).toContain("function getConfidenceBadge(confidence: number)")
        expect(scheduleParserSource).not.toContain("const getConfidenceBadge = (confidence")
    })

    it("uses reducer state for the schedule parser workflow", () => {
        const source = readSource("components/ai/ScheduleParserDialog.tsx")

        expect(source).toContain("useReducer")
        expect(source).toContain("scheduleParserStateReducer")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("setScheduleText")
        expect(source).not.toContain("setEditableTasks")
        expect(source).not.toContain("setErrorMessage")
    })

    it("keeps schedule parser rendering split into focused helpers", () => {
        const source = readSource("components/ai/ScheduleParserDialog.tsx")
        const dialogSource = readExportedFunctionSource(source, "ScheduleParserDialog")

        expect(source).toContain("function ScheduleParserInputStep")
        expect(source).toContain("function ScheduleParserReviewStep")
        expect(source).toContain("function ScheduleParserTaskTable")
        expect(source).toContain("function ScheduleParserTaskRow")
        expect(source).toContain("function ScheduleParserFooter")
        expect(dialogSource).not.toContain("<Table")
        expect(dialogSource).not.toContain("Medication Schedule:")
        expect(dialogSource).not.toContain("Create {selectedCount} Task")
    })

    it("keeps email template handler bookkeeping out of render state", () => {
        const source = readSource("app/(app)/automation/email-templates/page.tsx")

        expect(source).toContain("const templateBody = editorState.bodyOverride ?? (editorState.template ? fullTemplate?.body ?? \"\" : \"\")")
        expect(source).toContain("const templateBodyMode = editorState.bodyModeOverride ?? getTemplateBodyMode(editorState.template ? fullTemplate?.body : null)")
        expect(source).toContain("const activeInsertionTargetRef = useRef<ActiveInsertionTarget>(null)")
        expect(source).toContain("const copyShareTargetRef = useRef<EmailTemplateListItem | null>(null)")
        expect(source).toContain("const testSendDefaultVariables: Record<string, string> = {}")
        expect(source).toContain("const testSendVariables = {")
        expect(source).toContain("...testSendState.variables,")
        expect(source).toContain("const libraryCopyTargetRef = useRef<EmailTemplateLibraryItem | null>(null)")
        expect(source).not.toContain("testSendTouchedRef")
        expect(source).not.toContain("const [templateBodyOverride, setTemplateBodyOverride] = useState")
        expect(source).not.toContain("const [templateBodyModeOverride, setTemplateBodyModeOverride] = useState")
        expect(source).not.toContain("const [templateBody, setTemplateBody] = useState")
        expect(source).not.toContain("const [templateBodyMode, setTemplateBodyMode] = useState")
        expect(source).not.toContain("templateBodyModeTouchedRef")
        expect(source).not.toContain("setTemplateBody(fullTemplate.body)")
        expect(source).not.toContain("if (!fullTemplate || !editingTemplate || !fullTemplate.body) return")
        expect(source).not.toContain("const [templateBodyModeTouched, setTemplateBodyModeTouched] = useState")
        expect(source).not.toContain("const [activeInsertionTarget, setActiveInsertionTarget] = useState")
        expect(source).not.toContain("const [copyShareTarget, setCopyShareTarget] = useState")
        expect(source).not.toContain("const [testSendTouched, setTestSendTouched] = useState")
        expect(source).not.toContain("const [libraryCopyTarget, setLibraryCopyTarget] = useState")
    })

    it("keeps email template editor draft state grouped", () => {
        const source = readSource("app/(app)/automation/email-templates/page.tsx")
        const pageSource = readFunctionSource(source, "EmailTemplatesPage")

        expect(source).toContain("type EmailTemplateEditorState")
        expect(source).toContain("function emailTemplateEditorReducer")
        expect(pageSource).toContain("const [editorState, dispatchEditor] = useReducer")
        expect(pageSource).not.toContain("setEditingTemplate")
        expect(pageSource).not.toContain("setTemplateName")
        expect(pageSource).not.toContain("setTemplateSubject")
        expect(pageSource).not.toContain("setTemplateBodyOverride")
        expect(pageSource).not.toContain("setTemplateBodyModeOverride")
        expect(pageSource).not.toContain("setTemplateScope")
    })

    it("keeps email signature draft state grouped", () => {
        const source = readSource("app/(app)/automation/email-templates/page.tsx")
        const pageSource = readFunctionSource(source, "EmailTemplatesPage")

        expect(source).toContain("type SignatureDraftState")
        expect(source).toContain("function signatureDraftReducer")
        expect(pageSource).toContain("const [signatureDraftOverrides, dispatchSignatureDraft] = useReducer")
        expect(pageSource).toContain("const signatureDraft = {")
        expect(pageSource).toContain("...createSignatureDraftState(signatureData),")
        expect(pageSource).toContain("...signatureDraftOverrides,")
        expect(pageSource).not.toContain("setSignatureName")
        expect(pageSource).not.toContain("setSignatureTitle")
        expect(pageSource).not.toContain("setSignaturePhone")
        expect(pageSource).not.toContain("setSignatureLinkedin")
        expect(pageSource).not.toContain("setSignatureTwitter")
        expect(pageSource).not.toContain("setSignatureInstagram")
    })

    it("keeps email test-send dialog state grouped", () => {
        const source = readSource("app/(app)/automation/email-templates/page.tsx")
        const pageSource = readFunctionSource(source, "EmailTemplatesPage")

        expect(source).toContain("type TestSendDialogState")
        expect(source).toContain("function testSendDialogReducer")
        expect(pageSource).toContain("const [testSendState, dispatchTestSend] = useReducer")
        expect(pageSource).not.toContain("setTestSendOpen")
        expect(pageSource).not.toContain("setTestSendTarget")
        expect(pageSource).not.toContain("setTestSendToEmail")
        expect(pageSource).not.toContain("setTestSendIgnoreOptOut")
        expect(pageSource).not.toContain("setTestSendVariables")
    })

    it("clears email library preview state from the preview close handler", () => {
        const source = readSource("app/(app)/automation/email-templates/page.tsx")

        expect(source).toContain("const handlePreviewOpenChange = (open: boolean) =>")
        expect(source).toContain("setShowPreview(open)")
        expect(source).toContain("if (!open) {")
        expect(source).toContain("setLibraryPreviewId(null)")
        expect(source).toContain("onOpenChange={handlePreviewOpenChange}")
        expect(source).not.toContain(`if (!showPreview) {
            React.startTransition(() => {
                setLibraryPreviewId(null)`)
    })

    it("sets the email test recipient from the test dialog open handler", () => {
        const source = readSource("app/(app)/automation/email-templates/page.tsx")

        expect(source).toContain("const handleOpenTestDialog = (template: EmailTemplateListItem) =>")
        expect(source).toContain('dispatchTestSend({ type: "open", target: template, toEmail: user?.email || "" })')
        expect(source).not.toContain("setTestSendToEmail(user.email)")
        expect(source).not.toContain("[testSendOpen, testSendToEmail, user?.email]")
    })

    it("keeps queue edit target out of render state", () => {
        const source = readSource("app/(app)/settings/queues/page.tsx")
        const helperIndex = source.indexOf("function resolveErrorMessage(")
        const componentIndex = source.indexOf("export default function QueuesSettingsPage()")

        expect(source).toContain("const editingQueueRef = React.useRef<Queue | null>(null)")
        expect(source).toContain("editingQueueRef.current = queue")
        expect(source).toContain("editingQueueRef.current = null")
        expect(helperIndex).toBeGreaterThanOrEqual(0)
        expect(helperIndex).toBeLessThan(componentIndex)
        expect(source).not.toContain("const [editingQueue, setEditingQueue] = React.useState")
        expect(source).not.toContain("const resolveErrorMessage = (error: unknown, fallback: string) =>")
    })

    it("keeps queues settings rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/queues/page.tsx")
        const componentIndex = source.indexOf("export default function QueuesSettingsPage()")
        const contentIndex = source.indexOf("function QueuesSettingsContent()")
        const firstHelperIndex = source.indexOf("function QueuesPageHeader")
        const componentSource = source.slice(
            componentIndex,
            firstHelperIndex > componentIndex ? firstHelperIndex : undefined
        )
        const authorizationSource = source.slice(componentIndex, contentIndex)

        expect(componentIndex).toBeGreaterThanOrEqual(0)
        expect(contentIndex).toBeGreaterThan(componentIndex)
        expect(source).toContain('redirect("/settings")')
        expect(source).toContain("return <QueuesSettingsContent />")
        expect(source).not.toContain("React.useEffect")
        expect(authorizationSource).not.toContain("useQueues(")
        expect(authorizationSource).not.toContain("useMembers(")
        expect(source).toContain("function QueuesPageHeader")
        expect(source).toContain("function QueuesStatusContent")
        expect(source).toContain("function QueuesTable")
        expect(source).toContain("function QueueFormDialog")
        expect(source).toContain("function QueueMembersDialog")
        expect(componentSource).not.toContain("<Table")
        expect(componentSource).not.toContain("<Dialog")
        expect(componentSource).not.toContain("No members assigned. Queue is open to all case managers.")
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

    it("keeps rendered list keys after optional prop spreads", () => {
        const attentionPanelSource = readSource("app/(app)/dashboard/components/attention-needed-panel.tsx")
        const appointmentsListSource = readSource("components/appointments/AppointmentsList.tsx")
        const unifiedCalendarSource = readSource("components/appointments/UnifiedCalendar.tsx")
        const medicalInsuranceSource = readSource("components/surrogates/CombinedMedicalInsuranceCard.tsx")
        const commentCardSource = readSource("components/surrogates/interviews/CommentCard.tsx")

        expectKeyAfterLastSpread(attentionPanelSource, "UpcomingItemRow", "key={item.id}")
        expectKeyAfterLastSpread(attentionPanelSource, "OverdueSummaryRow", 'key="overdue-summary"')
        expectKeyAfterLastSpread(appointmentsListSource, "AppointmentCard", "key={appt.id}")
        expectKeyAfterLastSpread(unifiedCalendarSource, "EventItem", "key={appt.id}")
        expectKeyAfterLastSpread(unifiedCalendarSource, "TaskItem", "key={task.id}")
        expectKeyAfterLastSpread(medicalInsuranceSource, "MedicalContactSection", "key={section.key}")
        expectKeyAfterLastSpread(commentCardSource, "ReplyItem", "key={reply.id}")
    })

    it("keeps appointment cards on shared Base UI button semantics", () => {
        const source = readSource("components/appointments/AppointmentsList.tsx")

        expect(source).toContain('import { Button } from "@/components/ui/button"')
        expect(source).toContain("<Button unstyled")
        expect(source).toContain('type="button"')
        expect(source).not.toContain("<button")
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("tabIndex={0}")
        expect(source).not.toContain("onKeyDown={(e)")
    })

    it("keeps appointment card pending actions out of the selectable card variant", () => {
        const source = readSource("components/appointments/AppointmentsList.tsx")
        const appointmentCardSource = readFunctionSource(source, "AppointmentCard")

        expect(appointmentCardSource).toContain("trailingActions")
        expect(appointmentCardSource).not.toContain("isApproving")
        expect(appointmentCardSource).not.toContain("isCancelling")
        expect(appointmentCardSource).not.toContain("onApprove")
        expect(appointmentCardSource).not.toContain("onCancel")
    })

    it("keeps attention needed panel sections split into focused helpers", () => {
        const source = readSource("app/(app)/dashboard/components/attention-needed-panel.tsx")
        const panelSource = readFunctionSource(source, "AttentionNeededPanel")

        expect(source).toContain("function buildUpcomingSections")
        expect(source).toContain("function AttentionPanelSectionHeader")
        expect(source).toContain("function AttentionItemsSection")
        expect(source).toContain("function UpcomingItemsSection")
        expect(source).toContain("function UpcomingSectionGroup")
        expect(panelSource).not.toContain("Unreached leads (7+ days)")
        expect(panelSource).not.toContain("Upcoming This Week")
        expect(panelSource).not.toContain("Unable to load attention items")
    })

    it("keeps small loading variants out of boolean prop APIs", () => {
        const emailTemplatesSource = readSource("app/(app)/automation/email-templates/page.tsx")
        const signaturePhotoFieldSource = readFunctionSource(emailTemplatesSource, "SignaturePhotoField")
        const surrogateAiTabSource = readSource("components/surrogates/detail/SurrogateAiTab.tsx")

        expect(signaturePhotoFieldSource).toContain("avatarAction")
        expect(signaturePhotoFieldSource).toContain("customPhotoAction")
        expect(signaturePhotoFieldSource).not.toContain("uploadStatus")
        expect(signaturePhotoFieldSource).not.toContain("deleteStatus")
        expect(signaturePhotoFieldSource).not.toContain("isUploading")
        expect(signaturePhotoFieldSource).not.toContain("isDeleting")
        expect(signaturePhotoFieldSource).not.toContain("onUpload")
        expect(signaturePhotoFieldSource).not.toContain("onDelete")
        expect(surrogateAiTabSource).toContain("summaryStatus")
        expect(surrogateAiTabSource).toContain("draftEmailStatus")
        expect(surrogateAiTabSource).not.toContain("isGeneratingSummary")
        expect(surrogateAiTabSource).not.toContain("isDraftingEmail")
    })

    it("keeps boolean-heavy action and value state out of component prop APIs", () => {
        const emailTemplatesSource = readSource("app/(app)/automation/email-templates/page.tsx")
        const pipelinesSource = readSource("app/(app)/settings/pipelines/page.tsx")
        const fieldRowSource = readSource("components/surrogates/profile/ProfileCard/FieldRow.tsx")
        const templateCardSource = readFunctionSource(emailTemplatesSource, "TemplateCard")
        const draftActionsSource = readFunctionSource(pipelinesSource, "DraftActionsCard")
        const fieldRowValueSource = readFunctionSource(fieldRowSource, "FieldRowValue")

        expect(templateCardSource).toContain("controls")
        expect(templateCardSource).not.toContain("isReadOnly")
        expect(templateCardSource).not.toContain("canCopy")
        expect(templateCardSource).not.toContain("canShare")
        expect(templateCardSource).not.toContain("canSendTest")
        expect(templateCardSource).not.toContain("canDelete")
        expect(draftActionsSource).toContain("saveState")
        expect(pipelinesSource).toContain('"preview_loading"')
        expect(draftActionsSource).not.toContain("isSaving")
        expect(draftActionsSource).not.toContain("isPreviewLoading")
        expect(draftActionsSource).not.toContain("hasValidationErrors")
        expect(draftActionsSource).not.toContain("hasBlockingIssues")
        expect(fieldRowValueSource).toContain("valueMode")
        expect(fieldRowValueSource).toContain("visibility")
        expect(fieldRowValueSource).toContain("changeState")
        expect(fieldRowValueSource).not.toContain("isEditMode")
        expect(fieldRowValueSource).not.toContain("editingField")
        expect(fieldRowValueSource).not.toContain("isHidden")
        expect(fieldRowValueSource).not.toContain("isRevealed")
        expect(fieldRowValueSource).not.toContain("isOverridden")
        expect(fieldRowValueSource).not.toContain("isStaged")
    })

    it("models login navigation as redirect state instead of loading state", () => {
        const appLoginSource = readSource("app/login/LoginPageClient.tsx")
        const opsLoginSource = readSource("app/ops/login/page.client.tsx")

        expect(appLoginSource).toContain("redirectStatus")
        expect(appLoginSource).not.toContain("isLoading")
        expect(appLoginSource).not.toContain("setIsLoading")
        expect(opsLoginSource).toContain("redirectStatus")
        expect(opsLoginSource).not.toContain("isLoading")
        expect(opsLoginSource).not.toContain("setIsLoading")
    })

    it("keeps surrogate edit dialog saves button-driven", () => {
        const source = readSource("components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx")

        expect(source).toContain("function handleSave")
        expect(source).toContain("form.reportValidity()")
        expect(source).toContain('type="button"')
        expect(source).not.toContain("onSubmit=")
        expect(source).not.toContain("preventDefault")
        expect(source).not.toContain('type="submit"')
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

        expect(source).toContain("type AppointmentTypeFormUpdater =")
        expect(source).toContain("onFormDataChange={setFormData}")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, name: e.target.value }))")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, description: e.target.value }))")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, duration_minutes: parseInt(v) }))")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, buffer_after_minutes: parseInt(v) }))")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, meeting_location: e.target.value }))")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, dial_in_number: e.target.value }))")
        expect(source).toContain("onFormDataChange((current) => ({ ...current, auto_approve: checked }))")
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

    it("keeps appointment type rendering split into focused helpers", () => {
        const source = readSource("components/appointments/AppointmentSettings.tsx")
        const sectionSource = readFunctionSource(source, "AppointmentTypesCard")

        expect(source).toContain("function AppointmentTypesLoadingCard")
        expect(source).toContain("function AppointmentTypesHeader")
        expect(source).toContain("function AppointmentTypeDialog")
        expect(source).toContain("function AppointmentTypeMeetingModeFields")
        expect(source).toContain("function AppointmentTypeConditionalFields")
        expect(source).toContain("function AppointmentTypesEmptyState")
        expect(source).toContain("function AppointmentTypesList")
        expect(source).toContain("function AppointmentTypeListItem")
        expect(sectionSource).toContain("useAppointmentTypes()")
        expect(sectionSource).toContain("useCreateAppointmentType()")
        expect(sectionSource).toContain("useUpdateAppointmentType()")
        expect(sectionSource).toContain("useDeleteAppointmentType()")
        expect(sectionSource).toContain("const handleSubmit = async () =>")
        expect(sectionSource).not.toContain("Different appointment types clients can book")
        expect(sectionSource).not.toContain("New Appointment Type")
        expect(sectionSource).not.toContain("No appointment types yet")
    })

    it("derives public booking confirmation state from the response", () => {
        const source = readSource("components/appointments/PublicBookingPage.tsx")

        expect(source).toContain("if (confirmation && selectedType && selectedSlot)")
        expect(source).not.toContain("const [isConfirmed")
        expect(source).not.toContain("setIsConfirmed")
    })

    it("keeps public booking timezone defaults render-derived", () => {
        const source = readSource("components/appointments/PublicBookingPage.tsx")

        expect(source).toContain("function getInitialClientTimezone")
        expect(source).toContain("function getEffectiveBookingTimezone")
        expect(source).toContain("if (detectedTimezone === DEFAULT_TIMEZONE && orgTimezone) return orgTimezone")
        expect(source).toContain("useSyncExternalStore(")
        expect(source).toContain("const [timezoneOverride, setTimezoneOverride] = useState<string | null>(null)")
        expect(source).toContain("const timezone = getEffectiveBookingTimezone(")
        expect(source).toContain("pageData?.org_timezone,")
        expect(source).toContain("detectedTimezone")
        expect(source).toContain("onValueChange={(v) => v && setTimezoneOverride(v)}")
        expect(source).not.toContain("const [timezone, setTimezone]")
        expect(source).not.toContain("setTimezone(tz)")
        expect(source).not.toContain("setTimezone(orgTimezone)")
    })

    it("uses gap spacing for match dialog radio rows", () => {
        const addTaskSource = readSource("components/matches/AddTaskDialog.tsx")
        const uploadFileSource = readSource("components/matches/UploadFileDialog.tsx")

        expect(addTaskSource).not.toContain("flex items-center space-x-2")
        expect(uploadFileSource).not.toContain("flex items-center space-x-2")
        expect(addTaskSource).toContain("flex items-center gap-2")
        expect(uploadFileSource).toContain("flex items-center gap-2")
    })

    it("keeps match upload file helpers and controls scanner-friendly", () => {
        const source = readSource("components/matches/UploadFileDialog.tsx")

        expect(source).toContain("function formatFileSize(bytes: number)")
        expect(source).toContain('aria-label="Upload match file"')
        expect(source).not.toContain("const formatFileSize =")
    })

    it("keeps match tasks calendar derivations compiler-friendly", () => {
        const source = readSource("components/matches/MatchTasksCalendar.tsx")

        expect(source).not.toContain("useMemo")
    })

    it("uses reducer state for the match task form", () => {
        const source = readSource("components/matches/AddTaskDialog.tsx")

        expect(source).toContain("useReducer")
        expect(source).toContain("taskFormReducer")
        expect(source).not.toContain("useState")
    })

    it("uses reducer state for the surrogate task form", () => {
        const source = readSource("components/surrogates/AddSurrogateTaskDialog.tsx")

        expect(source).toContain("useReducer")
        expect(source).toContain("surrogateTaskFormReducer")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("setTitle")
        expect(source).not.toContain("setError")
    })

    it("uses reducer state for the task dialog form", () => {
        const source = readSource("components/tasks/AddTaskDialog.tsx")

        expect(source).toContain("useReducer")
        expect(source).toContain("taskDialogFormReducer")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("setTitle")
        expect(source).not.toContain("setError")
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

    it("keeps the change stage modal free of manual React memoization", () => {
        const source = readSource("components/surrogates/ChangeStageModal.tsx")

        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
    })

    it("keeps change stage modal reset logic out of effects", () => {
        const source = readSource("components/surrogates/ChangeStageModal.tsx")

        expect(source).toContain("function ChangeStageModalContent")
        expect(source).toContain("const resetInterviewFields =")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("setCalendarToday(new Date())")
    })

    it("keeps change stage modal sections split into focused render helpers", () => {
        const source = readSource("components/surrogates/ChangeStageModal.tsx")
        const contentSource = readFunctionSource(source, "ChangeStageModalContent")

        expect(source).toContain("function StageSelectionList")
        expect(source).toContain("function EffectiveScheduleSection")
        expect(source).toContain("function OnHoldFollowUpSection")
        expect(source).toContain("function InterviewAppointmentSection")
        expect(source).toContain("function DeliveryDetailsSection")
        expect(source).toContain("function ChangeStageWarnings")
        expect(source).toContain("function ChangeStageActions")
        expect(contentSource).not.toContain("Follow-up reminder")
        expect(contentSource).not.toContain("Interview appointment")
        expect(contentSource).not.toContain("Delivery details")
    })

    it("keeps bulk stage change reset logic in event handlers", () => {
        const source = readSource("components/surrogates/BulkChangeStageModal.tsx")

        expect(source).toContain("const handleOpenChange =")
        expect(source).toContain("setTargetStageId(\"\")")
        expect(source).not.toContain("React.useEffect")
    })

    it("keeps small surrogate stage dialogs free of manual React memoization", () => {
        const sources = [
            "components/surrogates/BulkChangeStageModal.tsx",
            "components/surrogates/LogContactAttemptDialog.tsx",
            "components/surrogates/LogInterviewOutcomeDialog.tsx",
        ].map(readSource)

        for (const source of sources) {
            expect(source).not.toContain("useMemo")
            expect(source).not.toContain("useCallback")
            expect(source).not.toContain("React.useMemo")
            expect(source).not.toContain("React.useCallback")
            expect(source).not.toContain("memo(")
        }
    })

    it("uses reducer state for the contact attempt form", () => {
        const source = readSource("components/surrogates/LogContactAttemptDialog.tsx")

        expect(source).toContain("useReducer")
        expect(source).toContain("contactAttemptFormReducer")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("setSelectedMethods")
        expect(source).not.toContain("setOutcome")
        expect(source).not.toContain("setIsBackdating")
    })

    it("keeps the surrogates floating scrollbar free of manual React memoization", () => {
        const source = readSource("components/surrogates/SurrogatesFloatingScrollbar.tsx")
        const controllerSource = readFunctionSource(
            source,
            "useSurrogatesFloatingScrollbarController"
        )

        expect(source).toContain("useState(detectPointerCapability)")
        expect(source).toContain("function useFloatingScrollbarDomLifecycle(")
        expect(source).toContain("function useFloatingScrollbarActivationSync(")
        expect(controllerSource).toContain("useFloatingScrollbarDomLifecycle({")
        expect(controllerSource).toContain("useFloatingScrollbarActivationSync({")
        expect(controllerSource).not.toContain("useEffect(() =>")
        expect(source).not.toContain("const [isDesktopPointer, setIsDesktopPointer] = useState(false)")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
    })

    it("keeps the surrogates floating scrollbar rendering split from scroll orchestration", () => {
        const source = readSource("components/surrogates/SurrogatesFloatingScrollbar.tsx")
        const scrollbarSource = readFunctionSource(source, "SurrogatesFloatingScrollbar")

        expect(source).toContain("function FloatingScrollbarPortal")
        expect(source).toContain("function FloatingScrollbarShell")
        expect(source).toContain("function FloatingScrollbarTrack")
        expect(scrollbarSource).not.toContain("data-testid=\"surrogates-floating-scrollbar\"")
        expect(scrollbarSource).not.toContain("surrogates-floating-scrollbar-viewport")
    })

    it("keeps automation form settings panel sections split into focused helpers", () => {
        const source = readSource("components/forms/builder/AutomationFormSettingsPanel.tsx")
        const panelSource = readFunctionSource(source, "AutomationFormSettingsPanel")

        expect(source).toContain("function FormIdentitySection")
        expect(source).toContain("function LogoSettingsSection")
        expect(source).toContain("function SharedDeliverySection")
        expect(source).toContain("function PublicHeaderSection")
        expect(source).toContain("function ShareQrSection")
        expect(source).toContain("function UploadRulesSection")
        expect(panelSource).not.toContain("Public Form Title & Subtitle")
        expect(panelSource).not.toContain("Share & QR")
        expect(panelSource).not.toContain("Allowed MIME types")
    })

    it("keeps surrogate detail header context files free of manual React memoization", () => {
        const sources = [
            "components/surrogates/detail/SurrogateDetailContext.tsx",
            "components/surrogates/detail/SurrogateDetailHeader.tsx",
        ].map(readSource)

        for (const source of sources) {
            expect(source).not.toContain("useMemo")
            expect(source).not.toContain("useCallback")
            expect(source).not.toContain("React.useMemo")
            expect(source).not.toContain("React.useCallback")
        }
    })

    it("uses immutable sorting in unified calendar derived lists", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")

        expect(source).toContain(".toSorted((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))")
        expect(source).toContain(".toSorted((a, b) => {")
        expect(source).not.toContain(".sort((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))")
        expect(source).not.toContain(".sort((a, b) => {")
    })

    it("keeps unified calendar manual memoization out of React Compiler output", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")

        expect(source).not.toContain("memo(function")
        expect(source).not.toContain("useMemo(")
        expect(source).not.toContain("useCallback(")
        expect(source).not.toContain("React.useMemo(")
        expect(source).not.toContain("React.useCallback(")
        expect(source).toContain("function TaskItem(")
        expect(source).toContain("function GoogleEventItem(")
        expect(source).toContain("function EventItem(")
        expect(source).toContain("const clientDateFormatter = Intl.DateTimeFormat(")
        expect(source).toContain("const clientTimeFormatter = Intl.DateTimeFormat(")
    })

    it("keeps unified calendar shell rendering split into focused helpers", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")
        const calendarSource = readExportedFunctionSource(source, "UnifiedCalendar")

        expect(source).toContain("function UnifiedCalendarHeader")
        expect(source).toContain("function UnifiedCalendarLoadingState")
        expect(source).toContain("function GoogleCalendarDisconnectedAlert")
        expect(source).toContain("function UnifiedCalendarViewContent")
        expect(source).toContain("function UnifiedCalendarLegend")
        expect(source).toContain("function UnifiedCalendarDialogs")
        expect(calendarSource).toContain("useUnifiedCalendarData({")
        expect(calendarSource).toContain("const navigate =")
        expect(calendarSource).toContain("const handleDragStart =")
        expect(calendarSource).toContain("const handleDrop =")
        expect(calendarSource).toContain("appointmentDetailDialogKey")
        expect(calendarSource).not.toContain("Previous period")
        expect(calendarSource).not.toContain("Google Calendar not connected")
        expect(calendarSource).not.toContain("Drag pending or confirmed appointments")
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

    it("keeps unified calendar appointment detail rendering split into focused helpers", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")
        const dialogSource = readFunctionSource(source, "AppointmentDetailDialog")

        expect(source).toContain("function AppointmentStatusPill")
        expect(source).toContain("function AppointmentClientSummary")
        expect(source).toContain("function AppointmentScheduleSummary")
        expect(source).toContain("function AppointmentFormatSummary")
        expect(source).toContain("function AppointmentLinkSection")
        expect(source).toContain("function AppointmentOutcomeAction")
        expect(source).toContain("function getSurrogateSelectLabel")
        expect(source).toContain("function getIntendedParentSelectLabel")
        expect(dialogSource).toContain("useUpdateAppointmentLink()")
        expect(dialogSource).toContain("useEffectivePermissions(")
        expect(dialogSource).toContain("const handleSaveLink =")
        expect(dialogSource).toContain("setLogOutcomeOpen")
        expect(dialogSource).not.toContain("Client timezone:")
        expect(dialogSource).not.toContain("Linked To")
        expect(dialogSource).not.toContain("Log Interview Outcome")
    })

    it("keeps appointment detail dialog state and rendering split", () => {
        const source = readSource("components/appointments/AppointmentsList.tsx")
        const dialogIndex = source.indexOf("export function AppointmentDetailDialog(")
        const firstHelperIndex = source.indexOf("function AppointmentStatusSummary")
        const dialogSource = source.slice(
            dialogIndex,
            firstHelperIndex > dialogIndex ? firstHelperIndex : undefined
        )

        expect(dialogIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function appointmentDetailDialogReducer")
        expect(source).toContain("function AppointmentStatusSummary")
        expect(source).toContain("function AppointmentClientInfo")
        expect(source).toContain("function AppointmentRescheduleForm")
        expect(source).toContain("function AppointmentDetailActions")
        expect(dialogSource).not.toContain("const [cancelReason")
        expect(dialogSource).not.toContain("const [showCancelForm")
        expect(dialogSource).not.toContain("const [showRescheduleForm")
        expect(dialogSource).not.toContain("Client Information")
        expect(dialogSource).not.toContain("Available Times")
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

    it("keeps form builder field settings tab reset render-derived", () => {
        const source = readSource("components/forms/builder/FormBuilderWorkspace.tsx")

        expect(source).toContain("type FieldSettingsTabState")
        expect(source).not.toContain("React.useEffect")
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain("React.useCallback")
        expect(source).not.toContain('setActiveTab("general")')
    })

    it("keeps form builder canvas field selection on native controls", () => {
        const source = readSource("components/forms/builder/FormBuilderWorkspace.tsx")

        expect(source).toContain('aria-label={`Select ${fieldLabel} field`}')
        expect(source).toContain('type="button"')
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("tabIndex={0}")
    })

    it("keeps self-service manage appointment timezone defaults render-derived", () => {
        const source = readSource("app/book/self-service/[orgId]/manage/[token]/page.tsx")

        expect(source).toContain("const hasManageLink = Boolean(orgId && token)")
        expect(source).toContain("subscribeTimezoneSnapshot")
        expect(source).toContain("timezoneOverride")
        expect(source).toContain("viewMonthOverride")
        expect(source).toContain("getTimezoneLabel")
        expect(source).not.toContain("setDetectedTimezone")
        expect(source).not.toContain("setViewMonth(startOfMonth")
        expect(source).not.toContain('error: "Invalid appointment management link"')
        expect(source).not.toContain("setTimezone(appointment.client_timezone)")
        expect(source).not.toContain("[appointment?.client_timezone]")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("<SelectValue />")
    })

    it("keeps self-service manage appointment rendering split into focused helpers", () => {
        const source = readSource("app/book/self-service/[orgId]/manage/[token]/page.tsx")
        const pageSource = readFunctionSource(source, "ManageAppointmentPage")

        expect(source).toContain("function ManageLoadingState")
        expect(source).toContain("function ManageErrorState")
        expect(source).toContain("function ManageSuccessState")
        expect(source).toContain("function AppointmentSummary")
        expect(source).toContain("function AppointmentActionToggle")
        expect(source).toContain("function ReschedulePanel")
        expect(source).toContain("function ManageCalendarGrid")
        expect(source).toContain("function ManageSlotsGrid")
        expect(source).toContain("function CancelPanel")
        expect(pageSource).not.toContain("Appointment Rescheduled")
        expect(pageSource).not.toContain("Select New Date")
        expect(pageSource).not.toContain("Cancel Appointment")
    })

    it("keeps form builder document hook compiler-derived", () => {
        const source = readSource("lib/forms/use-form-builder-document.ts")

        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
    })

    it("keeps template form builder hook compiler-derived", () => {
        const source = readSource("lib/forms/use-template-form-builder-page.ts")
        const stateSource = readSource("lib/forms/use-template-form-builder-state.ts")

        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toMatch(/\buseEffect\b/)
        expect(source).not.toContain("useRef<Promise<void>>(Promise.resolve())")
        expect(source).not.toContain("currentVersionRef")
        expect(source).not.toContain("templateIdRef")
        expect(source).not.toContain("hydratedFormRef")
        expect(source).toContain("templateData.id === formId")
        expect(stateSource).toContain("baselineTemplateKey: string | null")
        expect(stateSource).toContain("templateKey: string")
    })

    it("keeps automation form builder hook compiler-derived", () => {
        const source = readSource("lib/forms/use-automation-form-builder-page.ts")
        const stateSource = readSource("lib/forms/use-automation-form-builder-state.ts")

        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useDebouncedValue")
        expect(source).not.toMatch(/\buseEffect\b/)
        expect(source).toContain("formData.id === formId")
        expect(source).not.toContain("useEffect(() => {\n        resetForForm")
        expect(source).not.toContain(
            "useEffect(() => {\n        if (isNewForm || !formData"
        )
        expect(source).not.toContain("hydratedFormRef")
        expect(source).not.toContain("orgLogoInitRef")
        expect(stateSource).toContain("baselineFormKey: string | null")
        expect(stateSource).toContain("formKey: string")
        expect(stateSource).toContain("buildInitialState(action.payload.formKey")
    })

    it("keeps form builder state hooks compiler-derived", () => {
        const templateSource = readSource("lib/forms/use-template-form-builder-state.ts")
        const automationSource = readSource("lib/forms/use-automation-form-builder-state.ts")

        expect(templateSource).not.toContain("useCallback")
        expect(automationSource).not.toContain("useCallback")
    })

    it("keeps surrogate card, task calendar, and CSV derived lists single pass", () => {
        const medicalInsuranceSource = readSource("components/surrogates/CombinedMedicalInsuranceCard.tsx")
        const taskCalendarSource = readSource("components/surrogates/SurrogateTasksCalendar.tsx")
        const taskViewModeSource = readSource("components/surrogates/use-surrogate-task-view-mode.ts")
        const csvUploadSource = readSource("components/import/CSVUpload.tsx")
        const metaMappingSource = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")

        expect(medicalInsuranceSource).not.toContain("finally")
        expect(medicalInsuranceSource).not.toContain("useEffect")
        expect(medicalInsuranceSource).not.toContain("useMemo")
        expect(medicalInsuranceSource).not.toMatch(/SECTION_CONFIGS\.filter\([\s\S]*?\)\.map\(/)
        expect(medicalInsuranceSource).not.toMatch(/SECTION_CONFIGS\.filter\([\s\S]*?\)\s*\.filter\(/)
        expect(taskCalendarSource).toContain("const taskGroups = buildTaskGroups(tasks)")
        expect(taskCalendarSource).not.toContain("useMemo")
        expect(taskViewModeSource).toContain("useSyncExternalStore")
        expect(taskViewModeSource).not.toContain("useEffect")
        expect(taskCalendarSource).not.toContain("tasks.filter(t => t.is_completed).map")
        expect(csvUploadSource).not.toMatch(/const unmatched = mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
        expect(csvUploadSource).not.toMatch(/new Set\(\s*mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
        expect(metaMappingSource).not.toMatch(/const unmatched = mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
        expect(metaMappingSource).not.toMatch(/new Set\(\s*mappings\s*\.filter\([\s\S]*?\)\s*\.map\(/)
    })

    it("uses Sets for platform template variable validation membership checks", () => {
        const systemTemplateNewSource = readSource("app/ops/templates/system/new/page.client.tsx")
        const systemTemplateDetailSource = readSource("app/ops/templates/system/[systemKey]/page.client.tsx")

        expect(systemTemplateNewSource).toContain("const usedVariableNamesSet = new Set(usedVariableNames)")
        expect(systemTemplateNewSource).not.toContain("usedVariableNames.includes(")
        expect(systemTemplateDetailSource).toContain("const usedVariableNamesSet = new Set(usedVariableNames)")
        expect(systemTemplateDetailSource).toContain("!usedVariableNamesSet.has(variable)")
        expect(systemTemplateDetailSource).not.toContain("requiredVariableNames.filter((variable) => !usedVariableNames.includes(variable))")
    })

    it("keeps platform system template creation rendering split into sections", () => {
        const source = readSource("app/ops/templates/system/new/page.client.tsx")
        const pageIndex = source.indexOf("export default function PlatformSystemEmailTemplateNewPage()")
        const firstHelperIndex = source.indexOf("function TemplateCreateHeader")
        const pageSource = source.slice(
            pageIndex,
            firstHelperIndex > pageIndex ? firstHelperIndex : undefined
        )

        expect(pageIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function TemplateCreateHeader")
        expect(source).toContain("function TemplateSettingsCard")
        expect(source).toContain("function TemplateContentCard")
        expect(source).toContain("function TemplateVariableWarnings")
        expect(source).toContain("function TemplatePreviewCard")
        expect(pageSource).not.toContain("Template settings")
        expect(pageSource).not.toContain("Template content")
        expect(pageSource).not.toContain("Rendered using sample values")
        expect(pageSource).not.toContain("Unknown:")
    })

    it("keeps surrogate medical section visibility in render state", () => {
        const source = readSource("components/surrogates/CombinedMedicalInsuranceCard.tsx")

        expect(source).toContain("const [manuallyAdded, setManuallyAdded] = useState<SectionType[]>([])")
        expect(source).toContain("const [optimisticallyHiddenSections, setOptimisticallyHiddenSections] = useState<OptimisticallyHiddenSection[]>([])")
        expect(source).toContain("const visibleKeys = new Set([...sectionsWithData, ...manuallyAdded])")
        expect(source).toContain("for (const entry of optimisticallyHiddenSections)")
        expect(source).not.toContain("optimisticallyHiddenSectionsRef")
    })

    it("keeps CSV upload handlers and dropzone compiler-friendly", () => {
        const source = readSource("components/import/CSVUpload.tsx")

        expect(source).toContain("function resolveErrorDetail(error: unknown, fallback: string)")
        expect(source).toContain('aria-label="Upload CSV or TSV file"')
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("const resolveErrorDetail =")
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

    it("keeps activity timelines free of manual React memoization", () => {
        const surrogateTimelineSource = readSource("components/surrogates/ActivityTimeline.tsx")
        const intendedParentTimelineSource = readSource("components/intended-parents/IntendedParentActivityTimeline.tsx")

        for (const source of [surrogateTimelineSource, intendedParentTimelineSource]) {
            expect(source).not.toContain("useMemo")
            expect(source).not.toContain("memo(")
            expect(source).not.toContain("React.useMemo")
            expect(source).not.toContain("React.memo")
        }
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
        expect(source).not.toContain("useRequireAuth")
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

    it("keeps campaign detail edit draft state grouped", () => {
        const source = readSource("app/(app)/automation/campaigns/[id]/page.client.tsx")
        const pageSource = readFunctionSource(source, "CampaignDetailPage")

        expect(source).toContain("type CampaignEditDraftState")
        expect(source).toContain("function campaignEditDraftReducer")
        expect(pageSource).toContain("const [editDraft, dispatchEditDraft] = useReducer")
        expect(pageSource).toContain(
            "const [handledAutoEditRequest, setHandledAutoEditRequest] = useState<string | null>(null)"
        )
        expect(pageSource).toContain(
            "handledAutoEditRequest !== autoEditRequestKey"
        )
        expect(pageSource).not.toContain("useEffect")
        expect(pageSource).not.toContain("startTransition")
        expect(pageSource).not.toContain("setEditName")
        expect(pageSource).not.toContain("setEditDescription")
        expect(pageSource).not.toContain("setEditTemplateId")
        expect(pageSource).not.toContain("setEditRecipientType")
        expect(pageSource).not.toContain("setEditStages")
        expect(pageSource).not.toContain("setEditStates")
        expect(pageSource).not.toContain("setEditIncludeUnsubscribed")
        expect(pageSource).not.toContain("setEditScheduledAt")
    })

    it("keeps campaign detail rendering split into focused sections", () => {
        const source = readSource("app/(app)/automation/campaigns/[id]/page.client.tsx")
        const pageSource = readFunctionSource(source, "CampaignDetailPage")

        expect(source).toContain("function CampaignDetailHeader")
        expect(source).toContain("function CampaignStatsGrid")
        expect(source).toContain("function CampaignFilterSummaryCard")
        expect(source).toContain("function CampaignTemplatePreviewCard")
        expect(source).toContain("function CampaignRecipientsCard")
        expect(source).toContain("function CampaignEditDialog")
        expect(source).toContain("function CampaignConfirmationDialogs")
        expect(pageSource).toContain("<CampaignDetailHeader")
        expect(pageSource).toContain("<CampaignStatsGrid")
        expect(pageSource).toContain("<CampaignFilterSummaryCard")
        expect(pageSource).toContain("<CampaignTemplatePreviewCard")
        expect(pageSource).toContain("<CampaignRecipientsCard")
        expect(pageSource).toContain("<CampaignEditDialog")
        expect(pageSource).toContain("<CampaignConfirmationDialogs")
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

    it("keeps remaining pure render helpers at module scope", () => {
        const attentionSource = readSource("app/(app)/dashboard/components/attention-needed-panel.tsx")
        const matchDetailSource = readSource("app/(app)/intended-parents/matches/[id]/page.client.tsx")
        const loginSource = readSource("app/login/LoginPageClient.tsx")
        const opsLayoutSource = readSource("app/ops/layout.tsx")
        const appointmentSettingsSource = readSource("components/appointments/AppointmentSettings.tsx")
        const agencyInvitesSource = readSource("components/ops/agencies/AgencyInvitesTab.tsx")
        const sessionExpiredSource = readSource("components/session-expired-dialog.tsx")
        const notesSource = readSource("components/surrogates/tabs/SurrogateNotesTab.tsx")
        const toastSource = readSource("components/ui/toast.tsx")
        const versionHistorySource = readSource("components/version-history-modal.tsx")

        expect(attentionSource).toContain("function formatUpcomingItemTime")
        expect(attentionSource).not.toContain("const formatTime =")
        expect(matchDetailSource).toContain("function formatMatchDate")
        expect(matchDetailSource).toContain("function formatMatchDateTime")
        expect(matchDetailSource).not.toContain("const formatDate =")
        expect(matchDetailSource).not.toContain("const formatDateTime =")
        expect(loginSource).toContain("function getLoginReturnTo")
        expect(loginSource).not.toContain("const getReturnTo =")
        expect(opsLayoutSource).toContain("function redirectToOpsLogin")
        expect(opsLayoutSource).not.toContain("const handleLogout = async")
        expect(appointmentSettingsSource).toContain("function openBookingPreview")
        expect(appointmentSettingsSource).toContain("function getAppointmentTypeErrorMessage")
        expect(appointmentSettingsSource).not.toContain("const openPreview =")
        expect(appointmentSettingsSource).not.toContain("const getErrorMessage =")
        expect(agencyInvitesSource).toContain("function formatInviteCooldown")
        expect(agencyInvitesSource).not.toContain("const formatCooldown =")
        expect(sessionExpiredSource).toContain("function redirectToLogin")
        expect(sessionExpiredSource).not.toContain("const handleLogin =")
        expect(notesSource).toContain("function getNoteAuthorInitials")
        expect(notesSource).not.toContain("const getInitials =")
        expect(toastSource).toContain("function addToast")
        expect(toastSource).toContain("function ToastViewport")
        expect(versionHistorySource).toContain("function formatVersionHistoryDate")
        expect(versionHistorySource).not.toContain("const formatDate =")
    })

    it("contains session-expiration cache subscriptions in a named hook", () => {
        const dialogSource = readSource("components/session-expired-dialog.tsx")
        const hookSource = readSource("lib/hooks/use-session-expiration-detection.ts")

        expect(dialogSource).toContain("const isExpired = useSessionExpirationDetection()")
        expect(dialogSource).not.toContain("useEffect")
        expect(dialogSource).not.toContain("useQueryClient")
        expect(hookSource).toContain("getQueryCache().subscribe")
        expect(hookSource).toContain("getMutationCache().subscribe")
        expect(hookSource).toContain("unsubscribeQueries()")
        expect(hookSource).toContain("unsubscribeMutations()")
        expect(hookSource).toContain("}, [queryClient])")
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

    it("keeps Meta configuration account edit state grouped", () => {
        const source = readSource("app/(app)/settings/integrations/page.tsx")
        const sectionSource = readFunctionSource(source, "MetaConfigurationSection")

        expect(source).toContain("type MetaAccountEditState")
        expect(source).toContain("function metaAccountEditReducer")
        expect(sectionSource).toContain("const [accountEditState, dispatchAccountEdit] = useReducer")
        expect(sectionSource).not.toContain("setAccountFormError")
        expect(sectionSource).not.toContain("setAdAccountName")
        expect(sectionSource).not.toContain("setPixelId")
        expect(sectionSource).not.toContain("setCapiEnabled")
        expect(sectionSource).not.toContain("setAccountActive")
    })

    it("keeps AI chat message state compiler-friendly", () => {
        const source = readSource("components/ai/AIChatPanel.tsx")

        expect(source).toContain("type PanelMessageState")
        expect(source).toContain("function createConversationKey")
        expect(source).toContain("function createPanelMessageState")
        expect(source).toContain("function AIChatPanelContent")
        expect(source).toContain("const currentContext =")
        expect(source).toContain("<AIChatPanelContent key={contextKey}")
        expect(source).not.toContain("const [messages, setMessages]")
        expect(source).not.toContain("setMessages(")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("useEffect(() => {\n        if (isStreaming) return")
        expect(source).not.toContain("prevContextRef")
        expect(source).not.toContain("trackedContext")
        expect(source).not.toContain("useEffect(() => {\n        const prev =")
        expect(source).not.toContain("finally")
    })

    it("keeps AI chat panel rendering split into focused sections", () => {
        const source = readSource("components/ai/AIChatPanel.tsx")
        const panelSource = readFunctionSource(source, "AIChatPanel")

        expect(source).toContain("function AIChatHeader")
        expect(source).toContain("function AIChatContextBar")
        expect(source).toContain("function AIChatMessages")
        expect(source).toContain("function AIChatQuickActions")
        expect(source).toContain("function AIChatComposer")
        expect(source).toContain("function AIChatScheduleParser")
        expect(panelSource).not.toContain("AI Assistant")
        expect(panelSource).not.toContain("Ask anything")
        expect(panelSource).not.toContain("Parse Schedule")
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

    it("keeps reports page rendering split into focused sections", () => {
        const source = readSource("app/(app)/reports/page.tsx")
        const pageSource = readFunctionSource(source, "ReportsPage")

        expect(source).toContain("function ReportsPageHeader")
        expect(source).toContain("function ReportsQuickStatsGrid")
        expect(source).toContain("function ReportsAiSummaryCard")
        expect(source).toContain("function getPerformanceModeLabel")
        expect(pageSource).not.toContain("Total Surrogates")
        expect(pageSource).not.toContain("AI Summary")
        expect(source).not.toContain("<SelectValue />")
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

    it("uses Sets for Meta asset selection membership checks", () => {
        const source = readSource("app/(app)/settings/integrations/meta/page.client.tsx")
        const assetSelectionSource = readFunctionSource(source, "MetaAssetSelection")

        expect(assetSelectionSource).toContain("const selectedAdAccountIds = new Set(selectedAdAccounts)")
        expect(assetSelectionSource).toContain("const selectedPageIds = new Set(selectedPages)")
        expect(assetSelectionSource).toContain("selectedAdAccountIds.has(a.id)")
        expect(assetSelectionSource).toContain("selectedPageIds.has(p.id)")
        expect(assetSelectionSource).toContain("checked={selectedAdAccountIds.has(account.id)}")
        expect(assetSelectionSource).toContain("checked={selectedPageIds.has(page.id)}")
        expect(assetSelectionSource).not.toContain("selectedAdAccounts.includes(")
        expect(assetSelectionSource).not.toContain("selectedPages.includes(")
    })

    it("keeps Meta integration page state and rendering split into focused sections", () => {
        const source = readSource("app/(app)/settings/integrations/meta/page.client.tsx")
        const pageIndex = source.indexOf("export default function MetaIntegrationPage()")
        const firstHelperIndex = source.indexOf("function MetaIntegrationHeader")
        const pageSource = source.slice(
            pageIndex,
            firstHelperIndex > pageIndex ? firstHelperIndex : undefined
        )

        expect(pageIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function metaAccountEditReducer")
        expect(source).toContain("const [accountEditState, dispatchAccountEdit] = useReducer")
        expect(source).toContain("function MetaIntegrationHeader")
        expect(source).toContain("function MetaConnectionsCard")
        expect(source).toContain("function MetaConnectionAlerts")
        expect(source).toContain("function MetaAdAccountsCard")
        expect(source).toContain("function EditAdAccountDialog")
        expect(source).toContain("function DisconnectMetaConnectionDialog")
        expect(pageSource).not.toContain("setAdAccountName")
        expect(pageSource).not.toContain("setPixelId")
        expect(pageSource).not.toContain("Connections</CardTitle>")
        expect(pageSource).not.toContain("Ad Accounts</CardTitle>")
        expect(pageSource).not.toContain("Edit Ad Account")
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
        expect(source).toContain("INTELLIGENT_SUGGESTION_SETTINGS_QUERY_KEY")
        expect(source).toContain("INTELLIGENT_SUGGESTION_TEMPLATES_QUERY_KEY")
        expect(source).toContain("INTELLIGENT_SUGGESTION_RULES_QUERY_KEY")
        expect(source).toContain("staleTime: INTELLIGENT_SUGGESTIONS_STALE_TIME_MS")
        expect(source).not.toContain("window.setTimeout(() => void loadInitialSettings(), 0)")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
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
        expect(source).not.toContain("useMemo")
        expect(source).toContain("const groupedTasks: Record<DueCategory, TaskListItem[]> = {")
        expect(source).toContain("let selectedIncompleteCount = 0")
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

    it("keeps intended-parent matches list routing helpers compiler-friendly", () => {
        const source = readSource("app/(app)/intended-parents/matches/page.client.tsx")

        expect(source).toContain("function updateMatchListUrl(")
        expect(source).toContain("function formatMatchProposedDate(")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("const formatDate =")
    })

    it("keeps intended-parents list routing helpers compiler-friendly", () => {
        const source = readSource("app/(app)/intended-parents/page.client.tsx")

        expect(source).toContain("function updateIntendedParentListUrl(")
        expect(source).toContain("function formatIntendedParentCreatedDate(")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("const formatDate =")
    })

    it("keeps intended-parents list rendering split into focused helpers", () => {
        const source = readSource("app/(app)/intended-parents/page.client.tsx")
        const pageIndex = source.indexOf("export default function IntendedParentsPage")
        const pageSource = source.slice(pageIndex)

        expect(pageIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function IntendedParentsPageHeader")
        expect(source).toContain("function IntendedParentStatsGrid")
        expect(source).toContain("function IntendedParentsFilters")
        expect(source).toContain("function IntendedParentsTableCard")
        expect(source).toContain("function IntendedParentsPagination")
        expect(source).toContain("function CreateIntendedParentDialog")
        expect(pageSource).toContain("useIntendedParents(filters)")
        expect(pageSource).toContain("const handleSearchChange =")
        expect(pageSource).toContain("const handleCreate =")
        expect(pageSource).not.toContain("No intended parents found")
        expect(pageSource).not.toContain("Failed to load intended parents")
        expect(pageSource).not.toContain("New Intended Parent")
    })

    it("keeps match-detail tab state routing helpers compiler-friendly", () => {
        const source = readSource("app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabState.ts")

        expect(source).toContain("function updateMatchDetailTabUrl(")
        expect(source).not.toContain("useCallback")
    })

    it("keeps match-detail tab data derivations compiler-friendly", () => {
        const source = readSource("app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabData.ts")

        expect(source).not.toContain("useMemo")
    })

    it("keeps top-level matches dialog derivations compiler-friendly", () => {
        const source = readSource("app/(app)/matches/page.tsx")

        expect(source).not.toContain("useMemo")
    })

    it("keeps intended-parent match proposal derivations compiler-friendly", () => {
        const source = readSource("components/matches/ProposeMatchFromIPDialog.tsx")

        expect(source).not.toContain("useMemo")
    })

    it("keeps search page key handling compiler-friendly", () => {
        const source = readSource("app/(app)/search/page.tsx")

        expect(source).not.toContain("useCallback")
    })

    it("keeps settings derived maps compiler-friendly", () => {
        const complianceSource = readSource("app/(app)/settings/compliance/page.tsx")
        const metaFormMappingSource = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")
        const roleDetailSource = readSource("app/(app)/settings/team/roles/[role]/page.client.tsx")

        expect(complianceSource).not.toContain("useMemo")
        expect(metaFormMappingSource).not.toContain("useMemo")
        expect(roleDetailSource).not.toContain("useMemo")
    })

    it("keeps Meta form mapping drafts as explicit per-column overrides", () => {
        const source = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")

        expect(source).toContain("const [mappingOverrides, setMappingOverrides]")
        expect(source).toContain("const serverMappingState =")
        expect(source).toContain("mappingOverrides[mapping.csv_column] ?? mapping")
        expect(source).toContain("const touchedColumns = new Set(serverMappingState.touchedColumns)")
        expect(source).not.toContain("touchedColumnsRef")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("useRef")
    })

    it("keeps Meta form mapping page rendering split into focused helpers", () => {
        const source = readSource("app/(app)/settings/integrations/meta/forms/[id]/page.tsx")
        const pageSource = readFunctionSource(source, "MetaFormMappingPage")

        expect(source).toContain("function MetaFormMappingHeader")
        expect(source).toContain("function MetaMappingOutdatedAlert")
        expect(source).toContain("function MetaColumnMappingCard")
        expect(source).toContain("function MetaColumnMappingRow")
        expect(source).toContain("function MetaMappingPreviewCard")
        expect(source).toContain("function MetaMappingActions")
        expect(source).toContain("function MetaUnconvertedLeadsCard")
        expect(source).toContain("function MetaUnconvertedLeadsTable")
        expect(pageSource).not.toContain("Column Mapping")
        expect(pageSource).not.toContain("<CardTitle>Preview</CardTitle>")
        expect(pageSource).not.toContain("Live lead samples")
        expect(pageSource).not.toContain("Unconverted Leads")
        expect(pageSource).not.toContain("Reconversion queued")
    })

    it("keeps audit settings export derivations compiler-friendly", () => {
        const source = readSource("app/(app)/settings/audit/page.tsx")

        expect(source).toContain("function isExportFormat(")
        expect(source).toContain("function isRedactMode(")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("const isExportFormat =")
        expect(source).not.toContain("const isRedactMode =")
    })

    it("keeps audit settings page sections split into focused helpers", () => {
        const source = readSource("app/(app)/settings/audit/page.tsx")
        const pageSource = readFunctionSource(source, "AuditLogPage")

        expect(source).toContain("function AuditPageHeader")
        expect(source).toContain("function AuditExportCard")
        expect(source).toContain("function AuditActivityCard")
        expect(source).toContain("function AuditLogEntriesList")
        expect(source).toContain("function AuditPagination")
        expect(pageSource).not.toContain("Export Audit Logs")
        expect(pageSource).not.toContain("AI Activity")
        expect(pageSource).not.toContain("No audit log entries found")
    })

    it("keeps compliance settings page sections split into focused helpers", () => {
        const source = readSource("app/(app)/settings/compliance/page.tsx")
        const pageSource = readFunctionSource(source, "ComplianceSettingsPage")

        expect(source).toContain("function CompliancePageHeader")
        expect(source).toContain("function RetentionPoliciesCard")
        expect(source).toContain("function LegalHoldsCard")
        expect(source).toContain("function RetentionPurgeCard")
        expect(pageSource).not.toContain("Data Retention Policies")
        expect(pageSource).not.toContain("Legal Holds")
        expect(pageSource).not.toContain("Retention Purge")
    })

    it("keeps Meta asset selection derivations compiler-friendly", () => {
        const source = readSource("app/(app)/settings/integrations/meta/page.client.tsx")

        expect(source).not.toContain("useMemo")
    })

    it("keeps tickets list filters compiler-friendly", () => {
        const source = readSource("app/(app)/tickets/page.tsx")

        expect(source).not.toContain("useMemo")
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

    it("keeps ticket detail page rendering split into focused sections", () => {
        const source = readSource("app/(app)/tickets/[ticketId]/page.tsx")
        const pageIndex = source.indexOf("export default function TicketDetailPage()")
        const firstHelperIndex = source.indexOf("function TicketOverviewCard")
        const pageSource = source.slice(
            pageIndex,
            firstHelperIndex > pageIndex ? firstHelperIndex : undefined
        )

        expect(pageIndex).toBeGreaterThanOrEqual(0)
        expect(source).toContain("function TicketOverviewCard")
        expect(source).toContain("function TicketReplyCard")
        expect(source).toContain("function TicketNotesCard")
        expect(source).toContain("function TicketMessagesCard")
        expect(pageSource).not.toContain("Internal Notes")
        expect(pageSource).not.toContain("<CardTitle>Messages</CardTitle>")
        expect(pageSource).not.toContain("message.attachments.map")
        expect(pageSource).not.toContain("Surrogate ID (manual link)")
        expect(pageSource).not.toContain("Write your reply")
    })

    it("keeps publish dialog state reset and derivations compiler-friendly", () => {
        const source = readSource("components/ops/templates/PublishDialog.tsx")

        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("setMode(")
        expect(source).not.toContain("setSelectedOrgIds(")
        expect(source).not.toContain("setSearch(")
    })

    it("keeps ops templates landing rows compiler-derived", () => {
        const source = readSource("app/ops/templates/page.client.tsx")

        expect(source).toContain("const emailRows = emailTemplates")
        expect(source).toContain("const formRows = formTemplates")
        expect(source).toContain("const workflowRows = workflowTemplates")
        expect(source).toContain("const systemRows = systemTemplates")
        expect(source).not.toContain("useMemo")
    })

    it("keeps ops alert actions compiler-compatible", () => {
        const source = readSource("app/ops/alerts/page.client.tsx")

        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("finally")
    })

    it("keeps smaller ops pages compiler-compatible", () => {
        const opsDashboardSource = readSource("app/ops/page.client.tsx")
        const agenciesSource = readSource("app/ops/agencies/page.client.tsx")
        const newAgencySource = readSource("app/ops/agencies/new/page.client.tsx")

        expect(opsDashboardSource).not.toContain("finally")
        expect(agenciesSource).toContain("const agenciesQuery = useQuery({")
        expect(agenciesSource).toContain("'platform',")
        expect(agenciesSource).toContain("const data = await listOrganizations")
        expect(agenciesSource).not.toContain("if (!isCurrent) return")
        expect(agenciesSource).not.toContain("async function fetchAgencies")
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
        const unassignedContentIndex = unassignedSource.indexOf(
            "function UnassignedSurrogatesContent("
        )
        const unassignedAuthorizationSource = unassignedSource.slice(0, unassignedContentIndex)

        expect(appLinkSource).toContain("const { push, replace: replaceRoute } = useRouter()")
        expect(appLinkSource).toContain("replaceRoute(targetHref")
        expect(appLinkSource).toContain("push(targetHref")
        expect(opsLayoutSource).toContain("queryKey: ['platform', 'me']")
        expect(opsLayoutSource).toContain("queryKey: ['platform', 'stats']")
        expect(opsLayoutSource).toContain("redirect(getOpsAccessRedirect(platformMeQuery.error))")
        expect(opsLayoutSource).not.toContain("useEffect")
        expect(opsLayoutSource).not.toContain("useReducer")
        expect(opsLayoutSource).not.toContain("useRouter")
        expect(newAgencySource).toContain("const { push } = useRouter()")
        expect(newAgencySource).toContain("push(`/ops/agencies/${result.org.id}`)")
        expect(newAgencySource).toContain("push('/ops/agencies')")
        expect(welcomeSource).toContain("const { push } = useRouter()")
        expect(welcomeSource).toContain('push("/dashboard")')
        expect(welcomeSource).toContain('redirect("/dashboard")')
        expect(welcomeSource).not.toContain("useEffect")
        expect(welcomeSource).not.toContain("replace(")
        expect(ticketsSource).toContain("const { push } = useRouter()")
        expect(ticketsSource).toContain("push(`/tickets/${result.ticket_id}`)")
        expect(unassignedSource).toContain("const { push, replace } = useRouter()")
        expect(unassignedPageSource).toContain("searchParams: Promise<Record<string, SearchParamValue>>")
        expect(unassignedSource).toContain("initialSearchParams")
        expect(unassignedSource).toContain('redirect("/surrogates")')
        expect(unassignedAuthorizationSource).not.toContain("useUnassignedQueue(")
        expect(unassignedAuthorizationSource).not.toContain("useClaimSurrogate(")
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
        const focusNavigationSource = readSource("lib/hooks/use-task-focus-navigation.ts")

        expect(source).toContain("const [manualViewFocusTarget, setManualViewFocusTarget] = useState<FocusTarget | null>(null)")
        expect(source).toContain("const activeView = shouldUseListViewForFocus ? \"list\" : view")
        expect(source).toContain("useTaskFocusNavigation({")
        expect(source).not.toContain("handledFocusRef")
        expect(focusNavigationSource).toContain(
            "const handledFocusRef = useRef<TaskFocusTarget | null>(null)"
        )
        expect(focusNavigationSource).toContain("handledFocusRef.current === focusTarget")
        expect(focusNavigationSource).toContain("handledFocusRef.current = focusTarget")
        expect(source).not.toContain("const [pendingFocus, setPendingFocus]")
        expect(source).not.toContain("const pendingFocus =")
        expect(source).not.toContain("setPendingFocus(")
        expect(source).not.toContain("setView(\"list\")")
        expect(source).not.toContain("if (view === \"calendar\")")
    })

    it("keeps Tasks page handlers compiler-friendly", () => {
        const source = readSource("app/(app)/tasks/page.client.tsx")

        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
    })

    it("keeps Tasks page selection owned by visible rows and scope events", () => {
        const source = readSource("app/(app)/tasks/page.client.tsx")

        expect(source).not.toMatch(/\buseEffect\b/)
        expect(source).toContain("setSelectedTaskIds(new Set())\n        setFilter(newFilter)")
        expect(source).toContain("const visibleSelectedTaskIds = new Set<string>()")
        expect(source).toContain("const taskIds = Array.from(visibleSelectedTaskIds)")
        expect(source).toContain("selectedTaskIds: visibleSelectedTaskIds")
    })

    it("keeps Tasks page rendering split from the controller hook", () => {
        const source = readSource("app/(app)/tasks/page.client.tsx")
        const pageSource = readFunctionSource(source, "TasksPage")

        expect(source).toContain("function useTasksPageController")
        expect(source).toContain("function TasksPageHeader")
        expect(source).toContain("function TasksPageControls")
        expect(source).toContain("function TasksPageContent")
        expect(source).toContain("function TasksPageDialogs")
        expect(pageSource).not.toContain("useTasks(")
        expect(pageSource).not.toContain("Manage your tasks and appointments")
    })

    it("keeps platform email-template edit page helpers compiler-friendly", () => {
        const source = readSource("app/ops/templates/email/[id]/page.client.tsx")

        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("const applyTextInsertion =")
        expect(source).toContain("const usedVariableNamesSet = new Set(usedVariableNames)")
        expect(source).toContain("!usedVariableNamesSet.has(variable)")
        expect(source).toContain('testHasUnsubscribeUrl = usedVariableNames.includes("unsubscribe_url")')
        expect(source).not.toContain("requiredVariableNames.filter((variable) => !usedVariableNames.includes(variable))")
    })

    it("keeps shared display and navigation components compiler-friendly", () => {
        const sources = [
            readSource("components/FileUploadZone.tsx"),
            readSource("components/ai/AssistantRichText.tsx"),
            readSource("components/app-link.tsx"),
            readSource("components/charts/funnel-chart.tsx"),
            readSource("components/charts/us-map-chart.tsx"),
        ]

        for (const source of sources) {
            expect(source).not.toContain("useCallback")
            expect(source).not.toContain("React.useCallback")
            expect(source).not.toContain("useMemo")
            expect(source).not.toContain("React.useMemo")
        }
    })

    it("keeps form builder and template variable display helpers compiler-friendly", () => {
        const sources = [
            readSource("components/email/TemplateVariablePicker.tsx"),
            readSource("components/forms/FormBuilderPalette.tsx"),
            readSource("components/forms/builder/FieldLibrarySheet.tsx"),
            readSource("components/forms/builder/FormBuilderCanvasPreview.tsx"),
        ]

        for (const source of sources) {
            expect(source).not.toContain("useMemo")
            expect(source).not.toContain("React.useMemo")
        }
    })

    it("uses native navigation semantics for form builder category filters", () => {
        const source = readSource("components/forms/FormBuilderPalette.tsx")

        expect(source).toContain('<nav className="space-y-1 p-2.5" aria-label="Field categories">')
        expect(source).not.toContain('role="group"')
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

        expect(emailTemplatesSource).not.toContain("useMemo")
        expect(emailTemplatesSource).not.toContain("useCallback")
        expect(emailTemplatesSource).not.toContain("React.useMemo")
        expect(emailTemplatesSource).not.toContain("React.useCallback")
        expect(emailTemplatesSource).toContain("const requiredVariableNames: string[] = []")
        expect(emailTemplatesSource).toContain("for (const variable of templateVariables) {")
        expect(emailTemplatesSource).toContain("const usedVariableNamesSet = new Set(usedVariableNames)")
        expect(emailTemplatesSource).toContain("!usedVariableNamesSet.has(variable)")
        expect(emailTemplatesSource).toContain("function recordSelection")
        expect(emailTemplatesSource).toContain("function insertIntoTextControl")
        expect(emailTemplatesSource).toContain("async function handleCopySignatureHtml")
        expect(emailTemplatesSource).not.toContain("const handleCopySignatureHtml = async")
        expect(emailTemplatesSource).not.toContain("templateVariables.filter((variable) => variable.required).map")
        expect(emailTemplatesSource).not.toContain("requiredVariableNames.filter((variable) => !usedVariableNames.includes(variable))")

        expect(aiBuilderSource).toContain("const requiredTemplateVariableNames: string[] = []")
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

        expect(pipelinesSource).not.toContain("useMemo")
        expect(pipelinesSource).toContain("const baselineDraft = buildDraft(pipeline, entityType)")
        expect(pipelinesSource).toContain("const baselineDraftFingerprint = baselineDraft ? stringifyDraft(baselineDraft) : null")
        expect(pipelinesSource).toContain("const remapped: string[] = []")
        expect(pipelinesSource).toContain("const neighborColors = new Set<string>()")
        expect(pipelinesSource).toContain("const mappedLabels: string[] = []")
        expect(pipelinesSource).toContain("const selectedLabels: string[] = []")
        expect(pipelinesSource).toContain("const nextStages: EditableStage[] = []")
        expect(pipelinesSource).not.toContain("useEffect")
        expect(pipelinesSource).not.toContain("startTransition")
        expect(pipelinesSource).not.toContain(".map((value) => (value === removedStageKey ? targetStageKey ?? null : value))")
        expect(pipelinesSource).not.toContain(".filter((stage) => milestone.mapped_stage_keys.includes(stage.stageKey))")
        expect(pipelinesSource).not.toContain(".map((activeStage) => activeStage.stage_key)\n                                        .filter")
        expect(pipelinesSource).not.toContain("current.stages\n                .filter")

        expect(surrogatesSource).toContain("key !== \"intelligent_any\" &&")
        expect(surrogatesSource).not.toContain("useCallback")
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
        expect(source).toContain("triggerConfig: normalizeTriggerConfigForUi(action.value, {}, [])")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("setTriggerConfig({ ...triggerConfig")
    })

    it("hydrates workflow template drafts by server revision instead of query identity", () => {
        const source = readSource("app/ops/templates/workflows/[id]/page.client.tsx")

        expect(source).toContain("hydratedTemplateKey: string | null")
        expect(source).toContain("`${templateData.id}:${templateData.updated_at}`")
        expect(source).toContain("editorState.hydratedTemplateKey !== templateKey")
        expect(source).not.toContain(
            "useEffect(() => {\n        if (!templateData || isNew) return\n        dispatchEditor({ type: \"hydrateDraft\""
        )
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
        expect(source).toContain("getStableKeyedItems(templateErrors, getWorkflowMessageKey)")
        expect(source).toContain("getStableKeyedItems(templateWarnings, getWorkflowMessageKey)")
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
        expect(source).toContain("href={event.html_link}")
        expect(source).toContain('target="_blank"')
        expect(source).toContain('rel="noopener noreferrer"')
        expect(source).toContain("Saving…")
        expect(source).not.toContain("border-l-4 border-purple-500")
        expect(source).not.toContain("border-l-4 border-slate-400")
        expect(source).not.toContain("const openGoogleCalendarEvent = () =>")
        expect(source).not.toContain("onClick={openGoogleCalendarEvent}")
        expect(source).not.toContain("const handleClick = () =>")
        expect(source).not.toContain("onClick={handleClick}")
        expect(source).not.toContain("Saving...")
    })

    it("keeps unified calendar drag payload out of render state", () => {
        const source = readSource("components/appointments/UnifiedCalendar.tsx")

        expect(source).toContain("const draggedAppointmentRef = useRef<AppointmentListItem | null>(null)")
        expect(source).toContain("draggedAppointmentRef.current = appointment")
        expect(source).toContain("const draggedAppointment = draggedAppointmentRef.current")
        expect(source).not.toContain("const [draggedAppointment, setDraggedAppointment]")
        expect(source).not.toContain("setDraggedAppointment(")
    })

    it("keeps AppSidebar state and nav rendering compiler-friendly", () => {
        const source = readSource("components/app-sidebar.tsx")

        expect(source).toContain("appSidebarReducer")
        expect(source).toContain("SidebarNavLink")
        expect(source).toContain("function getSectionsForPath")
        expect(source).toContain('{ type: "syncPathname"')
        expect(source).toContain("createInitialAppSidebarState")
        expect(source).toContain("isExpanded: readSidebarCookie()")
        expect(source).not.toMatch(/\buseEffect\(/)
        expect(source).not.toContain('dispatch({ type: "setExpanded", isExpanded: readSidebarCookie() })')
        expect(source).toContain('const activeTab = searchParams.get("tab")')
        expect(source).not.toContain("readCurrentTabParam")
        expect(source).not.toContain("setActiveTab")
        expect(source).not.toContain("renderNavLink")
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useState")
        expect(source).not.toContain("setAutomationOpen(true)")
        expect(source).not.toContain("setSettingsOpen(true)")
        expect(source).not.toContain("setTasksOpen(true)")
    })

    it("keeps search command handlers compiler-friendly", () => {
        const source = readSource("components/search-command.tsx")
        const hotkeySource = readSource("lib/hooks/use-search-hotkey.ts")

        expect(source).toContain('key={open ? "open" : "closed"}')
        expect(source).not.toContain("useEffect")
        expect(source).toContain('export { useSearchHotkey } from "@/lib/hooks/use-search-hotkey"')
        expect(hotkeySource).toContain("useEffectEvent")
        expect(hotkeySource).toContain('document.addEventListener("keydown", handleKeyDown)')
        expect(hotkeySource).toContain('document.removeEventListener("keydown", handleKeyDown)')
        expect(source).not.toContain("useCallback")
        expect(source).not.toContain("startTransition")
    })

    it("keeps workflow templates panel derivations and controls compiler-friendly", () => {
        const source = readSource("components/automation/workflow-templates-panel.tsx")
        const panelSource = readFunctionSource(source, "WorkflowTemplatesPanel")

        expect(source).toContain("const [selectedWorkflowScope, setSelectedWorkflowScope]")
        expect(source).toContain('aria-label="Enable workflow immediately"')
        expect(source).toContain("function WorkflowTemplatesHeader")
        expect(source).toContain("function TemplateCategoryFilter")
        expect(source).toContain("function TemplateSections")
        expect(source).toContain("function UseTemplateDialog")
        expect(panelSource).not.toContain("<DialogContent>")
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain("startTransition")
    })

    it("keeps pending interview comment quote styling subtle", () => {
        const source = readSource("components/surrogates/interviews/InterviewComments/PendingCommentInput.tsx")

        expect(source).not.toContain("border-l-")
        expect(source).not.toContain("Add your comment...")
    })

    it("keeps unused library helpers out of the public export surface", () => {
        const matchesSource = readSource("lib/api/matches.ts")
        const surrogateEmailApiSource = readSource("lib/api/surrogate-emails.ts")
        const surrogateEmailsSource = readSource("lib/hooks/use-surrogate-emails.ts")
        const ticketApiSource = readSource("lib/api/tickets.ts")
        const ticketsSource = readSource("lib/hooks/use-tickets.ts")
        const intendedParentStageSource = readSource("lib/intended-parent-stage-utils.ts")

        expect(matchesSource).not.toContain("export async function getMatchEvent")
        expect(matchesSource).not.toContain("export const EVENT_TYPE_COLORS")
        expect(matchesSource).not.toContain("export const PERSON_TYPE_COLORS")
        expect(surrogateEmailApiSource).not.toContain("export interface SurrogateEmailContactPatchPayload")
        expect(surrogateEmailApiSource).not.toContain("export function patchSurrogateEmailContact")
        expect(surrogateEmailsSource).not.toContain("export function usePatchSurrogateEmailContact")
        expect(ticketApiSource).not.toContain("interface TicketSendIdentity")
        expect(ticketApiSource).not.toContain("interface TicketSendIdentityResponse")
        expect(ticketApiSource).not.toContain("export function getTicketSendIdentities")
        expect(ticketsSource).not.toContain("identities: () =>")
        expect(ticketsSource).not.toContain("export function useTicketSendIdentities")
        expect(ticketsSource).toContain("export function usePatchTicket")
        expect(intendedParentStageSource).toContain("const DEFAULT_INTENDED_PARENT_STAGE_OPTIONS")
        expect(intendedParentStageSource).toContain("function getIntendedParentStageOptionByValue")
        expect(intendedParentStageSource).not.toContain("export const DEFAULT_INTENDED_PARENT_STAGE_OPTIONS")
        expect(intendedParentStageSource).not.toContain("export function getIntendedParentStageOptionByValue")
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

    it("keeps automation form submissions panel split into focused render helpers", () => {
        const source = readSource("components/forms/builder/AutomationFormSubmissionsPanel.tsx")
        const panelSource = readExportedFunctionSource(source, "AutomationFormSubmissionsPanel")

        expect(source).toContain("function SubmissionMetricsGrid")
        expect(source).toContain("function SubmissionReviewQueues")
        expect(source).toContain("function SubmissionHistoryCard")
        expect(source).toContain("function SubmissionCandidateReviewCard")
        expect(panelSource).not.toContain("Ambiguous Match Queue")
        expect(panelSource).not.toContain("Submission History")
    })

    it("keeps production date-time formatters compiler-compatible", () => {
        const unifiedCalendarSource = readSource("components/appointments/UnifiedCalendar.tsx")
        const publicBookingSource = readSource("components/appointments/PublicBookingPage.tsx")
        const activityTimelineSource = readSource("components/surrogates/ActivityTimeline.tsx")
        const aiStudioSource = readSource("app/(app)/ai-studio/page.tsx")
        const unassignedSource = readSource("app/(app)/surrogates/unassigned/page.client.tsx")
        const activityTimelineTestSource = readSource("tests/activity-timeline.test.tsx")
        const dateRangePickerTestSource = readSource("tests/date-range-picker.test.tsx")
        const dateKeysSource = readSource("lib/utils/date-keys.ts")
        const formattersSource = readSource("lib/formatters.ts")

        expect(unifiedCalendarSource).toContain("const clientDateFormatter = Intl.DateTimeFormat(")
        expect(unifiedCalendarSource).toContain("const clientTimeFormatter = Intl.DateTimeFormat(")
        expect(unifiedCalendarSource).not.toMatch(/new Intl\.DateTimeFormat/)
        expect(publicBookingSource).toContain("function useBookingDateTimeFormatters")
        expect(publicBookingSource).toContain("const timeFormatter = Intl.DateTimeFormat")
        expect(publicBookingSource).toContain("const dateFormatter = Intl.DateTimeFormat")
        expect(publicBookingSource).not.toContain("useMemo")
        expect(publicBookingSource).not.toContain("React.useMemo")
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
        expect(source).not.toContain("useMemo")
        expect(source).not.toContain("useCallback")
    })

    it("keeps InlineDateField draft state tied to edit lifecycle", () => {
        const source = readSource("components/inline-date-field.tsx")

        expect(source).toContain("inlineDateFieldReducer")
        expect(source).toContain('type: "startEdit"')
        expect(source).not.toContain("React.useMemo")
        expect(source).not.toContain('role="button"')
        expect(source).not.toMatch(/useEffect\(\(\) => \{\s*setEditValue\(value \|\| ""\)/)
    })

    it("keeps InlineEditField draft state tied to edit lifecycle", () => {
        const source = readSource("components/inline-edit-field.tsx")

        expect(source).toContain("inlineEditFieldReducer")
        expect(source).toContain('type: "startEdit"')
        expect(source).toContain('import { Button } from "@/components/ui/button"')
        expect(source).toContain('<Button unstyled')
        expect(source).toContain('type="button"')
        expect(source).not.toContain('<button')
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain("handleDisplayKeyDown")
        expect(source).not.toMatch(/useEffect\(\(\) => \{\s*setEditValue\(value \|\| ""\)/)
    })

    it("keeps React Doctor-reported select controls associated with visible labels", () => {
        const hostedIntakeSource = readSource("app/intake/[slug]/page.client.tsx")
        const publicFieldRendererSource = readSource("components/forms/PublicFormFieldRenderer.tsx")
        const intendedParentFieldsSource = readSource("components/intended-parents/IntendedParentFormFields.tsx")

        expect(hostedIntakeSource).toContain("const fieldInputId = `${field.key}-${rowIndex}-${column.key}`")
        expect(hostedIntakeSource).toContain("const fieldInputLabelId = `${fieldInputId}-label`")
        expect(hostedIntakeSource).toMatch(/<Label[\s\S]*?id=\{fieldInputLabelId\}[\s\S]*?htmlFor=\{fieldInputId\}/)
        expect(hostedIntakeSource).toMatch(/<SelectTrigger[\s\S]*?id=\{fieldInputId\}[\s\S]*?aria-labelledby=\{fieldInputLabelId\}/)

        expect(publicFieldRendererSource).toContain("const fieldInputId = `${field.key}-${rowKey}-${column.key}`")
        expect(publicFieldRendererSource).toContain("const fieldInputLabelId = `${fieldInputId}-label`")
        expect(publicFieldRendererSource).toMatch(/<Label[\s\S]*?htmlFor=\{fieldInputId\}/)
        expect(publicFieldRendererSource).toContain("ariaLabelledBy={fieldInputLabelId}")
        expect(publicFieldRendererSource).toMatch(/<SelectTrigger[\s\S]*?id=\{id\}[\s\S]*?aria-labelledby=\{ariaLabelledBy\}/)
        expect(publicFieldRendererSource).toContain("const selectedValueSet = new Set(selectedValues)")
        expect(publicFieldRendererSource).not.toContain("selectedValues.includes(")

        expect(intendedParentFieldsSource).toContain("const labelId = `${id}-label`")
        expect(intendedParentFieldsSource).toContain("<Label id={labelId} htmlFor={id}>{label}</Label>")
        expect(intendedParentFieldsSource).toMatch(/<SelectTrigger[\s\S]*?id=\{id\}[\s\S]*?aria-labelledby=\{labelId\}/)
    })

    it("keeps the interview transcript pane on a native labeled region", () => {
        const source = readSource("components/surrogates/interviews/InterviewComments/TranscriptPane.tsx")
        const interactionSource = readSource("lib/hooks/use-transcript-comment-interactions.ts")

        expect(source).toContain("<section")
        expect(source).toContain('aria-label="Interview Transcript"')
        expect(source).toContain("useTranscriptCommentInteractions({")
        expect(source).not.toContain("useEffect")
        expect(source).not.toContain('role="button"')
        expect(source).not.toContain('role="region"')
        expect(source).not.toContain("onClick={")
        expect(source).not.toContain("onKeyDown={")
        expect(interactionSource).toContain(
            "const setHoveredCommentIdEvent = useEffectEvent(setHoveredCommentId)"
        )
        expect(interactionSource).toContain('container.addEventListener("focusin", handleFocusIn)')
        expect(interactionSource).toContain('container.removeEventListener("keydown", handleKeyDown)')
    })

    it("delegates match detail tab rendering to a dedicated component", () => {
        const source = readSource("app/(app)/intended-parents/matches/[id]/page.client.tsx")

        expect(source).toContain('import { MatchDetailOverviewTabs } from "./components/MatchDetailOverviewTabs"')
        expect(source).toContain("<MatchDetailOverviewTabs")
        expect(source).not.toContain('variant={activeTab === "notes" ? "secondary" : "ghost"}')
    })

    it("keeps match detail page rendering split into focused helpers", () => {
        const source = readSource("app/(app)/intended-parents/matches/[id]/page.client.tsx")
        const pageSource = readFunctionSource(source, "MatchDetailPage")

        expect(source).toContain("function MatchDetailHeader")
        expect(source).toContain("function MatchDetailMainTabs")
        expect(source).toContain("function SurrogateProfileColumn")
        expect(source).toContain("function IntendedParentProfileColumn")
        expect(source).toContain("function MatchDetailDialogs")
        expect(source).toContain("function useMatchDetailRelatedData")
        expect(pageSource).toContain("useMatch(matchId)")
        expect(pageSource).toContain("useMatchDetailRelatedData(match, sourceFilter)")
        expect(pageSource).toContain("const handleAcceptMatch =")
        expect(pageSource).toContain("const handleAddTask =")
        expect(pageSource).not.toContain("useSurrogate(")
        expect(pageSource).not.toContain("useIntendedParent(")
        expect(pageSource).not.toContain("No surrogate data")
        expect(pageSource).not.toContain("No intended parent data")
        expect(pageSource).not.toContain("Accept Match")
        expect(pageSource).not.toContain("Reject Match Dialog")
    })
})
