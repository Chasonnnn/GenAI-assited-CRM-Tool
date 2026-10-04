"use client"

import Image from "next/image"
import { type ChangeEvent, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ValidatedField } from "@/components/ui/field"
import { PageHeader } from "@/components/page-header"
import { SaveStatus, type SaveStatusState } from "@/components/ui/save-bar"
import { TestSendAgencySelect, useTestSendAgencies } from "@/components/ops/templates/TestSendAgencySelect"
import { getSubscriptionPlanLabel } from "@/components/ops/agencies/agency-constants"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { useFormValidation } from "@/lib/forms/use-form-validation"
import { validateEmail, validateRequired } from "@/lib/forms/validators"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import {
    AlertTriangleIcon,
    ArrowLeftIcon,
    ImageIcon,
    LayoutTemplateIcon,
    Loader2Icon,
    MoreHorizontalIcon,
    RotateCcwIcon,
    SaveIcon,
    SearchIcon,
    SendIcon,
    Trash2Icon,
    UploadIcon,
    UsersIcon,
} from "lucide-react"
import { toast } from "@/components/ui/toast"
import { EmailDesignEditor, type EmailDesignEditorHandle } from "@/components/email/design/email-design-editor"
import { EmailHtmlSource } from "@/components/email/design/email-html-source"
import { EmailPreviewPane } from "@/components/email/design/email-preview-pane"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import type { EmailBodyValue } from "@/lib/email-design"
import type { EmailBodyDesign } from "@/lib/api/email-templates"
import {
    usePlatformEmailBranding,
    usePlatformSystemEmailTemplate,
    usePlatformSystemEmailTemplateVariables,
    useDeletePlatformSystemEmailTemplate,
    useSendPlatformSystemEmailCampaign,
    useSendTestPlatformSystemEmailTemplate,
    useUploadPlatformEmailBrandingLogo,
    useUpdatePlatformEmailBranding,
    useUpdatePlatformSystemEmailTemplate,
} from "@/lib/hooks/use-platform-templates"
import {
    listMembers,
    previewPlatformSystemEmailTemplate,
    type OrganizationSummary,
    type OrgMember,
} from "@/lib/api/platform"

const SF_INVITE_SUBJECT = "Invitation to join {{org_name}} as {{role_title}}"
const SF_INVITE_BODY = `<div style="background-color: #f5f5f7; padding: 40px 12px; margin: 0;">
  <span style="display:none; max-height:0; max-width:0; color:transparent; height:0; width:0;">
    You're invited to join {{org_name}}. This link may expire soon.
  </span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f7;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="width: 100%; max-width: 600px; background-color: #ffffff;
                      border: 1px solid #e5e7eb; border-radius: 20px;
                      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
          <tr>
            <td style="padding: 30px 40px 0 40px; text-align: center;">
              {{platform_logo_block}}
              <div style="margin-top: 12px; font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 40px 0 40px; text-align: center;">
              <h1 style="margin: 0; font-size: 26px; line-height: 1.35; color: #111827; font-weight: 600;">
                You're invited to join
              </h1>
              <div style="margin-top: 6px; font-size: 22px; line-height: 1.3; color: #111827; font-weight: 600;">
                {{org_name}}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 48px 0 48px; text-align: center;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You've been invited to join
              </p>
              <p style="margin: 6px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                as a <strong>{{role_title}}</strong>.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 26px 40px 0 40px; text-align: center;">
              <a href="{{invite_url}}" target="_blank"
                 style="display: inline-block; background-color: #111827; color: #ffffff;
                        text-decoration: none; font-weight: 600; font-size: 15px;
                        padding: 14px 28px; border-radius: 999px;">
                Accept Invitation
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding: 28px 40px 0 40px;">
              <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                  What happens next
                </p>
                <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                  <li>Set up your account in minutes</li>
                  <li>Review your workspace access</li>
                  <li>Start collaborating with your team</li>
                </ul>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 18px 40px 0 40px;">
              <p style="margin: 0; font-size: 13px; color: #6b7280;">
                If the button doesn't work, paste this link into your browser:
              </p>
              <p style="margin: 8px 0 0 0; font-size: 13px;">
                <a href="{{invite_url}}" target="_blank" style="color: #2563eb; text-decoration: none;">
                  {{invite_url}}
                </a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 22px 40px 32px 40px;">
              <div style="padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                {{expires_block}}
                <p style="margin: 8px 0 0 0; color: #9ca3af;">
                  If you didn't expect this invitation, you can safely ignore this email.
                </p>
              </div>
            </td>
          </tr>
        </table>
        <div style="margin-top: 14px; text-align: center; font-size: 11px; color: #9ca3af;">
          Copyright 2026 Surrogacy Force. All rights reserved.
        </div>
      </td>
    </tr>
  </table>
</div>`

function createCampaignOccurrenceId(): string {
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
    return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
    ].join("-")
}

type ActiveInsertionTarget = "subject" | "body" | null

type EditorView = "edit" | "preview" | "html"

type TemplateDraft = {
    subject: string
    fromEmail: string
    body: string
    bodyDesign: EmailBodyDesign | null
    isActive: boolean
}

type TemplateDraftSource = {
    subject?: string | null
    from_email?: string | null
    body?: string | null
    body_design?: EmailBodyDesign | null
    is_active?: boolean
} | null | undefined

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

function buildTemplateDraft(template: TemplateDraftSource): TemplateDraft {
    return {
        subject: template?.subject ?? "",
        fromEmail: template?.from_email ?? "",
        body: template?.body ?? "",
        bodyDesign: template?.body_design ?? null,
        isActive: template?.is_active ?? true,
    }
}

function getFromEmailError(fromEmail: string): string | null {
    const value = fromEmail.trim()
    if (!value) return null
    const basicEmail = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/
    const namedEmail = /^.+<\s*[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+\s*>$/
    if (basicEmail.test(value) || namedEmail.test(value)) return null
    return "Use a valid email or name <email@domain> format."
}

function getLogoPreviewUrl(logoUrl: string): string {
    if (!logoUrl) return ""
    if (logoUrl.startsWith("/platform/email/branding/logo/local/")) {
        const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "")
        return base ? `${base}${logoUrl}` : logoUrl
    }
    return logoUrl
}

function recordSelection(
    el: HTMLInputElement | HTMLTextAreaElement,
    ref: MutableRefObject<{ start: number; end: number } | null>
) {
    ref.current = {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
}

function insertIntoTextControl(
    el: HTMLInputElement | HTMLTextAreaElement | null,
    selectionRef: MutableRefObject<{ start: number; end: number } | null>,
    setValue: Dispatch<SetStateAction<string>>,
    token: string
) {
    if (!el) {
        setValue((prev) => `${prev}${token}`)
        return
    }
    const selection = selectionRef.current ?? {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
    const result = insertAtCursor(el.value, token, selection.start, selection.end)
    setValue(result.nextValue)
    requestAnimationFrame(() => {
        el.focus()
        el.setSelectionRange(result.nextSelectionStart, result.nextSelectionEnd)
        selectionRef.current = { start: result.nextSelectionStart, end: result.nextSelectionEnd }
    })
}

function SystemTemplateCampaignRecipientCard({
    isMembersLoading,
    members,
    onToggleSelectAllUsers,
    onToggleUserSelection,
    org,
    orgId,
    selectedUsers,
}: {
    isMembersLoading: boolean
    members: OrgMember[]
    onToggleSelectAllUsers: (orgId: string, next: boolean) => void
    onToggleUserSelection: (orgId: string, userId: string, next: boolean) => void
    org: OrganizationSummary | undefined
    orgId: string
    selectedUsers: Set<string>
}) {
    const activeMembers = members.filter((member) => member.is_active)
    const selectionLabel = isMembersLoading
        ? "Loading members\u2026"
        : activeMembers.length === 0
          ? "No active members found."
          : `${selectedUsers.size} of ${activeMembers.length} selected`
    const allSelected =
        activeMembers.length > 0 &&
        activeMembers.every((member) => selectedUsers.has(member.user_id))

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">{org?.name || "Organization"}</CardTitle>
                <CardDescription>{selectionLabel}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                    <Label className="flex items-center gap-2">
                        <Checkbox
                            checked={allSelected}
                            onCheckedChange={(next) => onToggleSelectAllUsers(orgId, next === true)}
                        />
                        Select all active users
                    </Label>
                    {isMembersLoading && (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Loader2Icon className="size-3 animate-spin" />
                            Loading users&hellip;
                        </span>
                    )}
                </div>
                <div className="rounded-md border">
                    <ScrollArea className="h-40">
                        <div className="divide-y">
                            {members.map((member) => (
                                <label
                                    key={member.id}
                                    className="flex items-center justify-between gap-3 p-3 text-sm"
                                >
                                    <div className="flex items-center gap-3">
                                        <Checkbox
                                            checked={selectedUsers.has(member.user_id)}
                                            disabled={!member.is_active}
                                            onCheckedChange={(next) =>
                                                onToggleUserSelection(
                                                    orgId,
                                                    member.user_id,
                                                    next === true
                                                )
                                            }
                                        />
                                        <div>
                                            <div className="font-medium text-foreground">
                                                {member.display_name || member.email}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {member.email}
                                            </div>
                                        </div>
                                    </div>
                                    {!member.is_active && (
                                        <Badge variant="outline" className="text-xs">
                                            Inactive
                                        </Badge>
                                    )}
                                </label>
                            ))}
                            {members.length === 0 && !isMembersLoading && (
                                <div className="p-3 text-xs text-muted-foreground">
                                    No members found.
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                </div>
            </CardContent>
        </Card>
    )
}

function SystemTemplateCampaignRecipients({
    membersLoading,
    onToggleSelectAllUsers,
    onToggleUserSelection,
    orgMembers,
    orgs,
    selectedOrgIds,
    selectedUsersByOrg,
}: {
    membersLoading: Record<string, boolean>
    onToggleSelectAllUsers: (orgId: string, next: boolean) => void
    onToggleUserSelection: (orgId: string, userId: string, next: boolean) => void
    orgMembers: Record<string, OrgMember[]>
    orgs: OrganizationSummary[]
    selectedOrgIds: string[]
    selectedUsersByOrg: Record<string, string[]>
}) {
    if (selectedOrgIds.length === 0) return null

    return (
        <div className="space-y-3">
            <Label>Recipients</Label>
            <div className="space-y-4">
                {selectedOrgIds.map((selectedOrgId) => (
                    <SystemTemplateCampaignRecipientCard
                        key={selectedOrgId}
                        orgId={selectedOrgId}
                        org={orgs.find((org) => org.id === selectedOrgId)}
                        members={orgMembers[selectedOrgId] || []}
                        selectedUsers={new Set(selectedUsersByOrg[selectedOrgId] || [])}
                        isMembersLoading={membersLoading[selectedOrgId] === true}
                        onToggleSelectAllUsers={onToggleSelectAllUsers}
                        onToggleUserSelection={onToggleUserSelection}
                    />
                ))}
            </div>
        </div>
    )
}

function SystemTemplateLoadError({
    isRetrying,
    onBack,
    onRetry,
}: {
    isRetrying: boolean
    onBack: () => void
    onRetry: () => void
}) {
    return (
        <div className="flex min-h-[60vh] items-center justify-center p-6">
            <Card className="w-full max-w-lg">
                <CardHeader>
                    <CardTitle>System template unavailable</CardTitle>
                    <CardDescription>
                        The editor could not retrieve this system template.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Alert variant="destructive">
                        <AlertTriangleIcon aria-hidden="true" />
                        <AlertTitle>Unable to load system template</AlertTitle>
                        <AlertDescription>
                            Check your connection and platform access, then try loading the template
                            again.
                        </AlertDescription>
                    </Alert>
                    <div className="flex flex-wrap gap-2">
                        <Button type="button" variant="outline" onClick={onBack}>
                            <ArrowLeftIcon aria-hidden="true" />
                            Back to templates
                        </Button>
                        <Button type="button" disabled={isRetrying} onClick={onRetry}>
                            {isRetrying ? (
                                <>
                                    <Loader2Icon className="animate-spin" aria-hidden="true" />
                                    Retrying&hellip;
                                </>
                            ) : (
                                "Retry"
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

export default function PlatformSystemEmailTemplatePage() {
    const { push } = useRouter()
    const params = useParams()
    const systemKey = params?.systemKey as string
    const isOrgInvite = systemKey === "org_invite"

    const {
        data: template,
        isFetching: templateFetching,
        isLoading,
        refetch: refetchTemplate,
    } = usePlatformSystemEmailTemplate(systemKey)
    const { data: templateVariables = [], isLoading: variablesLoading } = usePlatformSystemEmailTemplateVariables(systemKey)
    const { data: branding } = usePlatformEmailBranding()
    const updateTemplate = useUpdatePlatformSystemEmailTemplate()
    const updateBranding = useUpdatePlatformEmailBranding()
    const uploadBrandingLogo = useUploadPlatformEmailBrandingLogo()
    const deleteTemplate = useDeletePlatformSystemEmailTemplate()
    const sendTest = useSendTestPlatformSystemEmailTemplate()
    const sendCampaign = useSendPlatformSystemEmailCampaign()

    const [templateDraftOverride, setTemplateDraftOverride] = useState<{
        systemKey: string
        draft: TemplateDraft
    } | null>(null)
    const [view, setView] = useState<EditorView>("edit")
    // Remounts the block editor when the body is replaced outside it (save, reset, layout).
    const [editorGeneration, setEditorGeneration] = useState(0)
    const [logoUrlOverride, setLogoUrlOverride] = useState<string | null>(null)
    const [testEmail, setTestEmail] = useState("")
    const [testOrgId, setTestOrgId] = useState("")
    const [saving, setSaving] = useState(false)
    const [saveResult, setSaveResult] = useState<"idle" | "saved" | "error">("idle")
    const [sending, setSending] = useState(false)
    const [brandingSaving, setBrandingSaving] = useState(false)
    const [campaignOpen, setCampaignOpen] = useState(false)
    const [campaignConfirmOpen, setCampaignConfirmOpen] = useState(false)
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const {
        agencies: orgs,
        isLoading: orgsLoading,
        isError: orgsError,
        defaultAgencyId,
    } = useTestSendAgencies()
    const [orgSearch, setOrgSearch] = useState("")
    const [selectedOrgIds, setSelectedOrgIds] = useState<string[]>([])
    const [orgMembers, setOrgMembers] = useState<Record<string, OrgMember[]>>({})
    const [membersLoading, setMembersLoading] = useState<Record<string, boolean>>({})
    const [selectedUsersByOrg, setSelectedUsersByOrg] = useState<Record<string, string[]>>({})
    const [campaignSending, setCampaignSending] = useState(false)
    const [campaignFailureSummary, setCampaignFailureSummary] = useState<string | null>(null)
    const logoFileInputRef = useRef<HTMLInputElement | null>(null)
    const testSendCardRef = useRef<HTMLFormElement | null>(null)
    const testSendOccurrenceIdRef = useRef<string | null>(null)
    const campaignOccurrenceIdRef = useRef<string | null>(null)

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const designRef = useRef<EmailDesignEditorHandle | null>(null)
    const activeInsertionTargetRef = useRef<ActiveInsertionTarget>(null)
    const currentVersionRef = useRef<{ systemKey: string; version: number | null } | null>(null)

    const setActiveInsertionTarget = (target: ActiveInsertionTarget) => {
        activeInsertionTargetRef.current = target
    }

    const sourceDraft = buildTemplateDraft(template)
    const draft =
        templateDraftOverride?.systemKey === systemKey ? templateDraftOverride.draft : sourceDraft
    const subject = draft.subject
    const fromEmail = draft.fromEmail
    const body = draft.body
    const bodyDesign = draft.bodyDesign
    const isActive = draft.isActive

    const updateDraft = (updater: (current: TemplateDraft) => TemplateDraft) => {
        setTemplateDraftOverride((current) => {
            const base = current?.systemKey === systemKey ? current.draft : sourceDraft
            return { systemKey, draft: updater(base) }
        })
    }

    const setSubject: Dispatch<SetStateAction<string>> = (value) => {
        updateDraft((current) => ({
            ...current,
            subject: typeof value === "function" ? value(current.subject) : value,
        }))
    }

    const setFromEmail = (value: string) => {
        updateDraft((current) => ({ ...current, fromEmail: value }))
    }

    const setBody = (value: EmailBodyValue) => {
        if (value.body === body && value.bodyDesign === bodyDesign) return
        updateDraft((current) => ({ ...current, body: value.body, bodyDesign: value.bodyDesign }))
    }

    const setIsActive = (value: boolean) => {
        updateDraft((current) => ({ ...current, isActive: value }))
    }

    const logoUrl = logoUrlOverride ?? branding?.logo_url ?? ""
    const setLogoUrl = (value: string) => setLogoUrlOverride(value)

    const canValidateVariables = !variablesLoading && templateVariables.length > 0
    const allowedVariableNames = new Set(templateVariables.map((variable) => variable.name))
    const requiredVariableNames: string[] = []
    for (const variable of templateVariables) {
        if (variable.required) {
            requiredVariableNames.push(variable.name)
        }
    }
    const usedVariableNames = extractTemplateVariables(`${subject}\n${body}`)
    const usedVariableNamesSet = new Set(usedVariableNames)
    const unknownVariables = canValidateVariables
        ? usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
        : []
    const missingRequiredVariables = canValidateVariables
        ? requiredVariableNames.filter((variable) => !usedVariableNamesSet.has(variable))
        : []
    const fromEmailError = getFromEmailError(fromEmail)
    const logoPreviewUrl = getLogoPreviewUrl(logoUrl)
    const isDirty =
        subject !== sourceDraft.subject ||
        fromEmail !== sourceDraft.fromEmail ||
        body !== sourceDraft.body ||
        bodyDesign !== sourceDraft.bodyDesign ||
        isActive !== sourceDraft.isActive
    const saveStatus: SaveStatusState = saving
        ? "saving"
        : saveResult === "error"
          ? "error"
          : saveResult === "saved" && !isDirty
            ? "saved"
            : "idle"

    // With exactly one agency, test sends default to it.
    const effectiveTestOrgId = testOrgId || defaultAgencyId
    const testSendValidation = useFormValidation({
        values: { agency: effectiveTestOrgId, email: testEmail },
        validate: (values) => ({
            agency: validateRequired(values.agency, "Select an agency."),
            email: validateEmail(values.email, { requiredMessage: "Enter a test email." }),
        }),
    })

    const focusTestSend = () => {
        setView("edit")
        requestAnimationFrame(() => {
            const form = testSendCardRef.current
            if (!form) return
            form.scrollIntoView({ behavior: "smooth", block: "nearest" })
            form.querySelector<HTMLElement>("button, input")?.focus({ preventScroll: true })
        })
    }

    const handleCampaignOpenChange = (open: boolean) => {
        setCampaignOpen(open)
        if (open) {
            campaignOccurrenceIdRef.current = createCampaignOccurrenceId()
            setCampaignFailureSummary(null)
        }
    }

    const ensureMembersLoaded = async (orgId: string) => {
        if (orgMembers[orgId] || membersLoading[orgId]) return
        setMembersLoading((prev) => ({ ...prev, [orgId]: true }))
        const finishLoading = () => setMembersLoading((prev) => ({ ...prev, [orgId]: false }))
        try {
            const members = await listMembers(orgId)
            setOrgMembers((prev) => ({ ...prev, [orgId]: members }))
            const activeIds: string[] = []
            for (const member of members) {
                if (member.is_active) {
                    activeIds.push(member.user_id)
                }
            }
            setSelectedUsersByOrg((prev) => ({ ...prev, [orgId]: activeIds }))
            finishLoading()
        } catch {
            toast.error("Failed to load org members")
            finishLoading()
        }
    }

    const toggleOrg = (orgId: string, next: boolean) => {
        if (next) {
            setSelectedOrgIds((prev) => (
                prev.includes(orgId) ? prev : [...prev, orgId]
            ))
            void ensureMembersLoaded(orgId)
            return
        }

        setSelectedOrgIds((prev) => prev.filter((id) => id !== orgId))
        setSelectedUsersByOrg((prev) => {
            const nextUsers = { ...prev }
            delete nextUsers[orgId]
            return nextUsers
        })
    }

    const toggleSelectAllUsers = (orgId: string, next: boolean) => {
        const members = orgMembers[orgId] || []
        const activeIds: string[] = []
        for (const member of members) {
            if (member.is_active) {
                activeIds.push(member.user_id)
            }
        }
        setSelectedUsersByOrg((prev) => ({ ...prev, [orgId]: next ? activeIds : [] }))
    }

    const toggleUserSelection = (orgId: string, userId: string, next: boolean) => {
        setSelectedUsersByOrg((prev) => {
            const current = new Set(prev[orgId] ?? [])
            if (next) {
                current.add(userId)
            } else {
                current.delete(userId)
            }
            return { ...prev, [orgId]: Array.from(current) }
        })
    }

    const orgSearchQuery = orgSearch.trim().toLowerCase()
    const filteredOrgs = orgSearchQuery
        ? orgs.filter(
              (org) =>
                  org.name.toLowerCase().includes(orgSearchQuery) ||
                  org.slug.toLowerCase().includes(orgSearchQuery)
          )
        : orgs

    const selectedOrgSet = new Set(selectedOrgIds)
    const allFilteredSelected = filteredOrgs.length > 0 && filteredOrgs.every((org) => selectedOrgSet.has(org.id))

    const toggleSelectAllOrgs = () => {
        const filteredIds = filteredOrgs.map((org) => org.id)
        const filteredSet = new Set(filteredIds)
        if (allFilteredSelected) {
            setSelectedOrgIds((prev) => prev.filter((id) => !filteredSet.has(id)))
            setSelectedUsersByOrg((prev) => {
                const copy = { ...prev }
                filteredIds.forEach((id) => {
                    delete copy[id]
                })
                return copy
            })
            return
        }
        setSelectedOrgIds((prev) => Array.from(new Set([...prev, ...filteredIds])))
        filteredIds.forEach((orgId) => {
            void ensureMembersLoaded(orgId)
        })
    }

    const campaignTargets: Array<{ org_id: string; user_ids: string[] }> = []
    for (const orgId of selectedOrgIds) {
        const userIds = selectedUsersByOrg[orgId] ?? []
        if (userIds.length > 0) {
            campaignTargets.push({ org_id: orgId, user_ids: userIds })
        }
    }
    const totalSelectedUsers = campaignTargets.reduce((acc, target) => acc + target.user_ids.length, 0)
    const campaignOrgCount = campaignTargets.length

    const insertToken = (token: string) => {
        if (activeInsertionTargetRef.current === "subject") {
            insertIntoTextControl(subjectRef.current, subjectSelectionRef, setSubject, token)
            return
        }
        designRef.current?.insertText(token)
    }

    // The server expands {{platform_logo_block}} to the branding logo image.
    const insertPlatformLogo = () => {
        if (body.includes("{{platform_logo_block}}")) return
        designRef.current?.insertText("{{platform_logo_block}}")
        setActiveInsertionTarget("body")
    }

    const applySfTemplate = () => {
        updateDraft((current) => ({
            ...current,
            subject: SF_INVITE_SUBJECT,
            body: SF_INVITE_BODY,
            bodyDesign: null,
        }))
        setEditorGeneration((generation) => generation + 1)
    }

    const handleSave = async () => {
        if (!subject.trim()) {
            toast.error("Subject is required")
            return
        }
        if (!body.trim()) {
            toast.error("Email body is required")
            return
        }
        if (fromEmailError) {
            toast.error(fromEmailError)
            return
        }

        setSaving(true)
        const finishSaving = () => setSaving(false)
        try {
            const expectedVersion =
                currentVersionRef.current?.systemKey === systemKey
                    ? currentVersionRef.current.version
                    : template?.current_version ?? null
            const payload: {
                subject: string
                body: string
                body_design: EmailBodyDesign | null
                is_active: boolean
                from_email: string | null
                expected_version?: number
            } = {
                subject: subject.trim(),
                body,
                body_design: bodyDesign,
                is_active: isActive,
                from_email: fromEmail.trim() ? fromEmail.trim() : null,
            }
            if (expectedVersion !== null) {
                payload.expected_version = expectedVersion
            }
            const updated = await updateTemplate.mutateAsync({
                systemKey,
                payload,
            })
            currentVersionRef.current = { systemKey, version: updated.current_version }
            testSendOccurrenceIdRef.current = null
            // Show the saved (server-sanitized) content; the refetched template then matches it.
            setTemplateDraftOverride({ systemKey, draft: buildTemplateDraft(updated) })
            if (updated.body !== body) setEditorGeneration((generation) => generation + 1)
            setSaveResult("saved")
            toast.success("System template updated")
            finishSaving()
        } catch (error) {
            setSaveResult("error")
            const message = getActionErrorMessage(error, "Couldn't save template.")
            if (message) toast.error(message)
            finishSaving()
        }
    }

    const isBuiltinTemplate = template?.is_builtin ?? false

    // Built-in keys are recreated from defaults on the next read, so deleting one resets it.
    const handleDeleteTemplate = async () => {
        await deleteTemplate.mutateAsync({ systemKey })
        if (isBuiltinTemplate) {
            setTemplateDraftOverride(null)
            setSaveResult("idle")
            currentVersionRef.current = null
            toast.success("System template reset to default")
            await refetchTemplate()
            setEditorGeneration((generation) => generation + 1)
            return
        }
        toast.success("System template deleted")
        push("/ops/templates?tab=system")
    }

    const handleSaveBranding = async () => {
        setBrandingSaving(true)
        const finishSaving = () => setBrandingSaving(false)
        try {
            await updateBranding.mutateAsync({
                logo_url: logoUrl.trim() ? logoUrl.trim() : null,
            })
            toast.success("Platform branding updated")
            finishSaving()
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't update branding.")
            if (message) toast.error(message)
            finishSaving()
        }
    }

    const handleLogoUpload = async (event: ChangeEvent<HTMLInputElement>) => {
        const input = event.currentTarget
        const file = input.files?.[0]
        if (!file) return

        const allowedTypes = ["image/png", "image/jpeg"]
        if (!allowedTypes.includes(file.type)) {
            toast.error("Logo must be a PNG or JPEG file")
            input.value = ""
            return
        }
        if (file.size > 1024 * 1024) {
            toast.error("Logo must be less than 1MB")
            input.value = ""
            return
        }

        const clearInput = () => {
            input.value = ""
        }
        try {
            const result = await uploadBrandingLogo.mutateAsync(file)
            setLogoUrl(result.logo_url ?? "")
            toast.success("Logo uploaded")
            clearInput()
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't upload logo.")
            if (message) toast.error(message)
            clearInput()
        }
    }

    const handleSendTest = async (values: { agency: string; email: string }) => {
        setSending(true)
        const finishSending = () => setSending(false)
        try {
            const testSendOccurrenceId =
                testSendOccurrenceIdRef.current ?? createCampaignOccurrenceId()
            testSendOccurrenceIdRef.current = testSendOccurrenceId
            const result = await sendTest.mutateAsync({
                systemKey,
                payload: {
                    to_email: values.email.trim(),
                    org_id: values.agency,
                    idempotency_key: testSendOccurrenceId,
                },
            })
            if (!result.queued) {
                toast.error("Test email was not durably queued")
                finishSending()
                return
            }
            testSendOccurrenceIdRef.current = null
            toast.success("Test email queued")
            finishSending()
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't send test email.")
            if (message) toast.error(message)
            finishSending()
        }
    }

    const handleSendCampaign = async () => {
        const targets = campaignTargets
        if (targets.length === 0) return

        setCampaignSending(true)
        const finishSending = () => setCampaignSending(false)
        try {
            const campaignOccurrenceId =
                campaignOccurrenceIdRef.current ?? createCampaignOccurrenceId()
            campaignOccurrenceIdRef.current = campaignOccurrenceId
            const result = await sendCampaign.mutateAsync({
                systemKey,
                payload: {
                    campaign_occurrence_id: campaignOccurrenceId,
                    targets,
                },
            })
            if (result.failed > 0) {
                const recipientLabel = result.failed === 1 ? "recipient" : "recipients"
                setCampaignFailureSummary(
                    `${result.failed} ${recipientLabel} could not be queued. Review the selected recipients, then retry this campaign.`
                )
                toast.error(
                    "Campaign partially queued. Review the selected recipients and retry."
                )
                finishSending()
                return
            }
            setCampaignFailureSummary(null)
            toast.success(
                `Campaign queued: ${result.queued} queued, ${result.suppressed} suppressed, ${result.failed} failed`
            )
            setCampaignOpen(false)
            finishSending()
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't send campaign.")
            if (message) toast.error(message)
            finishSending()
        }
    }

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-10">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!template) {
        return (
            <SystemTemplateLoadError
                isRetrying={templateFetching}
                onBack={() => push("/ops/templates?tab=system")}
                onRetry={() => {
                    void refetchTemplate()
                }}
            />
        )
    }

    const headerBusy = deleteTemplate.isPending || saving || sending || brandingSaving || campaignSending

    return (
        <Tabs value={view} onValueChange={(value) => setView(value as EditorView)} className="gap-0">
            {isBuiltinTemplate ? (
                <ConfirmDialog
                    open={showDeleteDialog}
                    onOpenChange={setShowDeleteDialog}
                    title={`Reset ${template.name} to default?`}
                    description="Your changes to the subject, sender and body are replaced with the built-in content."
                    confirmLabel="Reset to default"
                    confirmVariant="default"
                    errorFallback="Couldn't reset template."
                    onConfirm={handleDeleteTemplate}
                />
            ) : (
                <ConfirmDialog
                    open={showDeleteDialog}
                    onOpenChange={setShowDeleteDialog}
                    title={`Delete ${template.name}?`}
                    description="This system email is removed for every organization."
                    confirmLabel="Delete"
                    errorFallback="Couldn't delete template."
                    onConfirm={handleDeleteTemplate}
                />
            )}

            <PageHeader
                title={template.name}
                back={{ href: "/ops/templates?tab=system", label: "Back to templates" }}
                sticky
                className="top-14"
                meta={
                    <>
                        <Badge variant="outline" className="font-mono text-xs font-normal">
                            {template.system_key}
                        </Badge>
                        <SaveStatus state={saveStatus} />
                    </>
                }
                actions={
                    <>
                        <TabsList aria-label="Editor view">
                            <TabsTrigger value="edit">Edit</TabsTrigger>
                            <TabsTrigger value="preview">Preview</TabsTrigger>
                            <TabsTrigger value="html">HTML</TabsTrigger>
                        </TabsList>
                        <DropdownMenu>
                            <DropdownMenuTrigger
                                render={<Button variant="outline" size="icon" aria-label="More actions" />}
                                disabled={headerBusy}
                            >
                                <MoreHorizontalIcon aria-hidden="true" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={focusTestSend}>
                                    <SendIcon aria-hidden="true" />
                                    Send test
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleCampaignOpenChange(true)}>
                                    <UsersIcon aria-hidden="true" />
                                    Send campaign
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {isBuiltinTemplate ? (
                                    <DropdownMenuItem onClick={() => setShowDeleteDialog(true)}>
                                        <RotateCcwIcon aria-hidden="true" />
                                        Reset to default
                                    </DropdownMenuItem>
                                ) : (
                                    <DropdownMenuItem
                                        variant="destructive"
                                        onClick={() => setShowDeleteDialog(true)}
                                    >
                                        <Trash2Icon aria-hidden="true" />
                                        Delete
                                    </DropdownMenuItem>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                        <Button onClick={handleSave} disabled={saving}>
                            {saving ? (
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                            ) : (
                                <SaveIcon className="size-4" aria-hidden="true" />
                            )}
                            Save
                        </Button>
                    </>
                }
            />

                    <Dialog open={campaignOpen} onOpenChange={handleCampaignOpenChange}>
                        <DialogContent size="3xl">
                            <DialogHeader>
                                <DialogTitle>Send campaign</DialogTitle>
                                <DialogDescription>
                                    Send the <span className="font-medium">{template.name}</span> system email to selected users.
                                    Unsubscribe headers are included automatically.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4">
                                {campaignFailureSummary ? (
                                    <Alert variant="destructive">
                                        <AlertTriangleIcon aria-hidden="true" />
                                        <AlertTitle>Campaign needs attention</AlertTitle>
                                        <AlertDescription>
                                            {campaignFailureSummary}
                                        </AlertDescription>
                                    </Alert>
                                ) : null}
                                <div className="space-y-2">
                                    <Label>Organizations</Label>
                                    <div className="relative">
                                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            placeholder="Search organizations..."
                                            value={orgSearch}
                                            onChange={(event) => setOrgSearch(event.target.value)}
                                            className="pl-9"
                                        />
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <Label className="flex items-center gap-2">
                                            <Checkbox
                                                checked={allFilteredSelected}
                                                onCheckedChange={() => toggleSelectAllOrgs()}
                                            />
                                            Select all
                                        </Label>
                                        <span className="text-muted-foreground">
                                            {selectedOrgIds.length} selected
                                        </span>
                                    </div>
                                    <div className="rounded-lg border">
                                        <ScrollArea className="h-48">
                                            {orgsLoading ? (
                                                <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                                                    <Loader2Icon className="size-4 animate-spin" />
                                                    Loading organizations&hellip;
                                                </div>
                                            ) : orgsError ? (
                                                <div className="p-4 text-sm text-destructive">
                                                    Couldn&apos;t load organizations.
                                                </div>
                                            ) : filteredOrgs.length === 0 ? (
                                                <div className="p-4 text-sm text-muted-foreground">
                                                    No organizations match your search.
                                                </div>
                                            ) : (
                                                <div className="divide-y">
                                                    {filteredOrgs.map((org) => {
                                                        const checked = selectedOrgSet.has(org.id)
                                                        return (
                                                            <label
                                                                key={org.id}
                                                                className="flex items-center justify-between gap-3 p-3 text-sm hover:bg-muted/50"
                                                            >
                                                                <div className="flex items-center gap-3">
                                                                    <Checkbox
                                                                        checked={checked}
                                                                        onCheckedChange={(next) =>
                                                                            toggleOrg(org.id, next === true)
                                                                        }
                                                                    />
                                                                    <div>
                                                                        <div className="font-medium text-foreground">
                                                                            {org.name}
                                                                        </div>
                                                                        <div className="text-xs text-muted-foreground">
                                                                            {org.slug}
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                                <Badge variant="outline" className="text-xs">
                                                                    {getSubscriptionPlanLabel(org.subscription_plan)}
                                                                </Badge>
                                                            </label>
                                                        )
                                                    })}
                                                </div>
                                            )}
                                        </ScrollArea>
                                    </div>
                                </div>

                                <SystemTemplateCampaignRecipients
                                    selectedOrgIds={selectedOrgIds}
                                    orgs={orgs}
                                    orgMembers={orgMembers}
                                    membersLoading={membersLoading}
                                    selectedUsersByOrg={selectedUsersByOrg}
                                    onToggleSelectAllUsers={toggleSelectAllUsers}
                                    onToggleUserSelection={toggleUserSelection}
                                />
                            </div>
                            <DialogFooter className="flex flex-col gap-2 sm:flex-row sm:justify-between">
                                <span className="text-xs text-muted-foreground">
                                    {totalSelectedUsers} {totalSelectedUsers === 1 ? "recipient" : "recipients"} selected
                                </span>
                                <div className="flex gap-2">
                                    <Button variant="outline" onClick={() => setCampaignOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        onClick={() => setCampaignConfirmOpen(true)}
                                        disabled={campaignSending || totalSelectedUsers === 0}
                                    >
                                        {campaignSending && <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />}
                                        Send campaign
                                    </Button>
                                </div>
                            </DialogFooter>
                            <ConfirmDialog
                                open={campaignConfirmOpen}
                                onOpenChange={setCampaignConfirmOpen}
                                title={`Send to ${campaignOrgCount} ${campaignOrgCount === 1 ? "organization" : "organizations"}?`}
                                description={`${template.name} is sent to ${totalSelectedUsers} ${totalSelectedUsers === 1 ? "recipient" : "recipients"}.`}
                                confirmLabel="Send campaign"
                                confirmVariant="default"
                                confirmIcon={<SendIcon aria-hidden="true" />}
                                errorFallback="Couldn't send campaign."
                                onConfirm={handleSendCampaign}
                            />
                        </DialogContent>
                    </Dialog>

            <TabsContent value="edit" keepMounted className="mt-0 flex min-h-[calc(100dvh-8rem)] flex-col data-hidden:hidden">
                <EmailDesignEditor
                    key={`${systemKey}:${editorGeneration}`}
                    ref={designRef}
                    initialValue={{ body, bodyDesign }}
                    onChange={setBody}
                    variables={templateVariables}
                    onSelectVariable={(variable) => insertToken(`{{${variable.name}}}`)}
                    onFocus={() => setActiveInsertionTarget("body")}
                    fields={
                        <div className="grid gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="from-email">From (required for Resend)</Label>
                                <Input
                                    id="from-email"
                                    value={fromEmail}
                                    onChange={(event) => setFromEmail(event.target.value)}
                                    placeholder="Invites <welcome@surrogacyforce.com>"
                                />
                                {fromEmailError ? (
                                    <p className="text-xs text-destructive">{fromEmailError}</p>
                                ) : (
                                    <p className="text-xs text-muted-foreground">
                                        Must be a verified sender in Resend.
                                    </p>
                                )}
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="subject">Subject</Label>
                                <Input
                                    id="subject"
                                    ref={subjectRef}
                                    value={subject}
                                    onChange={(event) => setSubject(event.target.value)}
                                    onFocus={(event) => {
                                        setActiveInsertionTarget("subject")
                                        recordSelection(event.currentTarget, subjectSelectionRef)
                                    }}
                                    onKeyUp={(event) => recordSelection(event.currentTarget, subjectSelectionRef)}
                                    onMouseUp={(event) => recordSelection(event.currentTarget, subjectSelectionRef)}
                                    onSelect={(event) => recordSelection(event.currentTarget, subjectSelectionRef)}
                                    placeholder="Invitation to join {{org_name}}"
                                />
                            </div>
                            {(unknownVariables.length > 0 || missingRequiredVariables.length > 0) &&
                                (subject.trim() || body.trim()) && (
                                    <Alert className="border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-50">
                                        <AlertTriangleIcon className="size-4" />
                                        <AlertTitle>Template variables</AlertTitle>
                                        <AlertDescription className="text-amber-800 dark:text-amber-100">
                                            {unknownVariables.length > 0 && (
                                                <p>
                                                    Unknown:{" "}
                                                    <span className="font-mono">
                                                        {unknownVariables.map((v) => `{{${v}}}`).join(", ")}
                                                    </span>
                                                </p>
                                            )}
                                            {missingRequiredVariables.length > 0 && (
                                                <p>
                                                    Missing required:{" "}
                                                    <span className="font-mono">
                                                        {missingRequiredVariables.map((v) => `{{${v}}}`).join(", ")}
                                                    </span>
                                                </p>
                                            )}
                                        </AlertDescription>
                                    </Alert>
                                )}
                        </div>
                    }
                    settings={
                        <div className="grid gap-5">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <Label htmlFor="template-active" className="text-sm">
                                        Template active
                                    </Label>
                                    <p className="text-xs text-muted-foreground">
                                        If disabled, system emails fall back to the default template.
                                    </p>
                                </div>
                                <Switch id="template-active" checked={isActive} onCheckedChange={setIsActive} />
                            </div>
                            <div className="grid gap-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    disabled={body.includes("{{platform_logo_block}}")}
                                    onClick={insertPlatformLogo}
                                >
                                    <ImageIcon aria-hidden="true" />
                                    Insert logo
                                </Button>
                                {isOrgInvite ? (
                                    <Button type="button" variant="outline" size="sm" onClick={applySfTemplate}>
                                        <LayoutTemplateIcon aria-hidden="true" />
                                        Use SF-style layout
                                    </Button>
                                ) : null}
                            </div>

                            <section aria-labelledby="platform-branding-heading" className="grid gap-3">
                                <h2 id="platform-branding-heading" className="text-sm font-medium">
                                    Platform branding
                                </h2>
                                <div className="flex items-center gap-3">
                                    {logoPreviewUrl ? (
                                        <Image
                                            src={logoPreviewUrl}
                                            alt="Platform logo"
                                            className="h-12 w-auto rounded border object-contain"
                                            width={96}
                                            height={48}
                                            unoptimized
                                        />
                                    ) : (
                                        <div className="flex h-12 w-24 items-center justify-center rounded border border-dashed text-xs text-muted-foreground">
                                            No logo
                                        </div>
                                    )}
                                    <div>
                                        <input
                                            id="platform-branding-logo-upload"
                                            aria-label="Platform branding logo upload"
                                            name="platform_branding_logo_upload"
                                            type="file"
                                            ref={logoFileInputRef}
                                            onChange={handleLogoUpload}
                                            accept="image/png,image/jpeg"
                                            className="hidden"
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => logoFileInputRef.current?.click()}
                                            disabled={uploadBrandingLogo.isPending}
                                        >
                                            {uploadBrandingLogo.isPending ? (
                                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                            ) : (
                                                <UploadIcon className="size-4" aria-hidden="true" />
                                            )}
                                            Upload logo
                                        </Button>
                                        <p className="mt-1 text-xs text-muted-foreground">Max 200x80px, PNG/JPG</p>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="platform-logo">Logo URL</Label>
                                    <Input
                                        id="platform-logo"
                                        value={logoUrl}
                                        onChange={(event) => setLogoUrl(event.target.value)}
                                        placeholder="https://cdn.surrogacyforce.com/logo.png"
                                    />
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={handleSaveBranding}
                                    disabled={brandingSaving}
                                >
                                    {brandingSaving ? (
                                        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                    ) : null}
                                    Save branding
                                </Button>
                            </section>

                            <section aria-labelledby="send-test-heading" className="grid gap-3">
                                <h2 id="send-test-heading" className="text-sm font-medium">
                                    Send test email
                                </h2>
                                <form
                                    ref={testSendCardRef}
                                    noValidate
                                    onSubmit={testSendValidation.handleSubmit(handleSendTest)}
                                    className="space-y-3"
                                >
                                    <ValidatedField
                                        id="test-agency"
                                        label="Agency"
                                        error={testSendValidation.errorFor("agency")}
                                    >
                                        {(control) => (
                                            <TestSendAgencySelect
                                                id={control.id}
                                                agencies={orgs}
                                                isLoading={orgsLoading}
                                                isError={orgsError}
                                                value={effectiveTestOrgId}
                                                onValueChange={(value) => {
                                                    testSendOccurrenceIdRef.current = null
                                                    setTestOrgId(value)
                                                    testSendValidation.touch("agency")
                                                }}
                                                invalid={control["aria-invalid"] === true}
                                                describedBy={control["aria-describedby"]}
                                            />
                                        )}
                                    </ValidatedField>
                                    <ValidatedField
                                        id="test-email"
                                        label="Test email"
                                        error={testSendValidation.errorFor("email")}
                                    >
                                        {(control) => (
                                            <Input
                                                {...control}
                                                type="email"
                                                value={testEmail}
                                                onChange={(event) => {
                                                    testSendOccurrenceIdRef.current = null
                                                    setTestEmail(event.target.value)
                                                }}
                                                onBlur={() => testSendValidation.touch("email")}
                                                placeholder="test@example.com"
                                            />
                                        )}
                                    </ValidatedField>
                                    <Button type="submit" disabled={sending}>
                                        {sending ? (
                                            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                        ) : (
                                            <SendIcon className="size-4" aria-hidden="true" />
                                        )}
                                        Send test
                                    </Button>
                                </form>
                            </section>
                        </div>
                    }
                />
            </TabsContent>
            <TabsContent value="preview" className="mt-0 flex min-h-[calc(100dvh-8rem)] flex-col">
                <EmailPreviewPane
                    subject={subject}
                    body={body}
                    queryKey={["platform-system", systemKey, effectiveTestOrgId]}
                    modes={["sample", "names"]}
                    load={(request) =>
                        previewPlatformSystemEmailTemplate({
                            subject: request.subject,
                            body: request.body,
                            variable_mode: request.variableMode === "names" ? "names" : "sample",
                            org_id: effectiveTestOrgId || null,
                        })
                    }
                />
            </TabsContent>
            <TabsContent value="html" className="mt-0 min-h-[calc(100dvh-8rem)] bg-muted/40 p-4 sm:p-6">
                <EmailHtmlSource html={body} />
            </TabsContent>
        </Tabs>
    )
}
