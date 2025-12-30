"use client"

import * as React from "react"
import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
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
import { useSignature, useUpdateSignature } from "@/lib/hooks/use-signature"
import { RichTextEditor } from "@/components/rich-text-editor"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"

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

    // Signature state
    const [signatureName, setSignatureName] = useState("")
    const [signatureTitle, setSignatureTitle] = useState("")
    const [signaturePhone, setSignaturePhone] = useState("")
    const [signatureCompany, setSignatureCompany] = useState("")
    const [signatureEmail, setSignatureEmail] = useState("")
    const [signatureAddress, setSignatureAddress] = useState("")
    const [signatureWebsite, setSignatureWebsite] = useState("")
    const [signatureLogoUrl, setSignatureLogoUrl] = useState("")
    const [signatureCustomHtml, setSignatureCustomHtml] = useState("")
    const [useCustomSignature, setUseCustomSignature] = useState(false)

    // API hooks
    const { data: templates, isLoading } = useEmailTemplates(false)
    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()

    // Signature hooks
    const { data: signatureData } = useSignature()
    const updateSignatureMutation = useUpdateSignature()

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
            setSignatureName(signatureData.signature_name || "")
            setSignatureTitle(signatureData.signature_title || "")
            setSignaturePhone(signatureData.signature_phone || "")
            setSignatureCompany(signatureData.signature_company || "")
            setSignatureEmail(signatureData.signature_email || "")
            setSignatureAddress(signatureData.signature_address || "")
            setSignatureWebsite(signatureData.signature_website || "")
            setSignatureLogoUrl(signatureData.signature_logo_url || "")
            setSignatureCustomHtml(signatureData.signature_html || "")
            setUseCustomSignature(!!signatureData.signature_html)
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
            .replace(/\{\{org_name\}\}/g, signatureCompany || "ABC Surrogacy")
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

        // Append signature if set
        const signature = buildSignatureHtml()
        if (signature) {
            html += `<div style="margin-top: 24px;">${signature}</div>`
        }

        setPreviewHtml(sanitizeHtml(html))
        setShowPreview(true)
    }

    const insertVariable = (varName: string) => {
        setTemplateBody(templateBody + `{{${varName}}}`)
    }

    const buildSignatureHtml = (): string => {
        if (useCustomSignature && signatureCustomHtml.trim()) {
            return signatureCustomHtml
        }

        if (!signatureName && !signatureTitle && !signaturePhone && !signatureCompany && !signatureEmail && !signatureAddress && !signatureWebsite) {
            return ""
        }

        // Organization default logo - replace with your actual logo URL
        const DEFAULT_ORG_LOGO = "/logo.png" // Will use org logo from public folder

        let html = '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-family: system-ui, -apple-system, sans-serif;">'

        // Always show org logo
        html += `<img src="${DEFAULT_ORG_LOGO}" alt="Logo" style="max-height: 50px; margin-bottom: 12px;" />`

        if (signatureName) {
            html += `<p style="margin: 0 0 4px 0; font-weight: 600; color: #1a1a1a;">${signatureName}</p>`
        }
        if (signatureTitle) {
            html += `<p style="margin: 0 0 4px 0; color: #666;">${signatureTitle}</p>`
        }
        if (signatureCompany) {
            html += `<p style="margin: 0 0 8px 0; color: #666;">${signatureCompany}</p>`
        }

        // Contact info section
        const contactItems: string[] = []
        if (signaturePhone) contactItems.push(signaturePhone)
        if (signatureEmail) contactItems.push(`<a href="mailto:${signatureEmail}" style="color: #0066cc; text-decoration: none;">${signatureEmail}</a>`)

        if (contactItems.length > 0) {
            html += `<p style="margin: 0 0 4px 0; color: #666;">${contactItems.join(' | ')}</p>`
        }

        if (signatureAddress) {
            html += `<p style="margin: 0 0 4px 0; color: #666;">${signatureAddress}</p>`
        }
        if (signatureWebsite) {
            html += `<p style="margin: 0; color: #666;"><a href="${signatureWebsite}" style="color: #0066cc; text-decoration: none;">${signatureWebsite}</a></p>`
        }

        html += '</div>'
        return html
    }

    const handleSaveSignature = () => {
        updateSignatureMutation.mutate({
            signature_name: signatureName || null,
            signature_title: signatureTitle || null,
            signature_company: signatureCompany || null,
            signature_phone: signaturePhone || null,
            signature_email: signatureEmail || null,
            signature_address: signatureAddress || null,
            signature_website: signatureWebsite || null,
            signature_logo_url: signatureLogoUrl || null,
            signature_html: useCustomSignature ? signatureCustomHtml || null : buildSignatureHtml() || null,
        })
    }

    const signaturePreviewHtml = sanitizeHtml(buildSignatureHtml())
    const signaturePreviewFallback = '<p class="text-muted-foreground italic">No signature configured</p>'

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
                                    <CardTitle>Email Signature</CardTitle>
                                    <CardDescription>
                                        Configure your personal email signature that will be appended to outgoing emails.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <Label htmlFor="custom-html">Use custom HTML</Label>
                                        <Switch
                                            id="custom-html"
                                            checked={useCustomSignature}
                                            onCheckedChange={setUseCustomSignature}
                                        />
                                    </div>

                                    {useCustomSignature ? (
                                        <div className="space-y-2">
                                            <Label>Custom HTML</Label>
                                            <Textarea
                                                placeholder="<div>Your custom signature HTML...</div>"
                                                value={signatureCustomHtml}
                                                onChange={(e) => setSignatureCustomHtml(e.target.value)}
                                                rows={8}
                                                className="font-mono text-sm"
                                            />
                                        </div>
                                    ) : (
                                        <>
                                            <div className="space-y-2">
                                                <Label htmlFor="sig-name">
                                                    <UserIcon className="inline mr-2 size-4" />
                                                    Full Name
                                                </Label>
                                                <Input
                                                    id="sig-name"
                                                    placeholder="John Smith"
                                                    value={signatureName}
                                                    onChange={(e) => setSignatureName(e.target.value)}
                                                />
                                            </div>

                                            <div className="space-y-2">
                                                <Label htmlFor="sig-title">Title / Role</Label>
                                                <Input
                                                    id="sig-title"
                                                    placeholder="Case Manager"
                                                    value={signatureTitle}
                                                    onChange={(e) => setSignatureTitle(e.target.value)}
                                                />
                                            </div>

                                            <div className="space-y-2">
                                                <Label htmlFor="sig-company">
                                                    <BuildingIcon className="inline mr-2 size-4" />
                                                    Company
                                                </Label>
                                                <Input
                                                    id="sig-company"
                                                    placeholder="ABC Surrogacy Agency"
                                                    value={signatureCompany}
                                                    onChange={(e) => setSignatureCompany(e.target.value)}
                                                />
                                            </div>

                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="space-y-2">
                                                    <Label htmlFor="sig-phone">
                                                        <PhoneIcon className="inline mr-2 size-4" />
                                                        Phone
                                                    </Label>
                                                    <Input
                                                        id="sig-phone"
                                                        placeholder="(555) 123-4567"
                                                        value={signaturePhone}
                                                        onChange={(e) => setSignaturePhone(e.target.value)}
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <Label htmlFor="sig-email">
                                                        <MailIcon className="inline mr-2 size-4" />
                                                        Email
                                                    </Label>
                                                    <Input
                                                        id="sig-email"
                                                        placeholder="john@company.com"
                                                        value={signatureEmail}
                                                        onChange={(e) => setSignatureEmail(e.target.value)}
                                                    />
                                                </div>
                                            </div>

                                            <div className="space-y-2">
                                                <Label htmlFor="sig-address">Address</Label>
                                                <Input
                                                    id="sig-address"
                                                    placeholder="123 Main St, City, State 12345"
                                                    value={signatureAddress}
                                                    onChange={(e) => setSignatureAddress(e.target.value)}
                                                />
                                            </div>

                                            <div className="space-y-2">
                                                <Label htmlFor="sig-website">Website</Label>
                                                <Input
                                                    id="sig-website"
                                                    placeholder="https://www.company.com"
                                                    value={signatureWebsite}
                                                    onChange={(e) => setSignatureWebsite(e.target.value)}
                                                />
                                            </div>
                                        </>
                                    )}

                                    <Button onClick={handleSaveSignature} className="w-full">
                                        Save Signature
                                    </Button>
                                </CardContent>
                            </Card>

                            {/* Preview */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Preview</CardTitle>
                                    <CardDescription>
                                        How your signature will appear in emails
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="border rounded-lg p-4 bg-white min-h-[200px]">
                                        <p className="text-muted-foreground text-sm mb-4">
                                            [Email body content...]
                                        </p>
                                        <div
                                            className="prose prose-sm max-w-none"
                                            dangerouslySetInnerHTML={{ __html: signaturePreviewHtml || signaturePreviewFallback }}
                                        />
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
                                    {signatureName || "Your Name"} &lt;{signatureEmail || "you@company.com"}&gt;
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
                                        .replace(/\{\{org_name\}\}/g, signatureCompany || "ABC Surrogacy")}
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
