"use client"

import { type ChangeEvent, useEffect, useMemo, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useParams, useRouter } from "next/navigation"
import DOMPurify from "dompurify"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
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
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Badge } from "@/components/ui/badge"
import {
    AlertTriangleIcon,
    ArrowLeftIcon,
    EyeIcon,
    Loader2Icon,
    SaveIcon,
    SearchIcon,
    SendIcon,
    Trash2Icon,
    UploadIcon,
    UsersIcon,
} from "lucide-react"
import { toast } from "sonner"
import { TemplateVariablePicker } from "@/components/email/TemplateVariablePicker"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { RichTextEditor, type RichTextEditorHandle } from "@/components/rich-text-editor"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { insertAtCursor } from "@/lib/insert-at-cursor"
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
    listOrganizations,
    listMembers,
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

type EditorMode = "visual" | "html"

type ActiveInsertionTarget = "subject" | "body_html" | "body_visual" | null

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

export default function PlatformSystemEmailTemplatePage() {
    const router = useRouter()
    const params = useParams()
    const systemKey = params?.systemKey as string
    const isOrgInvite = systemKey === "org_invite"

    const { data: template, isLoading } = usePlatformSystemEmailTemplate(systemKey)
    const { data: templateVariables = [], isLoading: variablesLoading } = usePlatformSystemEmailTemplateVariables(systemKey)
    const { data: branding } = usePlatformEmailBranding()
    const updateTemplate = useUpdatePlatformSystemEmailTemplate()
    const updateBranding = useUpdatePlatformEmailBranding()
    const uploadBrandingLogo = useUploadPlatformEmailBrandingLogo()
    const deleteTemplate = useDeletePlatformSystemEmailTemplate()
    const sendTest = useSendTestPlatformSystemEmailTemplate()
    const sendCampaign = useSendPlatformSystemEmailCampaign()

    const [subject, setSubject] = useState("")
    const [fromEmail, setFromEmail] = useState("")
    const [body, setBody] = useState("")
    const [isActive, setIsActive] = useState(true)
    const [currentVersion, setCurrentVersion] = useState<number | null>(null)
    const [editorMode, setEditorMode] = useState<EditorMode>("visual")
    const [editorModeTouched, setEditorModeTouched] = useState(false)
    const [logoUrl, setLogoUrl] = useState("")
    const [testEmail, setTestEmail] = useState("")
    const [testOrgId, setTestOrgId] = useState("")
    const [saving, setSaving] = useState(false)
    const [sending, setSending] = useState(false)
    const [brandingSaving, setBrandingSaving] = useState(false)
    const [campaignOpen, setCampaignOpen] = useState(false)
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const [orgs, setOrgs] = useState<OrganizationSummary[]>([])
    const [orgsLoading, setOrgsLoading] = useState(false)
    const [orgSearch, setOrgSearch] = useState("")
    const [selectedOrgIds, setSelectedOrgIds] = useState<string[]>([])
    const [orgMembers, setOrgMembers] = useState<Record<string, OrgMember[]>>({})
    const [membersLoading, setMembersLoading] = useState<Record<string, boolean>>({})
    const [selectedUsersByOrg, setSelectedUsersByOrg] = useState<Record<string, string[]>>({})
    const [campaignSending, setCampaignSending] = useState(false)
    const logoFileInputRef = useRef<HTMLInputElement | null>(null)

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const htmlBodyRef = useRef<HTMLTextAreaElement | null>(null)
    const htmlBodySelectionRef = useRef<{ start: number; end: number } | null>(null)
    const visualBodyRef = useRef<RichTextEditorHandle | null>(null)
    const [activeInsertionTarget, setActiveInsertionTarget] = useState<ActiveInsertionTarget>(null)

    const canValidateVariables = !variablesLoading && templateVariables.length > 0
    const allowedVariableNames = useMemo(
        () => new Set(templateVariables.map((variable) => variable.name)),
        [templateVariables]
    )
    const requiredVariableNames = useMemo(
        () => templateVariables.filter((variable) => variable.required).map((variable) => variable.name),
        [templateVariables]
    )
    const usedVariableNames = useMemo(
        () => extractTemplateVariables(`${subject}\n${body}`),
        [subject, body]
    )
    const unknownVariables = useMemo(() => {
        if (!canValidateVariables) return []
        return usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
    }, [allowedVariableNames, canValidateVariables, usedVariableNames])
    const missingRequiredVariables = useMemo(() => {
        if (!canValidateVariables) return []
        return requiredVariableNames.filter((variable) => !usedVariableNames.includes(variable))
    }, [canValidateVariables, requiredVariableNames, usedVariableNames])

    const recordSelection = (
        el: HTMLInputElement | HTMLTextAreaElement,
        ref: MutableRefObject<{ start: number; end: number } | null>
    ) => {
        ref.current = {
            start: el.selectionStart ?? el.value.length,
            end: el.selectionEnd ?? el.value.length,
        }
    }

    const fromEmailError = useMemo(() => {
        const value = fromEmail.trim()
        if (!value) return null
        const basicEmail = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/
        const namedEmail = /^.+<\s*[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+\s*>$/
        if (basicEmail.test(value) || namedEmail.test(value)) return null
        return "Use a valid email or name <email@domain> format."
    }, [fromEmail])

    useEffect(() => {
        if (!template) return
        setSubject(template.subject ?? "")
        setFromEmail(template.from_email ?? "")
        setBody(template.body ?? "")
        setIsActive(template.is_active)
        setCurrentVersion(template.current_version)
    }, [template])

    useEffect(() => {
        if (!branding) return
        setLogoUrl(branding.logo_url ?? "")
    }, [branding])

    const logoPreviewUrl = useMemo(() => {
        if (!logoUrl) return ""
        if (logoUrl.startsWith("/platform/email/branding/logo/local/")) {
            const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "")
            return base ? `${base}${logoUrl}` : logoUrl
        }
        return logoUrl
    }, [logoUrl])

    useEffect(() => {
        if (!campaignOpen) return
        setOrgsLoading(true)
        listOrganizations({ limit: 200 })
            .then((data) => setOrgs(data.items))
            .catch(() => toast.error("Failed to load organizations"))
            .finally(() => setOrgsLoading(false))
    }, [campaignOpen])

    const ensureMembersLoaded = async (orgId: string) => {
        if (orgMembers[orgId] || membersLoading[orgId]) return
        setMembersLoading((prev) => ({ ...prev, [orgId]: true }))
        try {
            const members = await listMembers(orgId)
            setOrgMembers((prev) => ({ ...prev, [orgId]: members }))
            const activeIds = members.filter((m) => m.is_active).map((m) => m.user_id)
            setSelectedUsersByOrg((prev) => ({ ...prev, [orgId]: activeIds }))
        } catch {
            toast.error("Failed to load org members")
        } finally {
            setMembersLoading((prev) => ({ ...prev, [orgId]: false }))
        }
    }

    const toggleOrg = (orgId: string, next: boolean) => {
        setSelectedOrgIds((prev) => {
            if (next && !prev.includes(orgId)) {
                ensureMembersLoaded(orgId)
                return [...prev, orgId]
            }
            if (!next) {
                const updated = prev.filter((id) => id !== orgId)
                setSelectedUsersByOrg((userPrev) => {
                    const copy = { ...userPrev }
                    delete copy[orgId]
                    return copy
                })
                return updated
            }
            return prev
        })
    }

    const toggleSelectAllUsers = (orgId: string, next: boolean) => {
        const members = orgMembers[orgId] || []
        const activeIds = members.filter((m) => m.is_active).map((m) => m.user_id)
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

    const filteredOrgs = useMemo(() => {
        const query = orgSearch.trim().toLowerCase()
        if (!query) return orgs
        return orgs.filter(
            (org) =>
                org.name.toLowerCase().includes(query) ||
                org.slug.toLowerCase().includes(query)
        )
    }, [orgs, orgSearch])

    const selectedOrgSet = useMemo(() => new Set(selectedOrgIds), [selectedOrgIds])
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
        filteredIds.forEach((orgId) => ensureMembersLoaded(orgId))
    }

    const totalSelectedUsers = useMemo(() => {
        return Object.values(selectedUsersByOrg).reduce((acc, ids) => acc + ids.length, 0)
    }, [selectedUsersByOrg])

    const hasComplexHtml = useMemo(
        () => /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(body),
        [body]
    )

    useEffect(() => {
        if (editorModeTouched) return
        if (body && hasComplexHtml && editorMode !== "html") {
            setEditorMode("html")
        }
    }, [body, editorModeTouched, hasComplexHtml, editorMode])

    const effectiveEditorMode: EditorMode =
        editorMode === "visual" && hasComplexHtml && !editorModeTouched ? "html" : editorMode

    const insertIntoTextControl = (
        el: HTMLInputElement | HTMLTextAreaElement | null,
        selectionRef: MutableRefObject<{ start: number; end: number } | null>,
        setValue: Dispatch<SetStateAction<string>>,
        token: string
    ) => {
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

    const insertToken = (token: string) => {
        if (activeInsertionTarget === "subject") {
            insertIntoTextControl(subjectRef.current, subjectSelectionRef, setSubject, token)
            return
        }
        if (activeInsertionTarget === "body_html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, token)
            return
        }
        if (activeInsertionTarget === "body_visual") {
            visualBodyRef.current?.insertText(token)
            return
        }

        if (effectiveEditorMode === "html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, token)
            return
        }
        visualBodyRef.current?.insertText(token)
    }

    const insertPlatformLogo = () => {
        if (body.includes("{{platform_logo_block}}")) return
        const block = `<p>{{platform_logo_block}}</p>\n`
        if (effectiveEditorMode === "visual") {
            visualBodyRef.current?.insertHtml(block)
            setActiveInsertionTarget("body_visual")
            return
        }
        insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, block)
        setActiveInsertionTarget("body_html")
    }

    const applySfTemplate = () => {
        setSubject(SF_INVITE_SUBJECT)
        setBody(SF_INVITE_BODY)
    }

    const previewHtml = useMemo(() => {
        const logoPlaceholder =
            "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='54'><rect width='100%' height='100%' rx='10' fill='%23e5e7eb'/><text x='50%' y='55%' text-anchor='middle' font-family='Arial' font-size='14' fill='%236b7280'>Logo</text></svg>"
        const platformLogoUrl = logoPreviewUrl || logoPlaceholder
        const platformLogoBlock = logoPreviewUrl
            ? `<img src="${platformLogoUrl}" alt="Platform logo" style="max-width: 180px; height: auto; display: block; margin: 0 auto 6px auto;" />`
            : ""
        const rawHtml = body
            .replace(/\{\{org_name\}\}/g, "Sample Organization")
            .replace(/\{\{org_slug\}\}/g, "sample-org")
            .replace(/\{\{first_name\}\}/g, "Avery")
            .replace(/\{\{full_name\}\}/g, "Avery James")
            .replace(/\{\{email\}\}/g, "avery@example.com")
            .replace(/\{\{inviter_text\}\}/g, "")
            .replace(/\{\{role_title\}\}/g, "Admin")
            .replace(/\{\{invite_url\}\}/g, "https://app.surrogacyforce.com/invite/EXAMPLE")
            .replace(/\{\{expires_block\}\}/g, "<p>This invitation expires in 7 days.</p>")
            .replace(/\{\{platform_logo_url\}\}/g, platformLogoUrl)
            .replace(/\{\{platform_logo_block\}\}/g, platformLogoBlock)
            .replace(/\{\{unsubscribe_url\}\}/g, "https://app.surrogacyforce.com/email/unsubscribe/EXAMPLE")

        return DOMPurify.sanitize(normalizeTemplateHtml(rawHtml), {
            USE_PROFILES: { html: true },
            ADD_TAGS: [
                "table",
                "thead",
                "tbody",
                "tfoot",
                "tr",
                "td",
                "th",
                "colgroup",
                "col",
                "img",
                "hr",
                "div",
                "span",
                "center",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            ],
            ADD_ATTR: [
                "style",
                "class",
                "align",
                "valign",
                "width",
                "height",
                "cellpadding",
                "cellspacing",
                "border",
                "bgcolor",
                "colspan",
                "rowspan",
                "role",
                "target",
                "rel",
                "href",
                "src",
                "alt",
                "title",
            ],
        })
    }, [body, logoPreviewUrl])

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
        try {
            const payload: {
                subject: string
                body: string
                is_active: boolean
                from_email: string | null
                expected_version?: number
            } = {
                subject: subject.trim(),
                body,
                is_active: isActive,
                from_email: fromEmail.trim() ? fromEmail.trim() : null,
            }
            if (currentVersion !== null) {
                payload.expected_version = currentVersion
            }
            const updated = await updateTemplate.mutateAsync({
                systemKey,
                payload,
            })
            setCurrentVersion(updated.current_version)
            toast.success("System template updated")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to update template")
        } finally {
            setSaving(false)
        }
    }

    const handleDeleteTemplate = async () => {
        if (deleteTemplate.isPending) return
        try {
            await deleteTemplate.mutateAsync({ systemKey })
            toast.success("System template deleted")
            setShowDeleteDialog(false)
            router.push("/ops/templates?tab=system")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to delete system template")
        }
    }

    const handleSaveBranding = async () => {
        setBrandingSaving(true)
        try {
            await updateBranding.mutateAsync({
                logo_url: logoUrl.trim() ? logoUrl.trim() : null,
            })
            toast.success("Platform branding updated")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to update branding")
        } finally {
            setBrandingSaving(false)
        }
    }

    const handleLogoUpload = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) return

        const allowedTypes = ["image/png", "image/jpeg"]
        if (!allowedTypes.includes(file.type)) {
            toast.error("Logo must be a PNG or JPEG file")
            event.target.value = ""
            return
        }
        if (file.size > 1024 * 1024) {
            toast.error("Logo must be less than 1MB")
            event.target.value = ""
            return
        }

        try {
            const result = await uploadBrandingLogo.mutateAsync(file)
            setLogoUrl(result.logo_url ?? "")
            toast.success("Logo uploaded")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to upload logo")
        } finally {
            event.target.value = ""
        }
    }

    const handleSendTest = async () => {
        if (!testEmail.trim()) {
            toast.error("Test email is required")
            return
        }
        if (!testOrgId.trim()) {
            toast.error("Organization ID is required for test sends")
            return
        }
        setSending(true)
        try {
            await sendTest.mutateAsync({
                systemKey,
                payload: {
                    to_email: testEmail.trim(),
                    org_id: testOrgId.trim(),
                },
            })
            toast.success("Test email sent")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to send test email")
        } finally {
            setSending(false)
        }
    }

    const handleSendCampaign = async () => {
        const targets = selectedOrgIds
            .map((orgId) => ({
                org_id: orgId,
                user_ids: selectedUsersByOrg[orgId] ?? [],
            }))
            .filter((target) => target.user_ids.length > 0)

        if (targets.length === 0) {
            toast.error("Select at least one recipient to send the campaign")
            return
        }

        setCampaignSending(true)
        try {
            const result = await sendCampaign.mutateAsync({
                systemKey,
                payload: { targets },
            })
            toast.success(
                `Campaign sent: ${result.sent} delivered, ${result.suppressed} suppressed, ${result.failed} failed`
            )
            setCampaignOpen(false)
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to send campaign")
        } finally {
            setCampaignSending(false)
        }
    }

    if (isLoading || !template) {
        return (
            <div className="flex items-center justify-center p-10">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="p-6 space-y-6">
            <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete system template?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This deletes{" "}
                            <span className="font-medium text-foreground">{template.name}</span>. Built-in system templates will be restored to their default content automatically.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteTemplate.isPending}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDeleteTemplate}
                            disabled={deleteTemplate.isPending}
                            className="bg-destructive text-white hover:bg-destructive/90"
                        >
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <Button variant="ghost" onClick={() => router.push("/ops/templates?tab=system")}>
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back to templates
                    </Button>
                    <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                        {template.name}
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        System key: <span className="font-mono">{template.system_key}</span>
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <Button
                        variant="destructive"
                        onClick={() => setShowDeleteDialog(true)}
                        disabled={
                            deleteTemplate.isPending ||
                            saving ||
                            sending ||
                            brandingSaving ||
                            campaignSending
                        }
                    >
                        {deleteTemplate.isPending ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : (
                            <Trash2Icon className="mr-2 size-4" />
                        )}
                        Delete
                    </Button>
                    <Dialog open={campaignOpen} onOpenChange={setCampaignOpen}>
                        <DialogTrigger className={buttonVariants({ variant: "outline" })}>
                            <UsersIcon className="mr-2 size-4" />
                            Send campaign
                        </DialogTrigger>
                        <DialogContent className="max-w-3xl">
                            <DialogHeader>
                                <DialogTitle>Send campaign</DialogTitle>
                                <DialogDescription>
                                    Send the <span className="font-medium">{template.name}</span> system email to selected users.
                                    Unsubscribe headers are included automatically.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4">
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
                                                    Loading organizations...
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
                                                                className="flex items-center justify-between gap-3 p-3 text-sm hover:bg-stone-50 dark:hover:bg-stone-800/40"
                                                            >
                                                                <div className="flex items-center gap-3">
                                                                    <Checkbox
                                                                        checked={checked}
                                                                        onCheckedChange={(next) =>
                                                                            toggleOrg(org.id, next === true)
                                                                        }
                                                                    />
                                                                    <div>
                                                                        <div className="font-medium text-stone-900 dark:text-stone-100">
                                                                            {org.name}
                                                                        </div>
                                                                        <div className="text-xs text-muted-foreground">
                                                                            {org.slug}
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                                <Badge variant="outline" className="text-xs">
                                                                    {org.subscription_plan}
                                                                </Badge>
                                                            </label>
                                                        )
                                                    })}
                                                </div>
                                            )}
                                        </ScrollArea>
                                    </div>
                                </div>

                                {selectedOrgIds.length > 0 && (
                                    <div className="space-y-3">
                                        <Label>Recipients</Label>
                                        <div className="space-y-4">
                                            {selectedOrgIds.map((orgId) => {
                                                const org = orgs.find((o) => o.id === orgId)
                                                const members = orgMembers[orgId] || []
                                                const selectedUsers = new Set(selectedUsersByOrg[orgId] || [])
                                                const activeMembers = members.filter((m) => m.is_active)
                                                const isMembersLoading = membersLoading[orgId]
                                                const selectionLabel = isMembersLoading
                                                    ? "Loading members..."
                                                    : activeMembers.length === 0
                                                        ? "No active members found."
                                                        : `${selectedUsers.size} of ${activeMembers.length} selected`
                                                const allSelected =
                                                    activeMembers.length > 0 &&
                                                    activeMembers.every((m) => selectedUsers.has(m.user_id))
                                                return (
                                                    <Card key={orgId}>
                                                        <CardHeader className="pb-3">
                                                            <CardTitle className="text-base">
                                                                {org?.name || "Organization"}
                                                            </CardTitle>
                                                            <CardDescription>
                                                                {selectionLabel}
                                                            </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-3">
                                                            <div className="flex items-center justify-between text-sm">
                                                                <Label className="flex items-center gap-2">
                                                                    <Checkbox
                                                                        checked={allSelected}
                                                                        onCheckedChange={(next) =>
                                                                            toggleSelectAllUsers(orgId, next === true)
                                                                        }
                                                                    />
                                                                    Select all active users
                                                                </Label>
                                                                {membersLoading[orgId] && (
                                                                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                                        <Loader2Icon className="size-3 animate-spin" />
                                                                        Loading users...
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
                                                                                        checked={selectedUsers.has(
                                                                                            member.user_id
                                                                                        )}
                                                                                        disabled={!member.is_active}
                                                                                        onCheckedChange={(next) =>
                                                                                            toggleUserSelection(
                                                                                                orgId,
                                                                                                member.user_id,
                                                                                                next === true
                                                                                            )
                                                                                        }
                                                                                    />
                                                                                    <div>
                                                                                        <div className="font-medium text-stone-900 dark:text-stone-100">
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
                                                                        {members.length === 0 && !membersLoading[orgId] && (
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
                                            })}
                                        </div>
                                    </div>
                                )}
                            </div>
                            <DialogFooter className="flex flex-col gap-2 sm:flex-row sm:justify-between">
                                <span className="text-xs text-muted-foreground">
                                    {totalSelectedUsers} recipients selected
                                </span>
                                <div className="flex gap-2">
                                    <Button variant="outline" onClick={() => setCampaignOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button onClick={handleSendCampaign} disabled={campaignSending}>
                                        {campaignSending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                        Send campaign
                                    </Button>
                                </div>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                    <Button onClick={handleSave} disabled={saving}>
                        {saving ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : (
                            <SaveIcon className="mr-2 size-4" />
                        )}
                        Save changes
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Platform Branding</CardTitle>
                            <CardDescription>
                                Set the logo used in platform system emails.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="flex items-center gap-4">
                                {logoPreviewUrl ? (
                                    <img
                                        src={logoPreviewUrl}
                                        alt="Platform logo"
                                        className="h-14 w-auto rounded border"
                                    />
                                ) : (
                                    <div className="h-14 w-28 rounded border border-dashed flex items-center justify-center text-xs text-muted-foreground">
                                        No logo
                                    </div>
                                )}
                                <div>
                                    <input
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
                                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                                        ) : (
                                            <UploadIcon className="mr-2 size-4" />
                                        )}
                                        Upload Logo
                                    </Button>
                                    <p className="text-xs text-muted-foreground mt-1">Max 200x80px, PNG/JPG</p>
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
                                <p className="text-xs text-muted-foreground">
                                    This logo is available as <span className="font-mono">{"{{platform_logo_block}}"}</span>.
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                <Button
                                    variant="outline"
                                    onClick={handleSaveBranding}
                                    disabled={brandingSaving}
                                >
                                    {brandingSaving ? (
                                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    ) : null}
                                    Save branding
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Template Details</CardTitle>
                            <CardDescription>
                                Configure the sender, subject line, and content.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-5">
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
                            <div className="flex items-center justify-between rounded-md border p-3">
                                <div>
                                    <Label className="text-sm">Template active</Label>
                                    <p className="text-xs text-muted-foreground">
                                        If disabled, system emails fall back to the default template.
                                    </p>
                                </div>
                                <Switch checked={isActive} onCheckedChange={setIsActive} />
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Email Body</CardTitle>
                            <CardDescription>
                                Use variables to personalize content across all orgs.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex flex-wrap items-center gap-2">
                                    <ToggleGroup
                                        multiple={false}
                                        value={effectiveEditorMode ? [effectiveEditorMode] : []}
                                        onValueChange={(value) => {
                                            const next = value[0] as EditorMode | undefined
                                            if (!next) return
                                            setEditorMode(next)
                                            setEditorModeTouched(true)
                                        }}
                                    >
                                        <ToggleGroupItem value="visual" className="h-8">
                                            Visual
                                        </ToggleGroupItem>
                                    <ToggleGroupItem value="html" className="h-8">
                                            HTML
                                    </ToggleGroupItem>
                                    </ToggleGroup>
                                    <TemplateVariablePicker
                                        variables={templateVariables}
                                        disabled={variablesLoading || templateVariables.length === 0}
                                        triggerLabel={variablesLoading ? "Loading..." : "Insert Variable"}
                                        onSelect={(variable) => insertToken(`{{${variable.name}}}`)}
                                    />
                                    <Button type="button" variant="ghost" size="sm" onClick={insertPlatformLogo}>
                                        Insert Logo
                                    </Button>
                                    {isOrgInvite && (
                                        <Button type="button" variant="ghost" size="sm" onClick={applySfTemplate}>
                                            Use SF-style layout
                                        </Button>
                                    )}
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    Variables:{" "}
                                    {templateVariables.length > 0
                                        ? templateVariables.map((v) => `{{${v.name}}}`).join(", ")
                                        : "Loading..."}
                                </span>
                            </div>
                            {effectiveEditorMode === "visual" ? (
                                <RichTextEditor
                                    ref={visualBodyRef}
                                    content={body}
                                    onChange={(html) => setBody(html)}
                                    onFocus={() => setActiveInsertionTarget("body_visual")}
                                    placeholder="Write your system email content here..."
                                    minHeight="240px"
                                    maxHeight="480px"
                                    enableImages
                                />
                            ) : (
                                <Textarea
                                    ref={htmlBodyRef}
                                    value={body}
                                    onChange={(event) => setBody(event.target.value)}
                                    onFocus={(event) => {
                                        setActiveInsertionTarget("body_html")
                                        recordSelection(event.currentTarget, htmlBodySelectionRef)
                                    }}
                                    onKeyUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    onMouseUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    onSelect={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    placeholder="Paste or edit the HTML for this template..."
                                    className="min-h-[280px] font-mono text-xs leading-relaxed"
                                />
                            )}
                            {effectiveEditorMode === "visual" && hasComplexHtml && (
                                <p className="text-xs text-amber-600">
                                    This template contains advanced HTML. Switch to HTML mode to preserve layout.
                                </p>
                            )}
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
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Send test email</CardTitle>
                            <CardDescription>
                                Render this template for a specific organization and send to a test inbox.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="space-y-2">
                                <Label htmlFor="test-org-id">Organization ID</Label>
                                <Input
                                    id="test-org-id"
                                    value={testOrgId}
                                    onChange={(event) => setTestOrgId(event.target.value)}
                                    placeholder="UUID of an organization"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="test-email">Test email</Label>
                                <Input
                                    id="test-email"
                                    type="email"
                                    value={testEmail}
                                    onChange={(event) => setTestEmail(event.target.value)}
                                    placeholder="test@example.com"
                                />
                            </div>
                            <Button onClick={handleSendTest} disabled={sending}>
                                {sending ? (
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                ) : (
                                    <SendIcon className="mr-2 size-4" />
                                )}
                                Send test
                            </Button>
                        </CardContent>
                    </Card>
                </div>

                <Card className="h-fit">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <EyeIcon className="size-4" />
                            Preview
                        </CardTitle>
                        <CardDescription>Rendered using sample values.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border border-stone-200 bg-white shadow-sm">
                            <div
                                className="p-6 prose prose-sm prose-stone max-w-none text-stone-900"
                                dangerouslySetInnerHTML={{ __html: previewHtml }}
                            />
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
