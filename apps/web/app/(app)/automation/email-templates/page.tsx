"use client"

import * as React from "react"
import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    PlusIcon,
    MoreVerticalIcon,
    MailIcon,
    EditIcon,
    TrashIcon,
    EyeIcon,
    UserIcon,
    PhoneIcon,
    BuildingIcon,
    LoaderIcon,
    CodeIcon,
} from "lucide-react"
import DOMPurify from "dompurify"
import {
    useEmailTemplates,
    useEmailTemplate,
    useCreateEmailTemplate,
    useUpdateEmailTemplate,
    useDeleteEmailTemplate,
} from "@/lib/hooks/use-email-templates"
import { useUserSignature, useUpdateUserSignature, useSignaturePreview } from "@/lib/hooks/use-signature"
import { getSignaturePreview } from "@/lib/api/signature"
import { RichTextEditor } from "@/components/rich-text-editor"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"

// Signature Preview Component - fetches and renders backend HTML
function SignaturePreviewComponent() {
    const { data: preview, isLoading } = useSignaturePreview()

    if (isLoading) {
        return <div className="animate-pulse bg-muted h-24 rounded" />
    }

    if (!preview?.html) {
        return <p className="text-muted-foreground italic">No signature configured. Add your social links and save to preview.</p>
    }

    return (
        <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: preview.html }}
        />
    )
}

// Available template variables
const TEMPLATE_VARIABLES = [
    { name: "full_name", description: "Contact full name" },
    { name: "email", description: "Contact email" },
    { name: "phone", description: "Contact phone" },
    { name: "case_number", description: "Case number" },
    { name: "status_label", description: "Current status" },
    { name: "owner_name", description: "Case owner name" },
    { name: "org_name", description: "Organization name" },
    { name: "appointment_date", description: "Appointment date" },
    { name: "appointment_time", description: "Appointment time" },
    { name: "appointment_location", description: "Appointment location" },
]

export default function EmailTemplatesPage() {
    const [activeTab, setActiveTab] = useState("templates")
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<EmailTemplateListItem | null>(null)
    const [templateName, setTemplateName] = useState("")
    const [templateSubject, setTemplateSubject] = useState("")
    const [templateBody, setTemplateBody] = useState("")
    const [showPreview, setShowPreview] = useState(false)
    const [previewHtml, setPreviewHtml] = useState("")

    // Signature state (social links only)
    const [signatureLinkedin, setSignatureLinkedin] = useState("")
    const [signatureTwitter, setSignatureTwitter] = useState("")
    const [signatureInstagram, setSignatureInstagram] = useState("")

    // API hooks
    const { data: templates, isLoading } = useEmailTemplates(false)
    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()

    // Signature hooks - use new hooks from updated use-signature.ts
    const { data: signatureData } = useUserSignature()
    const updateSignatureMutation = useUpdateUserSignature()

    // Get full template details when editing
    const { data: fullTemplate } = useEmailTemplate(editingTemplate?.id || null)

    const sanitizeHtml = React.useCallback((html: string) => {
        return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
    }, [])

    const normalizeTemplateHtml = React.useCallback((html: string) => {
        return html
            .replace(/<p>\s*<\/p>/gi, "<p>&nbsp;</p>")
            .replace(/<p>\s*<br\s*\/?>\s*<\/p>/gi, "<p>&nbsp;</p>")
    }, [])

    // Load signature data on mount
    React.useEffect(() => {
        if (signatureData) {
            setSignatureLinkedin(signatureData.signature_linkedin || "")
            setSignatureTwitter(signatureData.signature_twitter || "")
            setSignatureInstagram(signatureData.signature_instagram || "")
        }
    }, [signatureData])

    const handleOpenModal = (template?: EmailTemplateListItem) => {
        if (template) {
            setEditingTemplate(template)
            setTemplateName(template.name)
            setTemplateSubject(template.subject)
            setTemplateBody("") // Will be populated from fullTemplate
        } else {
            setEditingTemplate(null)
            setTemplateName("")
            setTemplateSubject("")
            setTemplateBody("")
        }
        setIsModalOpen(true)
    }

    React.useEffect(() => {
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
                { name: templateName, subject: templateSubject, body: templateBody },
                { onSuccess: () => setIsModalOpen(false) }
            )
        }
    }

    const handleDelete = (id: string) => {
        if (confirm("Are you sure you want to delete this template?")) {
            deleteTemplate.mutate(id)
        }
    }

    const handlePreview = () => {
        // Simple preview - replace variables with sample values
        let html = templateBody
            .replace(/\{\{full_name\}\}/g, "John Smith")
            .replace(/\{\{email\}\}/g, "john@example.com")
            .replace(/\{\{phone\}\}/g, "(555) 123-4567")
            .replace(/\{\{case_number\}\}/g, "CASE-2024-001")
            .replace(/\{\{status_label\}\}/g, "Qualified")
            .replace(/\{\{owner_name\}\}/g, "Sara Manager")
            .replace(/\{\{org_name\}\}/g, signatureData?.org_signature_company_name || "ABC Surrogacy")
            .replace(/\{\{appointment_date\}\}/g, "January 15, 2025")
            .replace(/\{\{appointment_time\}\}/g, "2:00 PM PST")
            .replace(/\{\{appointment_location\}\}/g, "Virtual Appointment")

        // If content doesn't contain HTML tags, convert line breaks to paragraphs
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

        // Note: Signature is now rendered by backend, not appended here in preview
        // Template preview just shows the template body without signature

        setPreviewHtml(sanitizeHtml(html))
        setShowPreview(true)
    }

    const insertVariable = (varName: string) => {
        setTemplateBody(templateBody + `{{${varName}}}`)
    }

    const handleSaveSignature = () => {
        updateSignatureMutation.mutate({
            signature_linkedin: signatureLinkedin || null,
            signature_twitter: signatureTwitter || null,
            signature_instagram: signatureInstagram || null,
        })
    }

    const handleCopySignatureHtml = async () => {
        // Fetch fresh preview from backend
        try {
            const data = await getSignaturePreview()
            const html = data.html || ""

            try {
                await navigator.clipboard.writeText(html)
                // Would normally show a toast here
                alert("Signature HTML copied to clipboard!")
            } catch {
                // Fallback for older browsers
                const textarea = document.createElement("textarea")
                textarea.value = html
                document.body.appendChild(textarea)
                textarea.select()
                document.execCommand("copy")
                document.body.removeChild(textarea)
                alert("Signature HTML copied to clipboard!")
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
                    {activeTab === "templates" && (
                        <Button onClick={() => handleOpenModal()}>
                            <PlusIcon className="mr-2 size-4" />
                            Create Template
                        </Button>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList className="mb-6">
                        <TabsTrigger value="templates">Templates</TabsTrigger>
                        <TabsTrigger value="signature">My Signature</TabsTrigger>
                    </TabsList>

                    {/* Templates Tab */}
                    <TabsContent value="templates" className="space-y-4">
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !templates?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <MailIcon className="size-12 text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground mb-4">No email templates yet</p>
                                    <Button onClick={() => handleOpenModal()}>
                                        <PlusIcon className="mr-2 size-4" />
                                        Create Your First Template
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {templates.map((template) => (
                                    <Card key={template.id} className="group relative">
                                        <CardHeader className="pb-3">
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1 min-w-0">
                                                    <CardTitle className="text-base truncate">
                                                        {template.name}
                                                    </CardTitle>
                                                    <CardDescription className="truncate mt-1">
                                                        {template.subject}
                                                    </CardDescription>
                                                </div>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger>
                                                        <span className="inline-flex items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground size-8 shrink-0 cursor-pointer">
                                                            <MoreVerticalIcon className="size-4" />
                                                        </span>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => handleOpenModal(template)}>
                                                            <EditIcon className="mr-2 size-4" />
                                                            Edit
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem
                                                            onClick={() => handleDelete(template.id)}
                                                            className="text-destructive"
                                                        >
                                                            <TrashIcon className="mr-2 size-4" />
                                                            Delete
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
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
                                ))}
                            </div>
                        )}
                    </TabsContent>

                    {/* Signature Tab */}
                    <TabsContent value="signature">
                        <div className="grid gap-6 lg:grid-cols-2">
                            {/* Editor */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>My Social Links</CardTitle>
                                    <CardDescription>
                                        Add your social media links to your email signature. Branding and template are managed by your organization admin.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {/* Organization Branding (read-only) */}
                                    {(signatureData?.org_signature_company_name ||
                                        signatureData?.org_signature_address ||
                                        signatureData?.org_signature_phone ||
                                        signatureData?.org_signature_website ||
                                        signatureData?.org_signature_logo_url) && (
                                        <div className="p-3 bg-muted rounded-lg mb-4">
                                            <p className="text-sm text-muted-foreground mb-1">Organization</p>
                                            <div className="flex items-center gap-2">
                                                {signatureData.org_signature_logo_url && (
                                                    <img
                                                        src={signatureData.org_signature_logo_url}
                                                        alt="Logo"
                                                        className="h-8 w-auto"
                                                    />
                                                )}
                                                <span className="font-medium">
                                                    {signatureData.org_signature_company_name || "Organization"}
                                                </span>
                                                {signatureData.org_signature_template && (
                                                    <Badge variant="secondary" className="ml-auto">
                                                        {signatureData.org_signature_template} template
                                                    </Badge>
                                                )}
                                            </div>
                                            {(signatureData?.org_signature_address ||
                                                signatureData?.org_signature_phone ||
                                                signatureData?.org_signature_website) && (
                                                <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                                                    {signatureData?.org_signature_address && (
                                                        <p>{signatureData.org_signature_address}</p>
                                                    )}
                                                    {signatureData?.org_signature_phone && (
                                                        <p>{signatureData.org_signature_phone}</p>
                                                    )}
                                                    {signatureData?.org_signature_website && (
                                                        <a
                                                            className="underline"
                                                            href={signatureData.org_signature_website}
                                                            rel="noreferrer"
                                                            target="_blank"
                                                        >
                                                            {signatureData.org_signature_website}
                                                        </a>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Social Links (editable) */}
                                    <div className="space-y-2">
                                        <Label htmlFor="sig-linkedin">LinkedIn URL</Label>
                                        <Input
                                            id="sig-linkedin"
                                            placeholder="https://linkedin.com/in/yourprofile"
                                            value={signatureLinkedin}
                                            onChange={(e) => setSignatureLinkedin(e.target.value)}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="sig-twitter">Twitter/X URL</Label>
                                        <Input
                                            id="sig-twitter"
                                            placeholder="https://twitter.com/yourhandle"
                                            value={signatureTwitter}
                                            onChange={(e) => setSignatureTwitter(e.target.value)}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="sig-instagram">Instagram URL</Label>
                                        <Input
                                            id="sig-instagram"
                                            placeholder="https://instagram.com/yourhandle"
                                            value={signatureInstagram}
                                            onChange={(e) => setSignatureInstagram(e.target.value)}
                                        />
                                    </div>

                                    <div className="flex gap-2">
                                        <Button
                                            onClick={handleSaveSignature}
                                            className="flex-1"
                                            disabled={updateSignatureMutation.isPending}
                                        >
                                            {updateSignatureMutation.isPending ? (
                                                <LoaderIcon className="mr-2 size-4 animate-spin" />
                                            ) : null}
                                            Save Social Links
                                        </Button>
                                        <Button
                                            variant="outline"
                                            onClick={handleCopySignatureHtml}
                                        >
                                            Copy HTML
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Preview */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Preview</CardTitle>
                                    <CardDescription>
                                        How your signature will appear in emails (rendered from backend)
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="border rounded-lg p-4 bg-white min-h-[200px]">
                                        <p className="text-muted-foreground text-sm mb-4">
                                            [Email body content...]
                                        </p>
                                        <SignaturePreviewComponent />
                                    </div>
                                </CardContent>
                            </Card>
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
                                <LoaderIcon className="mr-2 size-4 animate-spin" />
                            )}
                            {editingTemplate ? "Save Changes" : "Create Template"}
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
