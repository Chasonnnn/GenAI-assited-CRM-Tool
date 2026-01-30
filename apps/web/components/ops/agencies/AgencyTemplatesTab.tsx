"use client"

import { useMemo } from "react"
import dynamic from "next/dynamic"
import DOMPurify from "dompurify"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Code, Loader2 } from "lucide-react"
import type { PlatformEmailStatus, SystemEmailTemplate } from "@/lib/api/platform"
import { format } from "date-fns"

const RichTextEditor = dynamic(
    () => import("@/components/rich-text-editor").then((mod) => mod.RichTextEditor),
    {
        ssr: false,
        loading: () => (
            <div className="rounded-md border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                Loading editor...
            </div>
        ),
    }
)

type AgencyTemplatesTabProps = {
    orgName: string
    portalBaseUrl: string | null
    platformEmailStatus: PlatformEmailStatus | null
    platformEmailLoading: boolean
    inviteTemplate: SystemEmailTemplate | null
    inviteTemplateLoading: boolean
    templateFromEmail: string
    templateSubject: string
    templateBody: string
    templateActive: boolean
    templateVersion: number | null
    onTemplateFromEmailChange: (value: string) => void
    onTemplateSubjectChange: (value: string) => void
    onTemplateBodyChange: (value: string) => void
    onTemplateActiveChange: (value: boolean) => void
    onSaveTemplate: () => void
    inviteTemplateSaving: boolean
    testEmail: string
    onTestEmailChange: (value: string) => void
    onSendTestEmail: () => void
    testSending: boolean
}

export function AgencyTemplatesTab({
    orgName,
    portalBaseUrl,
    platformEmailStatus,
    platformEmailLoading,
    inviteTemplate,
    inviteTemplateLoading,
    templateFromEmail,
    templateSubject,
    templateBody,
    templateActive,
    templateVersion,
    onTemplateFromEmailChange,
    onTemplateSubjectChange,
    onTemplateBodyChange,
    onTemplateActiveChange,
    onSaveTemplate,
    inviteTemplateSaving,
    testEmail,
    onTestEmailChange,
    onSendTestEmail,
    testSending,
}: AgencyTemplatesTabProps) {
    const previewSubject = useMemo(
        () =>
            templateSubject.replace(/\{\{org_name\}\}/g, orgName || "Organization"),
        [templateSubject, orgName]
    )

    const previewBody = useMemo(() => {
        const baseUrl = portalBaseUrl || "https://app.example.com"
        const rawHtml = templateBody
            .replace(/\{\{org_name\}\}/g, orgName || "Organization")
            .replace(/\{\{inviter_text\}\}/g, " by Platform Admin")
            .replace(/\{\{role_title\}\}/g, "Admin")
            .replace(/\{\{invite_url\}\}/g, `${baseUrl}/invite/EXAMPLE`)
            .replace(/\{\{expires_block\}\}/g, "<p>This invitation expires in 7 days.</p>")
        return DOMPurify.sanitize(rawHtml, {
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
    }, [templateBody, orgName, portalBaseUrl])

    return (
        <div className="grid gap-6 lg:grid-cols-2">
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg flex items-center justify-between">
                        Invite Email Template
                        <Badge variant="outline" className="font-mono text-xs">
                            org_invite
                        </Badge>
                    </CardTitle>
                    <CardDescription>
                        Used for user invites to this agency. Sent via the platform sender (Resend).
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                    {platformEmailLoading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="size-4 animate-spin" />
                            Loading email sender status...
                        </div>
                    ) : platformEmailStatus?.configured ? (
                        <div className="rounded-md border bg-stone-50 dark:bg-stone-900 p-3 text-sm">
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Sender configured</span>
                                <Badge variant="secondary">Resend</Badge>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                                From: managed per-template
                                {platformEmailStatus.from_email ? (
                                    <span className="ml-1 font-mono">
                                        (fallback: {platformEmailStatus.from_email})
                                    </span>
                                ) : null}
                            </div>
                        </div>
                    ) : (
                        <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">
                            Platform sender is not configured. Set PLATFORM_RESEND_API_KEY to enable
                            platform/system emails via Resend.
                        </div>
                    )}

                    {inviteTemplateLoading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="size-4 animate-spin" />
                            Loading template...
                        </div>
                    ) : (
                        <>
                            <div className="space-y-2">
                                <Label>From (required for Resend)</Label>
                                <Input
                                    value={templateFromEmail}
                                    onChange={(event) => onTemplateFromEmailChange(event.target.value)}
                                    placeholder="Invites <invites@surrogacyforce.com>"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Choose the sender for this template. You can use different senders per
                                    template without Terraform changes (must be on a verified domain in
                                    Resend).
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label>Subject</Label>
                                <Input
                                    value={templateSubject}
                                    onChange={(event) => onTemplateSubjectChange(event.target.value)}
                                    placeholder="You're invited to join {{org_name}}"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Variables: <span className="font-mono">{"{{org_name}}"}</span>
                                </p>
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <Label>Email Body (HTML)</Label>
                                    <Badge variant="outline" className="text-xs">
                                        <Code className="size-3 mr-1" />
                                        Variables
                                    </Badge>
                                </div>
                                <RichTextEditor
                                    content={templateBody}
                                    onChange={(html) => onTemplateBodyChange(html)}
                                    placeholder="Write your invite email content..."
                                    minHeight="220px"
                                    maxHeight="420px"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Available variables:{" "}
                                    <span className="font-mono">{"{{invite_url}}"}</span>,{" "}
                                    <span className="font-mono">{"{{role_title}}"}</span>,{" "}
                                    <span className="font-mono">{"{{inviter_text}}"}</span>,{" "}
                                    <span className="font-mono">{"{{expires_block}}"}</span>
                                </p>
                            </div>

                            <div className="flex items-center justify-between rounded-md border p-3">
                                <div>
                                    <div className="font-medium">Template active</div>
                                    <div className="text-xs text-muted-foreground">
                                        If disabled, invites use the default built-in template.
                                    </div>
                                </div>
                                <Switch
                                    checked={templateActive}
                                    onCheckedChange={onTemplateActiveChange}
                                />
                            </div>

                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <span>
                                    Version:{" "}
                                    <span className="font-mono">
                                        {templateVersion ?? inviteTemplate?.current_version ?? "-"}
                                    </span>
                                </span>
                                <span>
                                    Updated:{" "}
                                    {inviteTemplate?.updated_at
                                        ? format(new Date(inviteTemplate.updated_at), "MMM d, yyyy h:mm a")
                                        : "-"}
                                </span>
                            </div>

                            <div className="flex gap-2">
                                <Button onClick={onSaveTemplate} disabled={inviteTemplateSaving}>
                                    {inviteTemplateSaving && (
                                        <Loader2 className="mr-2 size-4 animate-spin" />
                                    )}
                                    Save Template
                                </Button>
                            </div>

                            <div className="rounded-md border p-4 space-y-3">
                                <div className="font-medium">Send Test Email</div>
                                <div className="grid gap-2">
                                    <Label className="text-xs">To</Label>
                                    <Input
                                        value={testEmail}
                                        onChange={(event) => onTestEmailChange(event.target.value)}
                                        placeholder="name@example.com"
                                    />
                                </div>
                                <Button
                                    variant="secondary"
                                    onClick={onSendTestEmail}
                                    disabled={
                                        !platformEmailStatus?.configured ||
                                        testSending ||
                                        !(templateFromEmail.trim() || platformEmailStatus?.from_email)
                                    }
                                >
                                    {testSending && (
                                        <Loader2 className="mr-2 size-4 animate-spin" />
                                    )}
                                    Send Test
                                </Button>
                                {!platformEmailStatus?.configured && (
                                    <p className="text-xs text-muted-foreground">
                                        Configure platform email sender to enable test sends.
                                    </p>
                                )}
                                {platformEmailStatus?.configured &&
                                    !templateFromEmail.trim() &&
                                    !platformEmailStatus?.from_email && (
                                        <p className="text-xs text-muted-foreground">
                                            Set a From address above to enable test sends.
                                        </p>
                                    )}
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Preview</CardTitle>
                    <CardDescription>Sample rendering with mock values.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-lg border bg-white overflow-hidden">
                        <div className="border-b bg-muted/30 px-4 py-3 text-sm space-y-2">
                            <div className="flex items-center gap-2">
                                <span className="w-16 text-muted-foreground font-medium">From:</span>
                                <span className="font-mono text-xs">
                                    {templateFromEmail.trim() ||
                                        platformEmailStatus?.from_email ||
                                        "you@company.com"}
                                </span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-16 text-muted-foreground font-medium">To:</span>
                                <span className="font-mono text-xs">person@example.com</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-16 text-muted-foreground font-medium">
                                    Subject:
                                </span>
                                <span className="font-medium">{previewSubject}</span>
                            </div>
                        </div>
                        <div className="p-4">
                            <div
                                className="prose prose-sm max-w-none [&_p]:whitespace-pre-wrap"
                                dangerouslySetInnerHTML={{ __html: previewBody }}
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
