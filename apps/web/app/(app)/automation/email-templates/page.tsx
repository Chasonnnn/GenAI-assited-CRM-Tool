"use client"

import * as React from "react"
import type { Route } from "next"
import NextImage from "next/image"
import { useRouter } from "next/navigation"
import { useState, useRef, useReducer } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    PlusIcon,
    TrashIcon,
    EyeIcon,
    CameraIcon,
    Loader2Icon,
    CodeIcon,
    XIcon,
    LinkIcon,
    CopyIcon,
    ShareIcon,
    UserIcon,
    BuildingIcon,
    LayoutTemplateIcon,
    AlertTriangleIcon,
    SearchIcon,
} from "lucide-react"
import {
    useEmailTemplates,
    useEmailTemplate,
    useUpdateEmailTemplate,
    useDeleteEmailTemplate,
    useCopyTemplateToPersonal,
    useShareTemplateWithOrg,
    useSendTestEmailTemplate,
    useEmailTemplateLibrary,
    useEmailTemplateLibraryItem,
    useCopyTemplateFromLibrary,
} from "@/lib/hooks/use-email-templates"
import {
    useDiscardEmailTemplateDraft,
    useEmailTemplateDrafts,
} from "@/lib/hooks/use-email-template-drafts"
import {
    useUserSignature,
    useUpdateUserSignature,
    useSignaturePreview,
    useUploadSignaturePhoto,
    useDeleteSignaturePhoto,
    useOrgSignaturePreview,
} from "@/lib/hooks/use-signature"
import { getSignaturePreview } from "@/lib/api/signature"
import type {
    EmailTemplateLibraryItem,
    EmailTemplateListItem,
} from "@/lib/api/email-templates"
import type {
    EmailTemplateDraft,
} from "@/lib/api/email-template-drafts"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import {
    buildEmailTemplatePreviewHtml,
    extractEmailTemplateVariables as extractTemplateVariables,
} from "@/lib/email-template-preview"
import { SafeHtmlContent } from "@/components/safe-html-content"
import { EmailTemplatesPageHeader } from "@/components/email/EmailTemplatesPageHeader"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { OrgSignaturePreview } from "@/components/email/OrgSignaturePreview"
import { SignaturePhotoField } from "@/components/email/SignaturePhotoField"
import { SignaturePreview } from "@/components/email/SignaturePreview"
import {
    TemplateCard,
    TemplateCardSubject,
    templateCardClassName,
    templateCardTitleClassName,
    type TemplateCardActionKind,
    type TemplateCardControls,
} from "@/components/email/TemplateCard"
import { TemplateDraftCard } from "@/components/email/TemplateDraftCard"
import { SendTestEmailDialog } from "@/components/email/SendTestEmailDialog"
import { getTemplateStudioHref } from "@/components/email/template-studio-route"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"

// =============================================================================
// Signature Override Field Component
// =============================================================================

interface SignatureOverrideFieldProps {
    id: string
    label: string
    value: string
    profileDefault: string | null
    onChange: (value: string) => void
    onClear: () => void
    placeholder?: string
    type?: string
}

function SignatureOverrideField({
    id,
    label,
    value,
    profileDefault,
    onChange,
    onClear,
    placeholder,
    type = "text",
}: SignatureOverrideFieldProps) {
    const hasOverride = value !== ""
    const displayPlaceholder = profileDefault
        ? `Defaults to: ${profileDefault}`
        : placeholder || `Enter ${label.toLowerCase()}`

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label htmlFor={id} className="text-sm font-medium">
                    {label}
                </Label>
                {hasOverride && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                        onClick={onClear}
                    >
                        <XIcon className="mr-1 size-3" />
                        Clear
                    </Button>
                )}
            </div>
            <Input
                id={id}
                type={type}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={displayPlaceholder}
                className={hasOverride ? "border-primary/50" : ""}
            />
            {!hasOverride && profileDefault && (
                <p className="text-xs text-muted-foreground">
                    Using profile: <span className="font-medium">{profileDefault}</span>
                </p>
            )}
            {hasOverride && (
                <p className="text-xs text-primary">
                    Custom signature value
                </p>
            )}
        </div>
    )
}

// =============================================================================
// Available template variables
// =============================================================================

type SignatureDraftState = {
    name: string
    title: string
    phone: string
    linkedin: string
    twitter: string
    instagram: string
}

type SignatureDraftField = keyof SignatureDraftState

type SignatureDraftAction =
    { type: "changeField"; field: SignatureDraftField; value: string }

type SignatureDraftOverrides = Partial<SignatureDraftState>

function createSignatureDraftState(
    signatureData: {
        signature_name?: string | null
        signature_title?: string | null
        signature_phone?: string | null
        signature_linkedin?: string | null
        signature_twitter?: string | null
        signature_instagram?: string | null
    } | null | undefined,
): SignatureDraftState {
    return {
        name: signatureData?.signature_name || "",
        title: signatureData?.signature_title || "",
        phone: signatureData?.signature_phone || "",
        linkedin: signatureData?.signature_linkedin || "",
        twitter: signatureData?.signature_twitter || "",
        instagram: signatureData?.signature_instagram || "",
    }
}

function signatureDraftReducer(
    state: SignatureDraftOverrides,
    action: SignatureDraftAction,
): SignatureDraftOverrides {
    switch (action.type) {
        case "changeField":
            return { ...state, [action.field]: action.value }
        default:
            return state
    }
}

type TestSendDialogState = {
    isOpen: boolean
    target: EmailTemplateListItem | null
    toEmail: string
    ignoreOptOut: boolean
    variables: Record<string, string>
    error: string | null
}

type TestSendDialogAction =
    | { type: "open"; target: EmailTemplateListItem; toEmail: string }
    | { type: "close" }
    | { type: "changeToEmail"; value: string }
    | { type: "changeIgnoreOptOut"; value: boolean }
    | { type: "changeVariable"; name: string; value: string }
    | { type: "setError"; value: string | null }

const initialTestSendDialogState: TestSendDialogState = {
    isOpen: false,
    target: null,
    toEmail: "",
    ignoreOptOut: false,
    variables: {},
    error: null,
}

function testSendDialogReducer(
    state: TestSendDialogState,
    action: TestSendDialogAction,
): TestSendDialogState {
    switch (action.type) {
        case "open":
            return {
                isOpen: true,
                target: action.target,
                toEmail: action.toEmail,
                ignoreOptOut: false,
                variables: {},
                error: null,
            }
        case "close":
            return initialTestSendDialogState
        case "changeToEmail":
            return { ...state, toEmail: action.value }
        case "changeIgnoreOptOut":
            return { ...state, ignoreOptOut: action.value }
        case "setError":
            return { ...state, error: action.value }
        case "changeVariable":
            return {
                ...state,
                variables: {
                    ...state.variables,
                    [action.name]: action.value,
                },
            }
        default:
            return state
    }
}

function createEmailTestOccurrenceId(): string {
    const cryptoApi = globalThis.crypto
    if (typeof cryptoApi?.randomUUID === "function") {
        return cryptoApi.randomUUID()
    }
    if (typeof cryptoApi?.getRandomValues !== "function") {
        throw new Error("Secure random UUID generation is unavailable")
    }
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16))
    bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40
    bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"))
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`
}

function buildTestVariableSample(
    variableName: string,
    context: {
        toEmail: string
        ownerName: string | null | undefined
        orgName: string | null | undefined
    }
): string {
    switch (variableName) {
        case "first_name":
            return "Jordan"
        case "full_name":
            return "Jordan Smith"
        case "email":
            return context.toEmail
        case "phone":
            return "(555) 555-5555"
        case "surrogate_number":
            return "S10001"
        case "intended_parent_number":
            return "I10001"
        case "donor_number":
            return "D10001"
        case "donor_type":
            return "Egg Donor"
        case "education":
            return "Bachelor's degree"
        case "status_label":
            return "Pre-Qualified"
        case "state":
            return "CA"
        case "owner_name":
            return context.ownerName || "Case Manager"
        case "form_link":
            return "https://app.surrogacyforce.com/intake/EXAMPLE_SLUG"
        case "appointment_link":
            return "https://app.surrogacyforce.com/book/EXAMPLE_APPOINTMENT_SLUG"
        case "appointment_manage_url":
            return "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/manage/EXAMPLE_TOKEN"
        case "appointment_reschedule_url":
            return "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/reschedule/EXAMPLE_TOKEN"
        case "appointment_cancel_url":
            return "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/cancel/EXAMPLE_TOKEN"
        case "appointment_date":
            return "2026-01-01"
        case "appointment_time":
            return "09:00"
        case "appointment_location":
            return "Zoom"
        case "org_name":
            return context.orgName || ""
        case "org_logo_url":
            return ""
        default:
            return `TEST_${variableName.toUpperCase()}`
    }
}

async function handleCopySignatureHtml() {
    try {
        const data = await getSignaturePreview()
        const html = data.html || ""

        try {
            await navigator.clipboard.writeText(html)
            toast.success("Signature HTML copied to clipboard!")
        } catch {
            const textarea = document.createElement("textarea")
            textarea.value = html
            document.body.appendChild(textarea)
            textarea.select()
            document.execCommand("copy")
            document.body.removeChild(textarea)
            toast.success("Signature HTML copied to clipboard!")
        }
    } catch (error) {
        console.error("Failed to copy signature:", error)
    }
}

// =============================================================================
// Template Card Component
// =============================================================================

const personalTemplateVisibilityLabels: Record<"mine" | "all", string> = {
    mine: "My Templates",
    all: "All Personal Templates",
}

function getPersonalTemplateVisibilityLabel(value: string | null) {
    return value === "all"
        ? personalTemplateVisibilityLabels.all
        : personalTemplateVisibilityLabels.mine
}

function matchesTemplateSearch(item: { name: string; subject: string }, search: string) {
    const query = search.trim().toLowerCase()
    return (
        !query ||
        item.name.toLowerCase().includes(query) ||
        item.subject.toLowerCase().includes(query)
    )
}

/**
 * Drafts of a listed template show as a chip on its card. The rest (unpublished,
 * or of a template hidden by a filter) render as their own cards.
 */
function splitTemplateDrafts(
    drafts: EmailTemplateDraft[],
    templates: EmailTemplateListItem[] | undefined,
) {
    const listedIds = new Set(templates?.map((template) => template.id))
    const draftByTemplateId = new Map<string, EmailTemplateDraft>()
    const standalone: EmailTemplateDraft[] = []
    for (const draft of drafts) {
        if (draft.template_id && listedIds.has(draft.template_id)) {
            draftByTemplateId.set(draft.template_id, draft)
        } else {
            standalone.push(draft)
        }
    }
    return { draftByTemplateId, standalone }
}

function TabCount({ count }: { count: number | undefined }) {
    return count === undefined ? null : (
        <span className="text-muted-foreground tabular-nums">{count}</span>
    )
}

function NoMatchingTemplates() {
    return (
        <Card className="py-0">
            <EmptyState icon={SearchIcon} title="No matching templates" headingLevel={2} />
        </Card>
    )
}

const templateGridClassName = "grid gap-4 sm:grid-cols-2 xl:grid-cols-3"

// =============================================================================
// Main Page Component
// =============================================================================

function TemplateListLoadError({
    query,
}: {
    query: { error: unknown; isFetching: boolean; refetch: () => Promise<unknown> }
}) {
    return (
        <Card className="py-0">
            <QueryErrorState
                error={query.error}
                onRetry={() => {
                    void query.refetch()
                }}
                isRetrying={query.isFetching}
                title="Couldn't load email templates"
                headingLevel={2}
            />
        </Card>
    )
}

function useEmailTemplatesPageView() {
    const router = useRouter()
    const { user } = useAuth()
    const isAdmin = user?.role === "admin" || user?.role === "developer"
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const permissions = effectivePermissions?.permissions || []
    const canUseAI = Boolean(user?.ai_enabled) && permissions.includes("use_ai_assistant")
    const isNewPolicy = (effectivePermissions?.policy_version ?? 1) >= 2
    const canCreatePersonal = Boolean(effectivePermissions) && (!isNewPolicy || permissions.includes("manage_email_templates"))
    const canManageEmailTemplates = isNewPolicy
        ? permissions.includes("manage_email_templates") && permissions.includes("manage_org_templates")
        : isAdmin || permissions.includes("manage_email_templates")

    const [activeTab, setActiveTab] = useState("personal")
    const [search, setSearch] = useState("")
    const [showAllPersonal, setShowAllPersonal] = useState(false)
    const [hideInactivePersonal, setHideInactivePersonal] = useState(true)
    const [hideInactiveOrg, setHideInactiveOrg] = useState(true)
    const [showPreview, setShowPreview] = useState(false)
    const [signaturePreviewMode, setSignaturePreviewMode] = useState<"personal" | "org">("personal")

    const signaturePhotoInputRef = useRef<HTMLInputElement>(null)

    // Copy/Share dialog state
    const [copyDialogOpen, setCopyDialogOpen] = useState(false)
    const [shareDialogOpen, setShareDialogOpen] = useState(false)
    const copyShareTargetRef = useRef<EmailTemplateListItem | null>(null)
    const [copyShareName, setCopyShareName] = useState("")

    // Test send dialog state
    const [testSendState, dispatchTestSend] = useReducer(
        testSendDialogReducer,
        initialTestSendDialogState,
    )
    const testSendOccurrenceIdRef = useRef<string | null>(null)

    // Platform library copy/preview state
    const [libraryCopyOpen, setLibraryCopyOpen] = useState(false)
    const libraryCopyTargetRef = useRef<EmailTemplateLibraryItem | null>(null)
    const [libraryCopyName, setLibraryCopyName] = useState("")
    const [libraryPreviewId, setLibraryPreviewId] = useState<string | null>(null)
    const [draftToDiscard, setDraftToDiscard] = useState<EmailTemplateDraft | null>(null)
    const [templateToDelete, setTemplateToDelete] = useState<EmailTemplateListItem | null>(null)
    const [templateDeleteError, setTemplateDeleteError] = useState<string | null>(null)
    const [templateStatusTarget, setTemplateStatusTarget] = useState<EmailTemplateListItem | null>(null)
    const [templateStatusError, setTemplateStatusError] = useState<string | null>(null)

    const [signatureDraftOverrides, dispatchSignatureDraft] = useReducer(
        signatureDraftReducer,
        {},
    )

    // API hooks for templates
    const personalTemplatesQuery = useEmailTemplates({
        activeOnly: hideInactivePersonal,
        scope: "personal",
        showAllPersonal: isAdmin && showAllPersonal,
    })
    const { data: personalTemplates, isLoading: loadingPersonal } = personalTemplatesQuery
    const orgTemplatesQuery = useEmailTemplates({
        activeOnly: canManageEmailTemplates ? hideInactiveOrg : true,
        scope: "org",
    })
    const { data: orgTemplates, isLoading: loadingOrg } = orgTemplatesQuery
    const {
        data: personalDrafts = [],
        isLoading: loadingPersonalDrafts,
        isError: personalDraftsError,
        refetch: refetchPersonalDrafts,
    } = useEmailTemplateDrafts({
        scope: "personal",
        showAllPersonal: isAdmin && showAllPersonal,
    })
    const {
        data: loadedOrgDrafts = [],
        isLoading: loadingOrgDrafts,
    } = useEmailTemplateDrafts(
        { scope: "org" },
        canManageEmailTemplates,
    )
    const orgDrafts = canManageEmailTemplates ? loadedOrgDrafts : []
    const templateStatusDraft = templateStatusTarget
        ? (templateStatusTarget.scope === "personal" ? personalDrafts : orgDrafts).find(
            (draft) => draft.template_id === templateStatusTarget.id,
        ) ?? null
        : null
    const libraryTemplatesQuery = useEmailTemplateLibrary()
    const { data: libraryTemplates, isLoading: loadingLibrary } = libraryTemplatesQuery
    const discardDraft = useDiscardEmailTemplateDraft()

    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()
    const copyToPersonal = useCopyTemplateToPersonal()
    const shareWithOrg = useShareTemplateWithOrg()
    const copyFromLibrary = useCopyTemplateFromLibrary()
    const sendTest = useSendTestEmailTemplate()

    // Signature hooks
    const { data: signatureData, refetch: refetchSignature } = useUserSignature()
    const updateSignatureMutation = useUpdateUserSignature()
    const uploadPhotoMutation = useUploadSignaturePhoto()
    const deletePhotoMutation = useDeleteSignaturePhoto()
    const { data: personalSignaturePreview } = useSignaturePreview()
    const { data: orgSignaturePreview } = useOrgSignaturePreview({ enabled: true, mode: "org_only" })
    const signatureDraft = {
        ...createSignatureDraftState(signatureData),
        ...signatureDraftOverrides,
    }

    const hasChanges = Boolean(
            signatureData &&
            (
            signatureDraft.name !== (signatureData.signature_name || "") ||
            signatureDraft.title !== (signatureData.signature_title || "") ||
            signatureDraft.phone !== (signatureData.signature_phone || "") ||
            signatureDraft.linkedin !== (signatureData.signature_linkedin || "") ||
            signatureDraft.twitter !== (signatureData.signature_twitter || "") ||
            signatureDraft.instagram !== (signatureData.signature_instagram || "")
        )
    )

    const { data: testSendTemplateDetail, isLoading: testSendTemplateLoading } = useEmailTemplate(
        testSendState.target?.id || null
    )
    const { data: libraryTemplateDetail } = useEmailTemplateLibraryItem(libraryPreviewId)
    const testSendUsedVariables = testSendTemplateDetail
        ? extractTemplateVariables(`${testSendTemplateDetail.subject}\n${testSendTemplateDetail.body}`)
            .slice()
            .sort((a, b) => a.localeCompare(b))
        : []
    const testSendHasUnsubscribeUrl = testSendUsedVariables.includes("unsubscribe_url")
    const testSendEditableVariables = testSendUsedVariables.filter((name) => name !== "unsubscribe_url")
    const testSendDefaultVariables: Record<string, string> = {}
    const testSendRecipient = testSendState.toEmail.trim() || user?.email || ""
    for (const variableName of testSendEditableVariables) {
        testSendDefaultVariables[variableName] = buildTestVariableSample(variableName, {
            toEmail: testSendRecipient,
            ownerName: user?.display_name,
            orgName: user?.org_name,
        })
    }
    const testSendVariables = {
        ...testSendDefaultVariables,
        ...testSendState.variables,
    }

    const handleOpenDeleteDialog = (template: EmailTemplateListItem) => {
        setTemplateDeleteError(null)
        setTemplateToDelete(template)
    }

    const handleDeleteTemplate = () => {
        if (!templateToDelete) return

        const target = templateToDelete
        setTemplateDeleteError(null)
        deleteTemplate.mutate(target.id, {
            onSuccess: () => {
                toast.success(`${target.name} deleted`)
                setTemplateToDelete(null)
            },
            onError: (error: Error) => {
                const message = error.message || `Failed to delete ${target.name}`
                setTemplateDeleteError(message)
                toast.error(message)
            },
        })
    }

    const handleOpenTemplateStatusDialog = (template: EmailTemplateListItem) => {
        setTemplateStatusError(null)
        setTemplateStatusTarget(template)
    }

    const handleChangeTemplateStatus = () => {
        if (!templateStatusTarget) return

        const nextIsActive = !templateStatusTarget.is_active
        const nextStatusLabel = nextIsActive ? "active" : "inactive"

        setTemplateStatusError(null)
        updateTemplate.mutate(
            {
                id: templateStatusTarget.id,
                data: { is_active: nextIsActive },
            },
            {
                onSuccess: () => {
                    toast.success(`${templateStatusTarget.name} is now ${nextStatusLabel}`)
                    setTemplateStatusTarget(null)
                },
                onError: (error: Error) => {
                    const message = error.message || `Failed to set template ${nextStatusLabel}`
                    setTemplateStatusError(message)
                    toast.error(message)
                },
            },
        )
    }

    const handleTemplateStatusPrimaryAction = () => {
        if (!templateStatusTarget) return

        if (templateStatusDraft) {
            router.push(getTemplateStudioHref(templateStatusTarget))
            setTemplateStatusTarget(null)
            setTemplateStatusError(null)
            return
        }

        handleChangeTemplateStatus()
    }

    const handleOpenCopyDialog = (template: EmailTemplateListItem) => {
        copyShareTargetRef.current = template
        setCopyShareName(`${template.name} (Copy)`)
        setCopyDialogOpen(true)
    }

    const handleOpenShareDialog = (template: EmailTemplateListItem) => {
        copyShareTargetRef.current = template
        setCopyShareName(template.name)
        setShareDialogOpen(true)
    }

    const handleOpenTestDialog = (template: EmailTemplateListItem) => {
        testSendOccurrenceIdRef.current = createEmailTestOccurrenceId()
        dispatchTestSend({ type: "open", target: template, toEmail: user?.email || "" })
    }

    const handleCloseTestDialog = () => {
        testSendOccurrenceIdRef.current = null
        dispatchTestSend({ type: "close" })
    }

    const handleSendTest = async () => {
        if (!testSendState.target) return
        // SendTestEmailDialog validates the address before calling this handler.
        const toEmail = testSendState.toEmail.trim()
        dispatchTestSend({ type: "setError", value: null })

        const overrides: Record<string, string> = {}
        for (const [key, value] of Object.entries(testSendState.variables)) {
            const trimmed = value.trim()
            if (!trimmed) continue
            overrides[key] = trimmed
        }

        try {
            const occurrenceId =
                testSendOccurrenceIdRef.current ?? createEmailTestOccurrenceId()
            testSendOccurrenceIdRef.current = occurrenceId
            const result = await sendTest.mutateAsync({
                id: testSendState.target.id,
                payload: {
                    to_email: toEmail,
                    variables: overrides,
                    idempotency_key: occurrenceId,
                    ...(testSendState.ignoreOptOut ? { ignore_opt_out: true } : {}),
                },
            })
            const providerLabel =
                result.provider_used === "resend"
                    ? "Resend"
                    : result.provider_used === "gmail"
                        ? "Gmail"
                        : "provider"
            toast.success(
                result.queued
                    ? `Test email queued via ${providerLabel}`
                    : `Test email sent via ${providerLabel}`,
            )
            handleCloseTestDialog()
        } catch (error) {
            dispatchTestSend({
                type: "setError",
                value: getActionErrorMessage(error, "Couldn't send the test email. Try again."),
            })
        }
    }

    const handleCopy = () => {
        const target = copyShareTargetRef.current
        if (!target || !copyShareName.trim()) return
        copyToPersonal.mutate(
            { id: target.id, data: { name: copyShareName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template copied to your personal templates")
                    setCopyDialogOpen(false)
                    copyShareTargetRef.current = null
                    setCopyShareName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to copy template")
                },
            }
        )
    }

    const handleShare = () => {
        const target = copyShareTargetRef.current
        if (!target || !copyShareName.trim()) return
        shareWithOrg.mutate(
            { id: target.id, data: { name: copyShareName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template shared with the organization")
                    setShareDialogOpen(false)
                    copyShareTargetRef.current = null
                    setCopyShareName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to share template")
                },
            }
        )
    }

    const previewSubjectTemplate = libraryTemplateDetail?.subject ?? ""
    const previewOrganizationName =
        signatureData?.org_signature_company_name ||
        user?.org_display_name ||
        user?.org_name ||
        "Your organization"
    const previewSubject = previewSubjectTemplate
        .replace(/\{\{full_name\}\}/g, "John Smith")
        .replace(/\{\{org_name\}\}/g, previewOrganizationName)
    const previewHtml = showPreview
        ? buildEmailTemplatePreviewHtml(
            libraryTemplateDetail?.body ?? "",
            {
                orgCompanyName: previewOrganizationName,
                scope: "org",
                personalSignatureHtml: personalSignaturePreview?.html,
                orgSignatureHtml: orgSignaturePreview?.html,
            }
        )
        : ""

    const handleLibraryPreview = (templateId: string) => {
        setLibraryPreviewId(templateId)
        setShowPreview(true)
    }

    const handlePreviewOpenChange = (open: boolean) => {
        setShowPreview(open)
        if (!open) {
            setLibraryPreviewId(null)
        }
    }

    const handleLibraryCopy = () => {
        const target = libraryCopyTargetRef.current
        if (!canManageEmailTemplates || copyFromLibrary.isPending || !target || !libraryCopyName.trim()) return
        copyFromLibrary.mutate(
            { id: target.id, data: { name: libraryCopyName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template copied to org templates")
                    setLibraryCopyOpen(false)
                    libraryCopyTargetRef.current = null
                    setLibraryCopyName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to copy template")
                },
            }
        )
    }

    const handleDiscardDraft = () => {
        if (!draftToDiscard) return

        discardDraft.mutate(
            {
                id: draftToDiscard.id,
                expectedRevision: draftToDiscard.revision,
            },
            {
                onSuccess: () => {
                    toast.success("Draft discarded")
                    setDraftToDiscard(null)
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to discard draft")
                },
            },
        )
    }

    // Save all signature settings
    const handleSaveSignature = () => {
        updateSignatureMutation.mutate(
            {
                signature_name: signatureDraft.name || null,
                signature_title: signatureDraft.title || null,
                signature_phone: signatureDraft.phone || null,
                signature_linkedin: signatureDraft.linkedin || null,
                signature_twitter: signatureDraft.twitter || null,
                signature_instagram: signatureDraft.instagram || null,
            },
            {
                onSuccess: () => {
                    void refetchSignature()
                },
            }
        )
    }

    const handleUploadPhoto = (file: File) => {
        uploadPhotoMutation.mutate(file, {
            onSuccess: () => {
                void refetchSignature()
            },
        })
    }

    const handleSignaturePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        const allowedTypes = ["image/png", "image/jpeg", "image/webp"]
        if (!allowedTypes.includes(file.type)) {
            toast.error("Please select a PNG, JPEG, or WebP image")
            return
        }

        if (file.size > 2 * 1024 * 1024) {
            toast.error("Image must be less than 2MB")
            return
        }

        handleUploadPhoto(file)
        e.target.value = ""
    }

    const handleDeletePhoto = () => {
        if (confirm("Remove your signature photo? Your profile avatar will be used instead.")) {
            deletePhotoMutation.mutate(undefined, {
                onSuccess: () => {
                    void refetchSignature()
                },
            })
        }
    }

    const personalDraftGroups = splitTemplateDrafts(personalDrafts, personalTemplates)
    const orgDraftGroups = splitTemplateDrafts(orgDrafts, orgTemplates)
    const visiblePersonalDrafts = personalDraftGroups.standalone.filter((draft) =>
        matchesTemplateSearch(draft, search),
    )
    const visiblePersonalTemplates = (personalTemplates ?? []).filter((template) =>
        matchesTemplateSearch(template, search),
    )
    const visibleOrgDrafts = orgDraftGroups.standalone.filter((draft) =>
        matchesTemplateSearch(draft, search),
    )
    const visibleOrgTemplates = (orgTemplates ?? []).filter((template) =>
        matchesTemplateSearch(template, search),
    )
    const visibleLibraryTemplates = (libraryTemplates ?? []).filter((template) =>
        matchesTemplateSearch(template, search),
    )
    const canDiscardPersonalDraft = (draft: EmailTemplateDraft) =>
        canCreatePersonal && (draft.owner_user_id === user?.user_id || isAdmin)
    const getDiscardDraftHandler = (draft: EmailTemplateDraft | undefined, canDiscard: boolean) =>
        draft && canDiscard ? () => setDraftToDiscard(draft) : undefined

    return (
        <div className="flex min-h-dvh flex-col">
            <EmailTemplatesPageHeader
                activeTab={activeTab}
                canUseAI={canUseAI}
                canManageEmailTemplates={canManageEmailTemplates}
                canCreatePersonal={canCreatePersonal}
                onCreatePersonal={() => router.push("/automation/email-templates/personal/new" as Route)}
                onCreateOrganization={() => router.push("/automation/email-templates/org/new")}
            />

            {/* Content */}
            <div className="flex-1 p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                        <TabsList
                            aria-label="Template type"
                            className="max-w-full justify-start overflow-x-auto"
                        >
                            <TabsTrigger value="personal" className="gap-1.5">
                                Personal{" "}
                                <TabCount
                                    count={
                                        personalTemplates
                                            ? personalTemplates.length + personalDraftGroups.standalone.length
                                            : undefined
                                    }
                                />
                            </TabsTrigger>
                            <TabsTrigger value="org" className="gap-1.5">
                                Organization{" "}
                                <TabCount
                                    count={
                                        orgTemplates
                                            ? orgTemplates.length + orgDraftGroups.standalone.length
                                            : undefined
                                    }
                                />
                            </TabsTrigger>
                            <TabsTrigger value="platform" className="gap-1.5">
                                Platform <TabCount count={libraryTemplates?.length} />
                            </TabsTrigger>
                            <TabsTrigger value="signature">Signature</TabsTrigger>
                        </TabsList>

                        {activeTab !== "signature" && (
                            <div className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 sm:w-auto">
                                <div className="relative w-full sm:w-56">
                                    <SearchIcon
                                        aria-hidden="true"
                                        className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                                    />
                                    <Input
                                        type="search"
                                        aria-label="Search templates"
                                        placeholder="Search"
                                        value={search}
                                        onChange={(event) => setSearch(event.target.value)}
                                        className="pl-8"
                                    />
                                </div>
                                {(activeTab === "personal" ||
                                    (activeTab === "org" && canManageEmailTemplates)) && (
                                    <>
                                        <div className="flex items-center gap-2">
                                            <Checkbox
                                                id={`hide-inactive-${activeTab}-templates`}
                                                checked={
                                                    activeTab === "personal"
                                                        ? hideInactivePersonal
                                                        : hideInactiveOrg
                                                }
                                                onCheckedChange={(checked) => {
                                                    if (activeTab === "personal") {
                                                        setHideInactivePersonal(checked === true)
                                                    } else {
                                                        setHideInactiveOrg(checked === true)
                                                    }
                                                }}
                                            />
                                            <Label
                                                htmlFor={`hide-inactive-${activeTab}-templates`}
                                                className="cursor-pointer text-sm font-normal"
                                            >
                                                Hide Inactive
                                            </Label>
                                        </div>
                                        {activeTab === "personal" && isAdmin && (
                                            <Select
                                                value={showAllPersonal ? "all" : "mine"}
                                                onValueChange={(v) => setShowAllPersonal(v === "all")}
                                            >
                                                <SelectTrigger className="w-auto min-w-[180px]">
                                                    <SelectValue>
                                                        {(value: string | null) =>
                                                            getPersonalTemplateVisibilityLabel(
                                                                value,
                                                            )
                                                        }
                                                    </SelectValue>
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="mine">My Templates</SelectItem>
                                                    <SelectItem value="all">All Personal Templates</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        )}
                                    </>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Personal Templates Tab */}
                    <TabsContent value="personal" className="space-y-4">
                        {loadingPersonal || loadingPersonalDrafts ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : personalTemplatesQuery.isError && personalTemplates === undefined ? (
                            <TemplateListLoadError query={personalTemplatesQuery} />
                        ) : personalDraftsError ? (
                            <Alert variant="destructive">
                                <AlertTriangleIcon aria-hidden="true" />
                                <AlertTitle>
                                    Unable to load personal drafts
                                </AlertTitle>
                                <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                                    <span>
                                        Published templates are unchanged. Retry to
                                        recover any saved draft work.
                                    </span>
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => void refetchPersonalDrafts()}
                                    >
                                        Retry drafts
                                    </Button>
                                </AlertDescription>
                            </Alert>
                        ) : !personalTemplates?.length && !personalDrafts.length ? (
                            <Card className="py-0">
                                <EmptyState
                                    icon={UserIcon}
                                    title="No personal templates yet"
                                    headingLevel={2}
                                    action={
                                        showAllPersonal || !canCreatePersonal ? undefined : (
                                            <Button
                                                onClick={() =>
                                                    router.push(
                                                        "/automation/email-templates/personal/new" as Route,
                                                    )
                                                }
                                            >
                                                <PlusIcon className="mr-2 size-4" />
                                                Create Template
                                            </Button>
                                        )
                                    }
                                />
                            </Card>
                        ) : !visiblePersonalTemplates.length && !visiblePersonalDrafts.length ? (
                            <NoMatchingTemplates />
                        ) : (
                            <div className={templateGridClassName}>
                                {visiblePersonalDrafts.map((draft) => (
                                    <TemplateDraftCard
                                        key={draft.id}
                                        draft={draft}
                                        onDiscard={getDiscardDraftHandler(draft, canDiscardPersonalDraft(draft))}
                                    />
                                ))}
                                {visiblePersonalTemplates.map((template) => {
                                    const draft = personalDraftGroups.draftByTemplateId.get(template.id)
                                    const isOwner = template.owner_user_id === user?.user_id
                                    const canManagePersonalTemplate = template.capabilities?.can_edit ?? (isOwner || isAdmin)
                                    const canSendPersonalTest = template.capabilities?.can_send_test ?? (isOwner || canManageEmailTemplates)
                                    const actions: TemplateCardActionKind[] = []
                                    if (canSendPersonalTest) {
                                        actions.push("send_test")
                                    }
                                    if (canManagePersonalTemplate && !template.is_system_template) {
                                        actions.push("edit")
                                        if (template.is_active) {
                                            actions.push("set_inactive")
                                        } else {
                                            actions.push("set_active")
                                        }
                                    }
                                    if (template.capabilities?.can_publish_to_org ?? isOwner) {
                                        actions.push("share")
                                    }
                                    if (canManagePersonalTemplate && !template.is_system_template) {
                                        actions.push("delete")
                                    }
                                    const controls: TemplateCardControls = !isOwner && !isAdmin
                                        ? { kind: "read_only" }
                                        : {
                                            kind: "actions",
                                            actions,
                                            onAction: (action) => {
                                                if (action === "send_test") {
                                                    handleOpenTestDialog(template)
                                                    return
                                                }
                                                if (action === "edit") {
                                                    router.push(getTemplateStudioHref(template))
                                                    return
                                                }
                                                if (action === "set_inactive" || action === "set_active") {
                                                    handleOpenTemplateStatusDialog(template)
                                                    return
                                                }
                                                if (action === "share") {
                                                    handleOpenShareDialog(template)
                                                    return
                                                }
                                                if (action === "delete") {
                                                    handleOpenDeleteDialog(template)
                                                }
                                            },
                                        }
                                    return (
                                        <TemplateCard
                                            key={template.id}
                                            template={template}
                                            controls={controls}
                                            draft={draft}
                                            onDiscardDraft={getDiscardDraftHandler(
                                                draft,
                                                Boolean(draft && canDiscardPersonalDraft(draft)),
                                            )}
                                        />
                                    )
                                })}
                            </div>
                        )}
                    </TabsContent>

                    {/* Org Templates Tab */}
                    <TabsContent value="org" className="space-y-4">
                        {loadingOrg || loadingOrgDrafts ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : orgTemplatesQuery.isError && orgTemplates === undefined ? (
                            <TemplateListLoadError query={orgTemplatesQuery} />
                        ) : !orgTemplates?.length && !orgDrafts.length ? (
                            <Card className="py-0">
                                <EmptyState
                                    icon={BuildingIcon}
                                    title="No organization templates yet"
                                    headingLevel={2}
                                    action={
                                        canManageEmailTemplates ? (
                                            <Button onClick={() => router.push("/automation/email-templates/org/new")}>
                                                <PlusIcon className="mr-2 size-4" />
                                                Create Org Template
                                            </Button>
                                        ) : undefined
                                    }
                                />
                            </Card>
                        ) : !visibleOrgTemplates.length && !visibleOrgDrafts.length ? (
                            <NoMatchingTemplates />
                        ) : (
                            <div className={templateGridClassName}>
                                {visibleOrgDrafts.map((draft) => (
                                    <TemplateDraftCard
                                        key={draft.id}
                                        draft={draft}
                                        onDiscard={getDiscardDraftHandler(draft, canManageEmailTemplates)}
                                    />
                                ))}
                                {visibleOrgTemplates.map((template) => {
                                    const draft = orgDraftGroups.draftByTemplateId.get(template.id)
                                    const actions: TemplateCardActionKind[] = []
                                    if (template.capabilities?.can_send_test ?? canManageEmailTemplates) {
                                        actions.push("send_test")
                                    }
                                    if ((template.capabilities?.can_edit ?? canManageEmailTemplates) && !template.is_system_template) {
                                        actions.push("edit")
                                        if (template.is_active) {
                                            actions.push("set_inactive")
                                        } else {
                                            actions.push("set_active")
                                        }
                                    }
                                    if (template.capabilities?.can_copy ?? true) actions.push("copy")
                                    if ((template.capabilities?.can_edit ?? canManageEmailTemplates) && !template.is_system_template) {
                                        actions.push("delete")
                                    }
                                    const controls: TemplateCardControls = actions.length === 0
                                        ? { kind: "read_only" }
                                        : {
                                            kind: "actions",
                                            actions,
                                            onAction: (action) => {
                                                if (action === "send_test") {
                                                    handleOpenTestDialog(template)
                                                    return
                                                }
                                                if (action === "edit") {
                                                    router.push(getTemplateStudioHref(template))
                                                    return
                                                }
                                                if (action === "set_inactive" || action === "set_active") {
                                                    handleOpenTemplateStatusDialog(template)
                                                    return
                                                }
                                                if (action === "copy") {
                                                    handleOpenCopyDialog(template)
                                                    return
                                                }
                                                if (action === "delete") {
                                                    handleOpenDeleteDialog(template)
                                                }
                                            },
                                        }
                                    return (
                                        <TemplateCard
                                            key={template.id}
                                            template={template}
                                            controls={controls}
                                            draft={draft}
                                            onDiscardDraft={getDiscardDraftHandler(draft, canManageEmailTemplates)}
                                        />
                                    )
                                })}
                            </div>
                        )}
                    </TabsContent>

                    {/* Platform Templates Tab */}
                    <TabsContent value="platform" className="space-y-4">
                        {loadingLibrary ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : libraryTemplatesQuery.isError && libraryTemplates === undefined ? (
                            <TemplateListLoadError query={libraryTemplatesQuery} />
                        ) : !libraryTemplates?.length ? (
                            <Card className="py-0">
                                <EmptyState
                                    icon={LayoutTemplateIcon}
                                    title="No platform templates yet"
                                    headingLevel={2}
                                />
                            </Card>
                        ) : !visibleLibraryTemplates.length ? (
                            <NoMatchingTemplates />
                        ) : (
                            <div className={templateGridClassName}>
                                {visibleLibraryTemplates.map((template) => (
                                    <Card key={template.id} className={templateCardClassName}>
                                        <h3 className={`${templateCardTitleClassName} px-4`}>
                                            <span className="line-clamp-2">{template.name}</span>
                                        </h3>
                                        <TemplateCardSubject subject={template.subject} />
                                        {template.category ? (
                                            <div className="flex flex-wrap items-center gap-1.5 px-4">
                                                <Badge variant="outline" className="capitalize">
                                                    {template.category}
                                                </Badge>
                                            </div>
                                        ) : null}
                                        <div className="flex items-center justify-between gap-2 px-4">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => handleLibraryPreview(template.id)}
                                            >
                                                <EyeIcon className="mr-2 size-4" />
                                                Preview
                                            </Button>
                                            <Button
                                                size="sm"
                                                disabled={!canManageEmailTemplates || copyFromLibrary.isPending}
                                                onClick={() => {
                                                    if (!canManageEmailTemplates) return
                                                    libraryCopyTargetRef.current = template
                                                    setLibraryCopyName(template.name)
                                                    setLibraryCopyOpen(true)
                                                }}
                                            >
                                                <CopyIcon className="mr-2 size-4" />
                                                Copy to Org
                                            </Button>
                                        </div>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </TabsContent>

                    {/* Signature Tab */}
                    <TabsContent value="signature">
                        <div className="grid gap-6 lg:grid-cols-2">
                            {/* Editor Column */}
                            <div className="space-y-6">
                                {/* Main Signature Card */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle>My Signature</CardTitle>
                                        <CardDescription>
                                            Customize your email signature. Leave fields empty to use your profile defaults.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        {/* Signature Photo */}
                                        <SignaturePhotoField
                                            signaturePhotoUrl={signatureData?.signature_photo_url || null}
                                            profilePhotoUrl={signatureData?.profile_photo_url || null}
                                            profileName={signatureData?.profile_name || ""}
                                            avatarAction={
                                                <>
                                                    <input
                                                        id="signature-photo-upload"
                                                        name="signature_photo_upload"
                                                        type="file"
                                                        ref={signaturePhotoInputRef}
                                                        onChange={handleSignaturePhotoChange}
                                                        accept="image/png,image/jpeg,image/webp"
                                                        aria-label="Upload signature photo"
                                                        className="hidden"
                                                    />
                                                    <Button unstyled
                                                        type="button"
                                                        onClick={() => signaturePhotoInputRef.current?.click()}
                                                        disabled={uploadPhotoMutation.isPending}
                                                        className="absolute bottom-0 right-0 flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-md"
                                                        aria-label="Upload signature photo"
                                                    >
                                                        {uploadPhotoMutation.isPending ? (
                                                            <Loader2Icon className="size-3.5 animate-spin" />
                                                        ) : (
                                                            <CameraIcon className="size-3.5" />
                                                        )}
                                                    </Button>
                                                </>
                                            }
                                            customPhotoAction={
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-7 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                                                    onClick={handleDeletePhoto}
                                                    disabled={deletePhotoMutation.isPending}
                                                >
                                                    {deletePhotoMutation.isPending ? (
                                                        <Loader2Icon className="mr-1 size-3 animate-spin" />
                                                    ) : (
                                                        <TrashIcon className="mr-1 size-3" />
                                                    )}
                                                    Remove & use profile photo
                                                </Button>
                                            }
                                        />

                                        <div className="border-t pt-4" />

                                        {/* Override Fields */}
                                        <div className="space-y-3">
                                            <SignatureOverrideField
                                                id="sig-name"
                                                label="Name"
                                                value={signatureDraft.name}
                                                profileDefault={signatureData?.profile_name || null}
                                                onChange={(value) =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "name",
                                                        value,
                                                    })
                                                }
                                                onClear={() =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "name",
                                                        value: "",
                                                    })
                                                }
                                            />

                                            <SignatureOverrideField
                                                id="sig-title"
                                                label="Title"
                                                value={signatureDraft.title}
                                                profileDefault={signatureData?.profile_title || null}
                                                onChange={(value) =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "title",
                                                        value,
                                                    })
                                                }
                                                onClear={() =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "title",
                                                        value: "",
                                                    })
                                                }
                                                placeholder="e.g., Case Manager"
                                            />

                                            <SignatureOverrideField
                                                id="sig-phone"
                                                label="Phone"
                                                value={signatureDraft.phone}
                                                profileDefault={signatureData?.profile_phone || null}
                                                onChange={(value) =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "phone",
                                                        value,
                                                    })
                                                }
                                                onClear={() =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "phone",
                                                        value: "",
                                                    })
                                                }
                                                type="tel"
                                                placeholder="e.g., (555) 123-4567"
                                            />
                                        </div>

                                        <div className="border-t pt-4" />

                                        {/* Social Links */}
                                        <div className="space-y-3">
                                            <h4 className="text-sm font-medium flex items-center gap-2">
                                                Social Links
                                                <span className="text-xs font-normal text-muted-foreground">
                                                    (optional)
                                                </span>
                                            </h4>

                                            <div className="space-y-2">
                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-linkedin" className="text-xs flex items-center gap-1.5">
                                                        <LinkIcon className="size-3.5 text-muted-foreground" />
                                                        LinkedIn
                                                    </Label>
                                                    <Input
                                                        id="sig-linkedin"
                                                        placeholder="https://linkedin.com/in/yourprofile"
                                                        value={signatureDraft.linkedin}
                                                        onChange={(e) =>
                                                            dispatchSignatureDraft({
                                                                type: "changeField",
                                                                field: "linkedin",
                                                                value: e.target.value,
                                                            })
                                                        }
                                                        className="h-9"
                                                    />
                                                </div>

                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-twitter" className="text-xs flex items-center gap-1.5">
                                                        <svg className="size-3.5 text-muted-foreground" viewBox="0 0 24 24" fill="currentColor">
                                                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                                                        </svg>
                                                        X (Twitter)
                                                    </Label>
                                                    <Input
                                                        id="sig-twitter"
                                                        placeholder="https://x.com/yourhandle"
                                                        value={signatureDraft.twitter}
                                                        onChange={(e) =>
                                                            dispatchSignatureDraft({
                                                                type: "changeField",
                                                                field: "twitter",
                                                                value: e.target.value,
                                                            })
                                                        }
                                                        className="h-9"
                                                    />
                                                </div>

                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-instagram" className="text-xs flex items-center gap-1.5">
                                                        <CameraIcon className="size-3.5 text-muted-foreground" />
                                                        Instagram
                                                    </Label>
                                                    <Input
                                                        id="sig-instagram"
                                                        placeholder="https://instagram.com/yourhandle"
                                                        value={signatureDraft.instagram}
                                                        onChange={(e) =>
                                                            dispatchSignatureDraft({
                                                                type: "changeField",
                                                                field: "instagram",
                                                                value: e.target.value,
                                                            })
                                                        }
                                                        className="h-9"
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        {/* Save Button */}
                                        <div className="flex items-center gap-3 pt-1">
                                            <Button
                                                onClick={handleSaveSignature}
                                                disabled={updateSignatureMutation.isPending || !hasChanges}
                                                className="flex-1"
                                            >
                                                {updateSignatureMutation.isPending ? (
                                                    <>
                                                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                                                        Saving…
                                                    </>
                                                ) : (
                                                    "Save Signature"
                                                )}
                                            </Button>
                                            <Button
                                                variant="outline"
                                                onClick={handleCopySignatureHtml}
                                            >
                                                <CodeIcon className="mr-2 size-4" />
                                                Copy HTML
                                            </Button>
                                        </div>
                                        {hasChanges && (
                                            <p className="text-xs text-amber-600">
                                                You have unsaved changes
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Organization Branding (read-only) */}
                                {(signatureData?.org_signature_company_name ||
                                    signatureData?.org_signature_address ||
                                    signatureData?.org_signature_phone ||
                                    signatureData?.org_signature_website ||
                                    signatureData?.org_signature_logo_url) && (
                                    <Card className="border-dashed">
                                        <CardHeader className="pb-3">
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="text-base">Organization Branding</CardTitle>
                                                <Badge variant="secondary" className="text-xs">
                                                    Read-only
                                                </Badge>
                                            </div>
                                            <CardDescription>
                                                Managed by your organization admin in Settings
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="flex items-center gap-3">
                                                {signatureData.org_signature_logo_url && (
                                                    <NextImage
                                                        src={signatureData.org_signature_logo_url}
                                                        alt="Logo"
                                                        width={160}
                                                        height={40}
                                                        unoptimized
                                                        className="h-10 w-auto rounded border"
                                                    />
                                                )}
                                                <div>
                                                    <p className="font-medium">
                                                        {signatureData.org_signature_company_name || "Organization"}
                                                    </p>
                                                    {signatureData.org_signature_template && (
                                                        <p className="text-sm text-muted-foreground">
                                                            {signatureData.org_signature_template} template
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            {(signatureData?.org_signature_address ||
                                                signatureData?.org_signature_phone ||
                                                signatureData?.org_signature_website) && (
                                                <div className="mt-3 pt-3 border-t space-y-1 text-sm text-muted-foreground">
                                                    {signatureData?.org_signature_address && (
                                                        <p>{signatureData.org_signature_address}</p>
                                                    )}
                                                    {signatureData?.org_signature_phone && (
                                                        <p>{signatureData.org_signature_phone}</p>
                                                    )}
                                                    {signatureData?.org_signature_website && (
                                                        <a
                                                            className="underline hover:text-foreground transition-colors"
                                                            href={signatureData.org_signature_website}
                                                            rel="noreferrer"
                                                            target="_blank"
                                                        >
                                                            {signatureData.org_signature_website}
                                                        </a>
                                                    )}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                )}
                            </div>

                            {/* Preview Column */}
                            <div className="space-y-6 lg:sticky lg:top-6 h-fit">
                                <Card>
                                    <CardHeader>
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                            <div>
                                                <CardTitle>Signature Preview</CardTitle>
                                                <CardDescription>
                                                    {signaturePreviewMode === "personal"
                                                        ? "Personal email signature (your info + org branding)"
                                                        : "Org workflow signature (org branding only)"}
                                                </CardDescription>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Button
                                                    size="sm"
                                                    variant={signaturePreviewMode === "personal" ? "default" : "outline"}
                                                    onClick={() => setSignaturePreviewMode("personal")}
                                                >
                                                    Personal Email
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant={signaturePreviewMode === "org" ? "default" : "outline"}
                                                    onClick={() => setSignaturePreviewMode("org")}
                                                >
                                                    Org Workflow
                                                </Button>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="border rounded-lg p-4 bg-white min-h-[200px]">
                                            <p className="text-muted-foreground text-sm mb-4 border-b pb-4">
                                                [Your email content here…]
                                            </p>
                                            {signaturePreviewMode === "personal" ? (
                                                        <SignaturePreview />
                                            ) : (
                                                        <OrgSignaturePreview />
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>
                </Tabs>
            </div>

            {/* Copy Template Dialog */}
            <Dialog open={copyDialogOpen} onOpenChange={setCopyDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Copy to My Templates</DialogTitle>
                        <DialogDescription>
                            Create a personal copy of this template that you can customize.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="copy-name">Template Name</Label>
                            <Input
                                id="copy-name"
                                placeholder="My Template Name"
                                value={copyShareName}
                                onChange={(e) => setCopyShareName(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCopyDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCopy}
                            disabled={copyToPersonal.isPending || !copyShareName.trim()}
                        >
                            {copyToPersonal.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            <CopyIcon className="mr-2 size-4" />
                            Copy Template
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Platform Library Copy Dialog */}
            <Dialog open={libraryCopyOpen && canManageEmailTemplates} onOpenChange={(open) => setLibraryCopyOpen(open && canManageEmailTemplates)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Copy to Org Templates</DialogTitle>
                        <DialogDescription>
                            Create an organization template from this platform template.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="library-copy-name">Template Name</Label>
                            <Input
                                id="library-copy-name"
                                placeholder="Org Template Name"
                                value={libraryCopyName}
                                onChange={(e) => setLibraryCopyName(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setLibraryCopyOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleLibraryCopy} disabled={!canManageEmailTemplates || copyFromLibrary.isPending || !libraryCopyName.trim()}>
                            {copyFromLibrary.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Copy Template
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Share Template Dialog */}
            <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Share with Organization</DialogTitle>
                        <DialogDescription>
                            Share this template with your organization. Your personal copy will remain unchanged.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="share-name">Template Name</Label>
                            <Input
                                id="share-name"
                                placeholder="Shared Template Name"
                                value={copyShareName}
                                onChange={(e) => setCopyShareName(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShareDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleShare}
                            disabled={shareWithOrg.isPending || !copyShareName.trim()}
                        >
                            {shareWithOrg.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            <ShareIcon className="mr-2 size-4" />
                            Share Template
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <AlertDialog
                open={templateToDelete !== null}
                onOpenChange={(open) => {
                    if (!open && !deleteTemplate.isPending) {
                        setTemplateToDelete(null)
                        setTemplateDeleteError(null)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Delete {templateToDelete?.name || "this template"}?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            {templateToDelete?.scope === "personal" &&
                            templateToDelete.owner_user_id !== user?.user_id ? (
                                <>
                                    This personal template is owned by{" "}
                                    {templateToDelete.owner_name || "another user"}. It will be set
                                    inactive and hidden from their template picker. Its content stays
                                    preserved and can be reactivated later.
                                </>
                            ) : templateToDelete?.scope === "org" ? (
                                <>
                                    This organization template will be set inactive and hidden from
                                    template pickers. Its content stays preserved and can be
                                    reactivated later.
                                </>
                            ) : (
                                <>
                                    This personal template will be set inactive and hidden from
                                    template pickers. Its content stays preserved and can be
                                    reactivated later.
                                </>
                            )}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    {templateDeleteError && (
                        <Alert variant="destructive" role="alert">
                            <AlertTriangleIcon aria-hidden="true" />
                            <AlertTitle>Unable to delete template</AlertTitle>
                            <AlertDescription>{templateDeleteError}</AlertDescription>
                        </Alert>
                    )}
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteTemplate.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={deleteTemplate.isPending}
                            onClick={handleDeleteTemplate}
                        >
                            {deleteTemplate.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            {deleteTemplate.isPending ? "Deleting…" : "Delete template"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={draftToDiscard !== null}
                onOpenChange={(open) => {
                    if (!open && !discardDraft.isPending) {
                        setDraftToDiscard(null)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Discard draft?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This removes the draft for {draftToDiscard?.name || "this template"}.
                            The published template will not be changed.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={discardDraft.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={discardDraft.isPending}
                            onClick={handleDiscardDraft}
                        >
                            {discardDraft.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Discard draft
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={templateStatusTarget !== null}
                onOpenChange={(open) => {
                    if (!open && !updateTemplate.isPending) {
                        setTemplateStatusTarget(null)
                        setTemplateStatusError(null)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            {templateStatusDraft ? (
                                "Update status in Studio"
                            ) : (
                                <>
                                    Set {templateStatusTarget?.name || "this template"}{" "}
                                    {templateStatusTarget?.is_active ? "inactive" : "active"}?
                                </>
                            )}
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            {templateStatusDraft ? (
                                <>
                                    This template has a saved draft. Changing status here would make
                                    that draft stale. Open the draft in Studio to update and publish
                                    the status together.
                                </>
                            ) : templateStatusTarget?.is_active ? (
                                <>
                                    This preserves the template, its content, and its version history.
                                    It will be hidden from template pickers. New manual sends and future
                                    automated workflow sends using it will stop, while existing queued
                                    or scheduled emails will still send.
                                </>
                            ) : (
                                <>
                                    This preserves the template, its content, and its version
                                    history. It will be available for future email actions, and future
                                    automated workflow sends using it may resume.
                                </>
                            )}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    {templateStatusError && (
                        <Alert variant="destructive" role="alert">
                            <AlertTriangleIcon aria-hidden="true" />
                            <AlertTitle>Unable to update template</AlertTitle>
                            <AlertDescription>{templateStatusError}</AlertDescription>
                        </Alert>
                    )}
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={updateTemplate.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            variant={
                                !templateStatusDraft && templateStatusTarget?.is_active
                                    ? "destructive"
                                    : "default"
                            }
                            disabled={updateTemplate.isPending}
                            onClick={handleTemplateStatusPrimaryAction}
                        >
                            {updateTemplate.isPending && !templateStatusDraft && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            {templateStatusDraft
                                ? "Open draft"
                                : updateTemplate.isPending
                                ? "Updating…"
                                : templateStatusTarget?.is_active
                                  ? "Set inactive"
                                  : "Set active"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <SendTestEmailDialog
                open={testSendState.isOpen}
                onOpenChange={(open) => {
                    if (!open) {
                        handleCloseTestDialog()
                    }
                }}
                description={testSendState.target?.name}
                toEmail={testSendState.toEmail}
                onToEmailChange={(value) => {
                    testSendOccurrenceIdRef.current = null
                    dispatchTestSend({ type: "changeToEmail", value })
                }}
                ignoreOptOut={testSendState.ignoreOptOut}
                onIgnoreOptOutChange={(value) => {
                    testSendOccurrenceIdRef.current = null
                    dispatchTestSend({ type: "changeIgnoreOptOut", value })
                }}
                variableNames={testSendEditableVariables}
                variables={testSendVariables}
                onVariableChange={(name, value) => {
                    testSendOccurrenceIdRef.current = null
                    dispatchTestSend({ type: "changeVariable", name, value })
                }}
                variablesLoading={testSendTemplateLoading}
                hasUnsubscribeUrl={testSendHasUnsubscribeUrl}
                error={testSendState.error}
                isSending={sendTest.isPending}
                onSend={() => {
                    void handleSendTest()
                }}
            />

            {/* Preview Modal */}
            <Dialog open={showPreview} onOpenChange={handlePreviewOpenChange}>
                <DialogContent size="2xl" className="max-h-[80vh]">
                    <DialogHeader>
                        <DialogTitle>Email Preview</DialogTitle>
                        <DialogDescription>
                            Preview with sample data
                        </DialogDescription>
                    </DialogHeader>
                    <div className="border rounded-lg bg-white overflow-y-auto max-h-[60vh]">
                        {/* Email header section */}
                        <div className="bg-muted/30 border-b px-4 py-3 space-y-2">
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">From:</span>
                                <span className="text-foreground">
                                    {previewOrganizationName} &lt;you@company.com&gt;
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">To:</span>
                                <span className="text-foreground">John Smith &lt;john@example.com&gt;</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">Subject:</span>
                                <span className="font-medium text-foreground">
                                    {previewSubject}
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">Signature:</span>
                                <span className="text-foreground">
                                    Organization signature
                                </span>
                            </div>
                        </div>
                        {/* Email body section */}
                        <div className="p-4">
                            <SafeHtmlContent
                                html={previewHtml}
                                className="prose prose-sm prose-neutral max-w-none text-neutral-900 [&_p]:whitespace-pre-wrap"
                            />
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}

export default function EmailTemplatesPage() {
    return useEmailTemplatesPageView()
}
