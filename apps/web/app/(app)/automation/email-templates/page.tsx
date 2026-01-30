"use client"

import * as React from "react"
import { useState, useRef, useEffect, useCallback } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    PlusIcon,
    MoreVerticalIcon,
    MailIcon,
    EditIcon,
    TrashIcon,
    EyeIcon,
    CameraIcon,
    Loader2Icon,
    CodeIcon,
    XIcon,
    LinkedinIcon,
    InstagramIcon,
    ImageIcon,
    CopyIcon,
    ShareIcon,
    UserIcon,
    BuildingIcon,
    LockIcon,
} from "lucide-react"
import DOMPurify from "dompurify"
import {
    useEmailTemplates,
    useEmailTemplate,
    useCreateEmailTemplate,
    useUpdateEmailTemplate,
    useDeleteEmailTemplate,
    useCopyTemplateToPersonal,
    useShareTemplateWithOrg,
} from "@/lib/hooks/use-email-templates"
import {
    useUserSignature,
    useUpdateUserSignature,
    useSignaturePreview,
    useUploadSignaturePhoto,
    useDeleteSignaturePhoto,
    useOrgSignaturePreview,
} from "@/lib/hooks/use-signature"
import { getSignaturePreview } from "@/lib/api/signature"
import { RichTextEditor } from "@/components/rich-text-editor"
import type { EmailTemplateListItem, EmailTemplateScope } from "@/lib/api/email-templates"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"

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
// Signature Photo Upload Component
// =============================================================================

interface SignaturePhotoFieldProps {
    signaturePhotoUrl: string | null
    profilePhotoUrl: string | null
    profileName: string
    onUpload: (file: File) => void
    onDelete: () => void
    isUploading: boolean
    isDeleting: boolean
}

function SignaturePhotoField({
    signaturePhotoUrl,
    profilePhotoUrl,
    profileName,
    onUpload,
    onDelete,
    isUploading,
    isDeleting,
}: SignaturePhotoFieldProps) {
    const fileInputRef = useRef<HTMLInputElement>(null)
    const hasSignaturePhoto = !!signaturePhotoUrl
    const displayPhoto = signaturePhotoUrl || profilePhotoUrl

    const initials = profileName
        ?.split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2) || "??"

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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

        onUpload(file)
        e.target.value = ""
    }

    return (
        <div className="space-y-3">
            <Label className="text-sm font-medium">Signature Photo</Label>
            <div className="flex items-center gap-4">
                <div className="relative group">
                    <Avatar className="size-20 border-2 border-border">
                        <AvatarImage src={displayPhoto || undefined} />
                        <AvatarFallback className="text-lg bg-muted">
                            {initials}
                        </AvatarFallback>
                    </Avatar>
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        accept="image/png,image/jpeg,image/webp"
                        className="hidden"
                    />
                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isUploading}
                        className="absolute bottom-0 right-0 flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-md"
                    >
                        {isUploading ? (
                            <Loader2Icon className="size-3.5 animate-spin" />
                        ) : (
                            <CameraIcon className="size-3.5" />
                        )}
                    </button>
                </div>
                <div className="flex-1 space-y-1">
                    {hasSignaturePhoto ? (
                        <>
                            <p className="text-sm font-medium text-primary">
                                Custom signature photo
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Different from your profile avatar
                            </p>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                                onClick={onDelete}
                                disabled={isDeleting}
                            >
                                {isDeleting ? (
                                    <Loader2Icon className="mr-1 size-3 animate-spin" />
                                ) : (
                                    <TrashIcon className="mr-1 size-3" />
                                )}
                                Remove & use profile photo
                            </Button>
                        </>
                    ) : (
                        <>
                            <p className="text-sm text-muted-foreground">
                                {profilePhotoUrl ? "Using profile photo" : "No photo set"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Click camera to upload a signature-specific photo
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}

// =============================================================================
// Signature Preview Component
// =============================================================================

function SignaturePreviewComponent() {
    const { data: preview, isLoading } = useSignaturePreview()

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!preview?.html) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center">
                <ImageIcon className="size-10 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                    No signature configured yet
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                    Add your details and save to see preview
                </p>
            </div>
        )
    }

    return (
        <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: preview.html }}
        />
    )
}

// =============================================================================
// Org Signature Preview Component
// =============================================================================

function OrgSignaturePreviewComponent() {
    const { data: preview, isLoading } = useOrgSignaturePreview({ enabled: true, mode: "org_only" })

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!preview?.html) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center">
                <ImageIcon className="size-10 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                    No organization signature configured yet
                </p>
            </div>
        )
    }

    return (
        <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: preview.html }}
        />
    )
}

// =============================================================================
// Available template variables
// =============================================================================

const TEMPLATE_VARIABLES = [
    { name: "first_name", description: "Contact first name" },
    { name: "full_name", description: "Contact full name" },
    { name: "email", description: "Contact email" },
    { name: "phone", description: "Contact phone" },
    { name: "surrogate_number", description: "Surrogate number" },
    { name: "intended_parent_number", description: "Intended parent number" },
    { name: "status_label", description: "Current status" },
    { name: "owner_name", description: "Surrogate owner name" },
    { name: "org_name", description: "Organization name" },
    { name: "appointment_date", description: "Appointment date" },
    { name: "appointment_time", description: "Appointment time" },
    { name: "appointment_location", description: "Appointment location" },
    { name: "unsubscribe_url", description: "Unsubscribe link" },
]

// =============================================================================
// Template Card Component
// =============================================================================

interface TemplateCardProps {
    template: EmailTemplateListItem
    isReadOnly?: boolean
    canCopy?: boolean
    canShare?: boolean
    onEdit: () => void
    onDelete: () => void
    onCopy: () => void
    onShare: () => void
}

function TemplateCard({
    template,
    isReadOnly = false,
    canCopy = false,
    canShare = false,
    onEdit,
    onDelete,
    onCopy,
    onShare,
}: TemplateCardProps) {
    return (
        <Card className="group relative">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <CardTitle className="text-base truncate">
                                {template.name}
                            </CardTitle>
                            {template.is_system_template && (
                                <Badge variant="secondary" className="text-xs shrink-0">
                                    System
                                </Badge>
                            )}
                        </div>
                        <CardDescription className="truncate mt-1">
                            {template.subject}
                        </CardDescription>
                        {template.owner_name && (
                            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                                <UserIcon className="size-3" />
                                {template.owner_name}
                            </p>
                        )}
                    </div>
                    {!isReadOnly && (
                        <DropdownMenu>
                            <DropdownMenuTrigger>
                                <span className="inline-flex items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground size-8 shrink-0 cursor-pointer">
                                    <MoreVerticalIcon className="size-4" />
                                </span>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {!template.is_system_template && (
                                    <>
                                        <DropdownMenuItem onClick={onEdit}>
                                            <EditIcon className="mr-2 size-4" />
                                            Edit
                                        </DropdownMenuItem>
                                        <DropdownMenuSeparator />
                                    </>
                                )}
                                {canCopy && (
                                    <DropdownMenuItem onClick={onCopy}>
                                        <CopyIcon className="mr-2 size-4" />
                                        Copy to My Templates
                                    </DropdownMenuItem>
                                )}
                                {canShare && (
                                    <DropdownMenuItem onClick={onShare}>
                                        <ShareIcon className="mr-2 size-4" />
                                        Share with Org
                                    </DropdownMenuItem>
                                )}
                                {!template.is_system_template && (canCopy || canShare) && (
                                    <DropdownMenuSeparator />
                                )}
                                {!template.is_system_template && (
                                    <DropdownMenuItem
                                        onClick={onDelete}
                                        className="text-destructive"
                                    >
                                        <TrashIcon className="mr-2 size-4" />
                                        Delete
                                    </DropdownMenuItem>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                    {isReadOnly && (
                        <Badge variant="outline" className="text-xs shrink-0">
                            <LockIcon className="size-3 mr-1" />
                            View Only
                        </Badge>
                    )}
                </div>
            </CardHeader>
            <CardContent className="pt-0">
                <div className="flex items-center gap-2">
                    <Badge variant={template.is_active ? "default" : "secondary"}>
                        {template.is_active ? "Active" : "Inactive"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                        Updated {new Date(template.updated_at).toLocaleDateString()}
                    </span>
                </div>
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function EmailTemplatesPage() {
    const { user } = useAuth()
    const isAdmin = user?.role === "admin" || user?.role === "developer"

    const [activeTab, setActiveTab] = useState("personal")
    const [showAllPersonal, setShowAllPersonal] = useState(false)
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<EmailTemplateListItem | null>(null)
    const [templateName, setTemplateName] = useState("")
    const [templateSubject, setTemplateSubject] = useState("")
    const [templateBody, setTemplateBody] = useState("")
    const [templateScope, setTemplateScope] = useState<EmailTemplateScope>("personal")
    const [showPreview, setShowPreview] = useState(false)
    const [previewHtml, setPreviewHtml] = useState("")
    const [signaturePreviewMode, setSignaturePreviewMode] = useState<"personal" | "org">("personal")

    // Copy/Share dialog state
    const [copyDialogOpen, setCopyDialogOpen] = useState(false)
    const [shareDialogOpen, setShareDialogOpen] = useState(false)
    const [copyShareTarget, setCopyShareTarget] = useState<EmailTemplateListItem | null>(null)
    const [copyShareName, setCopyShareName] = useState("")

    // Signature override state
    const [signatureName, setSignatureName] = useState("")
    const [signatureTitle, setSignatureTitle] = useState("")
    const [signaturePhone, setSignaturePhone] = useState("")

    // Social links state
    const [signatureLinkedin, setSignatureLinkedin] = useState("")
    const [signatureTwitter, setSignatureTwitter] = useState("")
    const [signatureInstagram, setSignatureInstagram] = useState("")

    // Track if form has unsaved changes
    const [hasChanges, setHasChanges] = useState(false)

    // API hooks for templates
    const { data: personalTemplates, isLoading: loadingPersonal } = useEmailTemplates({
        activeOnly: false,
        scope: "personal",
        showAllPersonal: isAdmin && showAllPersonal,
    })
    const { data: orgTemplates, isLoading: loadingOrg } = useEmailTemplates({
        activeOnly: false,
        scope: "org",
    })

    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()
    const copyToPersonal = useCopyTemplateToPersonal()
    const shareWithOrg = useShareTemplateWithOrg()

    // Signature hooks
    const { data: signatureData, refetch: refetchSignature } = useUserSignature()
    const updateSignatureMutation = useUpdateUserSignature()
    const uploadPhotoMutation = useUploadSignaturePhoto()
    const deletePhotoMutation = useDeleteSignaturePhoto()

    // Get full template details when editing
    const { data: fullTemplate } = useEmailTemplate(editingTemplate?.id || null)

    const sanitizeHtml = useCallback((html: string) => {
        return DOMPurify.sanitize(html, {
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
    }, [])

    const normalizeTemplateHtml = useCallback((html: string) => {
        return html
            .replace(/<p>\s*<\/p>/gi, "<p>&nbsp;</p>")
            .replace(/<p>\s*<br\s*\/?>\s*<\/p>/gi, "<p>&nbsp;</p>")
    }, [])

    // Load signature data on mount
    useEffect(() => {
        if (signatureData) {
            setSignatureName(signatureData.signature_name || "")
            setSignatureTitle(signatureData.signature_title || "")
            setSignaturePhone(signatureData.signature_phone || "")
            setSignatureLinkedin(signatureData.signature_linkedin || "")
            setSignatureTwitter(signatureData.signature_twitter || "")
            setSignatureInstagram(signatureData.signature_instagram || "")
            setHasChanges(false)
        }
    }, [signatureData])

    // Track changes
    useEffect(() => {
        if (!signatureData) return
        const changed =
            signatureName !== (signatureData.signature_name || "") ||
            signatureTitle !== (signatureData.signature_title || "") ||
            signaturePhone !== (signatureData.signature_phone || "") ||
            signatureLinkedin !== (signatureData.signature_linkedin || "") ||
            signatureTwitter !== (signatureData.signature_twitter || "") ||
            signatureInstagram !== (signatureData.signature_instagram || "")
        setHasChanges(changed)
    }, [signatureName, signatureTitle, signaturePhone, signatureLinkedin, signatureTwitter, signatureInstagram, signatureData])

    const handleOpenModal = (template?: EmailTemplateListItem, scope: EmailTemplateScope = "personal") => {
        if (template) {
            setEditingTemplate(template)
            setTemplateName(template.name)
            setTemplateSubject(template.subject)
            setTemplateBody("")
            setTemplateScope(template.scope)
        } else {
            setEditingTemplate(null)
            setTemplateName("")
            setTemplateSubject("")
            setTemplateBody("")
            setTemplateScope(scope)
        }
        setIsModalOpen(true)
    }

    useEffect(() => {
        if (fullTemplate && editingTemplate && !templateBody && fullTemplate.body) {
            setTemplateBody(fullTemplate.body)
        }
    }, [fullTemplate, editingTemplate, templateBody])

    const handleSave = () => {
        if (!templateName.trim() || !templateSubject.trim() || !templateBody.trim()) return

        if (editingTemplate) {
            updateTemplate.mutate(
                { id: editingTemplate.id, data: { name: templateName, subject: templateSubject, body: templateBody } },
                { onSuccess: () => setIsModalOpen(false) }
            )
        } else {
            createTemplate.mutate(
                { name: templateName, subject: templateSubject, body: templateBody, scope: templateScope },
                { onSuccess: () => setIsModalOpen(false) }
            )
        }
    }

    const handleDelete = (id: string) => {
        if (confirm("Are you sure you want to delete this template?")) {
            deleteTemplate.mutate(id)
        }
    }

    const handleOpenCopyDialog = (template: EmailTemplateListItem) => {
        setCopyShareTarget(template)
        setCopyShareName(`${template.name} (Copy)`)
        setCopyDialogOpen(true)
    }

    const handleOpenShareDialog = (template: EmailTemplateListItem) => {
        setCopyShareTarget(template)
        setCopyShareName(template.name)
        setShareDialogOpen(true)
    }

    const handleCopy = () => {
        if (!copyShareTarget || !copyShareName.trim()) return
        copyToPersonal.mutate(
            { id: copyShareTarget.id, data: { name: copyShareName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template copied to your personal templates")
                    setCopyDialogOpen(false)
                    setCopyShareTarget(null)
                    setCopyShareName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to copy template")
                },
            }
        )
    }

    const handleShare = () => {
        if (!copyShareTarget || !copyShareName.trim()) return
        shareWithOrg.mutate(
            { id: copyShareTarget.id, data: { name: copyShareName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template shared with the organization")
                    setShareDialogOpen(false)
                    setCopyShareTarget(null)
                    setCopyShareName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to share template")
                },
            }
        )
    }

    const handlePreview = () => {
        let html = templateBody
            .replace(/\{\{full_name\}\}/g, "John Smith")
            .replace(/\{\{email\}\}/g, "john@example.com")
            .replace(/\{\{phone\}\}/g, "(555) 123-4567")
            .replace(/\{\{surrogate_number\}\}/g, "S10001")
            .replace(/\{\{status_label\}\}/g, "Qualified")
            .replace(/\{\{owner_name\}\}/g, "Sara Manager")
            .replace(/\{\{org_name\}\}/g, signatureData?.org_signature_company_name || "ABC Surrogacy")
            .replace(/\{\{appointment_date\}\}/g, "January 15, 2025")
            .replace(/\{\{appointment_time\}\}/g, "2:00 PM PST")
            .replace(/\{\{appointment_location\}\}/g, "Virtual Appointment")

        const hasHtmlTags = /<[a-z][\s\S]*>/i.test(html)
        if (!hasHtmlTags) {
            const lines = html.split(/\n/)
            html = lines
                .map((line) => {
                    if (!line.trim()) {
                        return `<p style="margin: 0 0 1em 0;">&nbsp;</p>`
                    }
                    return `<p style="margin: 0 0 1em 0;">${line}</p>`
                })
                .join("")
        } else {
            html = normalizeTemplateHtml(html)
        }

        setPreviewHtml(sanitizeHtml(html))
        setShowPreview(true)
    }

    const insertVariable = (varName: string) => {
        setTemplateBody(templateBody + `{{${varName}}}`)
    }

    // Save all signature settings
    const handleSaveSignature = () => {
        updateSignatureMutation.mutate(
            {
                signature_name: signatureName || null,
                signature_title: signatureTitle || null,
                signature_phone: signaturePhone || null,
                signature_linkedin: signatureLinkedin || null,
                signature_twitter: signatureTwitter || null,
                signature_instagram: signatureInstagram || null,
            },
            {
                onSuccess: () => {
                    setHasChanges(false)
                    refetchSignature()
                },
            }
        )
    }

    const handleUploadPhoto = (file: File) => {
        uploadPhotoMutation.mutate(file, {
            onSuccess: () => refetchSignature(),
        })
    }

    const handleDeletePhoto = () => {
        if (confirm("Remove your signature photo? Your profile avatar will be used instead.")) {
            deletePhotoMutation.mutate(undefined, {
                onSuccess: () => refetchSignature(),
            })
        }
    }

    const handleCopySignatureHtml = async () => {
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

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Email Templates</h1>
                    {activeTab === "personal" && (
                        <Button onClick={() => handleOpenModal(undefined, "personal")}>
                            <PlusIcon className="mr-2 size-4" />
                            Create Template
                        </Button>
                    )}
                    {activeTab === "org" && isAdmin && (
                        <Button onClick={() => handleOpenModal(undefined, "org")}>
                            <PlusIcon className="mr-2 size-4" />
                            Create Org Template
                        </Button>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <div className="flex items-center justify-between mb-6">
                        <TabsList>
                            <TabsTrigger value="personal" className="gap-2">
                                <UserIcon className="size-4" />
                                My Email Templates
                            </TabsTrigger>
                            <TabsTrigger value="org" className="gap-2">
                                <BuildingIcon className="size-4" />
                                Email Templates
                            </TabsTrigger>
                            <TabsTrigger value="signature">My Signature</TabsTrigger>
                        </TabsList>

                        {/* Admin filter for personal templates */}
                        {activeTab === "personal" && isAdmin && (
                            <Select
                                value={showAllPersonal ? "all" : "mine"}
                                onValueChange={(v) => setShowAllPersonal(v === "all")}
                            >
                                <SelectTrigger className="w-[180px]">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="mine">My Templates</SelectItem>
                                    <SelectItem value="all">All Personal Templates</SelectItem>
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    {/* Personal Templates Tab */}
                    <TabsContent value="personal" className="space-y-4">
                        {loadingPersonal ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !personalTemplates?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <UserIcon className="size-12 text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground mb-4">
                                        {showAllPersonal
                                            ? "No personal templates found"
                                            : "You don't have any personal templates yet"}
                                    </p>
                                    {!showAllPersonal && (
                                        <Button onClick={() => handleOpenModal(undefined, "personal")}>
                                            <PlusIcon className="mr-2 size-4" />
                                            Create Your First Template
                                        </Button>
                                    )}
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {personalTemplates.map((template) => {
                                    const isOwner = template.owner_user_id === user?.user_id
                                    return (
                                        <TemplateCard
                                            key={template.id}
                                            template={template}
                                            isReadOnly={!isOwner}
                                            canCopy={false}
                                            canShare={isOwner}
                                            onEdit={() => handleOpenModal(template)}
                                            onDelete={() => handleDelete(template.id)}
                                            onCopy={() => {}}
                                            onShare={() => handleOpenShareDialog(template)}
                                        />
                                    )
                                })}
                            </div>
                        )}
                    </TabsContent>

                    {/* Org Templates Tab */}
                    <TabsContent value="org" className="space-y-4">
                        {loadingOrg ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !orgTemplates?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <BuildingIcon className="size-12 text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground mb-4">No organization templates yet</p>
                                    {isAdmin && (
                                        <Button onClick={() => handleOpenModal(undefined, "org")}>
                                            <PlusIcon className="mr-2 size-4" />
                                            Create Org Template
                                        </Button>
                                    )}
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {orgTemplates.map((template) => (
                                    <TemplateCard
                                        key={template.id}
                                        template={template}
                                        isReadOnly={!isAdmin && !template.is_system_template}
                                        canCopy={true}
                                        canShare={false}
                                        onEdit={() => handleOpenModal(template)}
                                        onDelete={() => handleDelete(template.id)}
                                        onCopy={() => handleOpenCopyDialog(template)}
                                        onShare={() => {}}
                                    />
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
                                            onUpload={handleUploadPhoto}
                                            onDelete={handleDeletePhoto}
                                            isUploading={uploadPhotoMutation.isPending}
                                            isDeleting={deletePhotoMutation.isPending}
                                        />

                                        <div className="border-t pt-4" />

                                        {/* Override Fields */}
                                        <div className="space-y-3">
                                            <SignatureOverrideField
                                                id="sig-name"
                                                label="Name"
                                                value={signatureName}
                                                profileDefault={signatureData?.profile_name || null}
                                                onChange={setSignatureName}
                                                onClear={() => setSignatureName("")}
                                            />

                                            <SignatureOverrideField
                                                id="sig-title"
                                                label="Title"
                                                value={signatureTitle}
                                                profileDefault={signatureData?.profile_title || null}
                                                onChange={setSignatureTitle}
                                                onClear={() => setSignatureTitle("")}
                                                placeholder="e.g., Case Manager"
                                            />

                                            <SignatureOverrideField
                                                id="sig-phone"
                                                label="Phone"
                                                value={signaturePhone}
                                                profileDefault={signatureData?.profile_phone || null}
                                                onChange={setSignaturePhone}
                                                onClear={() => setSignaturePhone("")}
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
                                                        <LinkedinIcon className="size-3.5 text-muted-foreground" />
                                                        LinkedIn
                                                    </Label>
                                                    <Input
                                                        id="sig-linkedin"
                                                        placeholder="https://linkedin.com/in/yourprofile"
                                                        value={signatureLinkedin}
                                                        onChange={(e) => setSignatureLinkedin(e.target.value)}
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
                                                        value={signatureTwitter}
                                                        onChange={(e) => setSignatureTwitter(e.target.value)}
                                                        className="h-9"
                                                    />
                                                </div>

                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-instagram" className="text-xs flex items-center gap-1.5">
                                                        <InstagramIcon className="size-3.5 text-muted-foreground" />
                                                        Instagram
                                                    </Label>
                                                    <Input
                                                        id="sig-instagram"
                                                        placeholder="https://instagram.com/yourhandle"
                                                        value={signatureInstagram}
                                                        onChange={(e) => setSignatureInstagram(e.target.value)}
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
                                                        Saving...
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
                                                    <img
                                                        src={signatureData.org_signature_logo_url}
                                                        alt="Logo"
                                                        className="h-10 w-auto border rounded"
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
                                                [Your email content here...]
                                            </p>
                                            {signaturePreviewMode === "personal" ? (
                                                <SignaturePreviewComponent />
                                            ) : (
                                                <OrgSignaturePreviewComponent />
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>
                </Tabs>
            </div>

            {/* Create/Edit Template Modal */}
            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle>
                            {editingTemplate ? "Edit Template" : "Create Template"}
                        </DialogTitle>
                        <DialogDescription>
                            Create reusable email templates with dynamic variables.
                            {!editingTemplate && (
                                <span className="block mt-1">
                                    Creating a{" "}
                                    <Badge variant="outline" className="text-xs">
                                        {templateScope === "personal" ? "Personal" : "Organization"}
                                    </Badge>{" "}
                                    template
                                </span>
                            )}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex-1 overflow-y-auto space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="name">Template Name</Label>
                            <Input
                                id="name"
                                placeholder="Welcome Email"
                                value={templateName}
                                onChange={(e) => setTemplateName(e.target.value)}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="subject">Subject Line</Label>
                            <Input
                                id="subject"
                                placeholder="Welcome to {{org_name}}, {{full_name}}!"
                                value={templateSubject}
                                onChange={(e) => setTemplateSubject(e.target.value)}
                            />
                        </div>

                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="body">Email Body (HTML)</Label>
                                <DropdownMenu>
                                    <DropdownMenuTrigger>
                                        <span className="inline-flex items-center justify-center gap-2 rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 text-sm cursor-pointer">
                                            <CodeIcon className="size-4" />
                                            Insert Variable
                                        </span>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-56">
                                        {TEMPLATE_VARIABLES.map((v) => (
                                            <DropdownMenuItem
                                                key={v.name}
                                                onClick={() => insertVariable(v.name)}
                                            >
                                                <span className="font-mono text-xs">{`{{${v.name}}}`}</span>
                                                <span className="ml-2 text-muted-foreground text-xs">
                                                    {v.description}
                                                </span>
                                            </DropdownMenuItem>
                                        ))}
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                            <RichTextEditor
                                content={templateBody}
                                onChange={(html) => setTemplateBody(html)}
                                placeholder="Write your email content here... Use the toolbar to format text."
                                minHeight="200px"
                                maxHeight="350px"
                            />
                            <p className="text-xs text-muted-foreground">
                                Use the Insert Variable button above to add dynamic placeholders like {"{{full_name}}"}
                            </p>
                        </div>
                    </div>

                    <DialogFooter className="flex gap-2">
                        <Button variant="outline" onClick={handlePreview}>
                            <EyeIcon className="mr-2 size-4" />
                            Preview
                        </Button>
                        <Button
                            onClick={handleSave}
                            disabled={createTemplate.isPending || updateTemplate.isPending}
                        >
                            {(createTemplate.isPending || updateTemplate.isPending) && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            {editingTemplate ? "Save Changes" : "Create Template"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

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

            {/* Preview Modal */}
            <Dialog open={showPreview} onOpenChange={setShowPreview}>
                <DialogContent className="max-w-2xl max-h-[80vh]">
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
                                    {signatureData?.org_signature_company_name || "Your Company"} &lt;you@company.com&gt;
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">To:</span>
                                <span className="text-foreground">John Smith &lt;john@example.com&gt;</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">Subject:</span>
                                <span className="font-medium text-foreground">
                                    {templateSubject
                                        .replace(/\{\{full_name\}\}/g, "John Smith")
                                        .replace(/\{\{org_name\}\}/g, signatureData?.org_signature_company_name || "ABC Surrogacy")}
                                </span>
                            </div>
                        </div>
                        {/* Email body section */}
                        <div className="p-4">
                            <div
                                className="prose prose-sm max-w-none [&_p]:whitespace-pre-wrap"
                                dangerouslySetInnerHTML={{ __html: previewHtml }}
                            />
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
