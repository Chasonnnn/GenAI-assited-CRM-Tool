"use client"

import { useMemo, useState, useEffect } from "react"
import dynamic from "next/dynamic"
import DOMPurify from "dompurify"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
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

const APPLE_INVITE_SUBJECT = "Invitation to join {{org_name}} as {{role_title}}"
const APPLE_INVITE_BODY = `<div style="background-color: #f5f5f7; padding: 40px 12px; margin: 0;">
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
              <div style="font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 40px 0 40px; text-align: center;">
              <h1 style="margin: 0; font-size: 26px; line-height: 1.35; color: #111827; font-weight: 600;">
                You're invited to join {{org_name}}
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 48px 0 48px; text-align: center;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You've been invited{{inviter_text}} to join <strong>{{org_name}}</strong> as a
                <strong>{{role_title}}</strong>.
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

type AgencyTemplatesTabProps = {
    orgName: string
    orgSlug: string
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
    orgSlug,
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
    const [editorMode, setEditorMode] = useState<EditorMode>("visual")
    const [editorModeTouched, setEditorModeTouched] = useState(false)

    const applyAppleTemplate = () => {
        onTemplateSubjectChange(APPLE_INVITE_SUBJECT)
        onTemplateBodyChange(APPLE_INVITE_BODY)
    }

    const hasComplexHtml = useMemo(
        () => /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(templateBody),
        [templateBody]
    )

    useEffect(() => {
        if (editorModeTouched) return
        if (templateBody && hasComplexHtml) {
            setEditorMode("html")
        }
    }, [templateBody, editorModeTouched, hasComplexHtml])

    const previewSubject = useMemo(
        () =>
            templateSubject
                .replace(/\{\{org_name\}\}/g, orgName || "Organization")
                .replace(/\{\{org_slug\}\}/g, orgSlug || "org"),
        [templateSubject, orgName, orgSlug]
    )

    const previewBody = useMemo(() => {
        const baseUrl = portalBaseUrl || "https://app.example.com"
        const rawHtml = templateBody
            .replace(/\{\{org_name\}\}/g, orgName || "Organization")
            .replace(/\{\{org_slug\}\}/g, orgSlug || "org")
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
    }, [templateBody, orgName, orgSlug, portalBaseUrl])

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
                                    {editorMode === "html" ? (
                                        <Label htmlFor="invite-template-body">Email Body</Label>
                                    ) : (
                                        <span className="text-sm font-medium leading-none">
                                            Email Body
                                        </span>
                                    )}
                                    <div className="flex flex-wrap items-center gap-2">
                                        <ToggleGroup
                                            multiple={false}
                                            value={editorMode ? [editorMode] : []}
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
                                        <Badge variant="outline" className="text-xs">
                                            <Code className="size-3 mr-1" />
                                            Variables
                                        </Badge>
                                    </div>
                                </div>
                                {editorMode === "visual" ? (
                                    <RichTextEditor
                                        content={templateBody}
                                        onChange={(html) => onTemplateBodyChange(html)}
                                        placeholder="Write your invite email content..."
                                        minHeight="220px"
                                        maxHeight="420px"
                                        enableImages
                                    />
                                ) : (
                                    <Textarea
                                        id="invite-template-body"
                                        value={templateBody}
                                        onChange={(event) => onTemplateBodyChange(event.target.value)}
                                        placeholder="Paste or edit the HTML for the invite email..."
                                        className="min-h-[220px] font-mono text-xs leading-relaxed"
                                    />
                                )}
                                {editorMode === "visual" && hasComplexHtml && (
                                    <p className="text-xs text-amber-600">
                                        This template contains advanced HTML. Switch to HTML mode to preserve layout.
                                    </p>
                                )}
                                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                                    <span>
                                        Available variables: <span className="font-mono">{"{{org_name}}"}</span>,{" "}
                                        <span className="font-mono">{"{{org_slug}}"}</span>,{" "}
                                        <span className="font-mono">{"{{org_logo_url}}"}</span>,{" "}
                                        <span className="font-mono">{"{{invite_url}}"}</span>,{" "}
                                        <span className="font-mono">{"{{role_title}}"}</span>,{" "}
                                        <span className="font-mono">{"{{inviter_text}}"}</span>,{" "}
                                        <span className="font-mono">{"{{expires_block}}"}</span>
                                    </span>
                                    <Button type="button" variant="ghost" size="sm" onClick={applyAppleTemplate}>
                                        Use Apple-style layout
                                    </Button>
                                </div>
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
                                className="text-sm text-slate-900"
                                dangerouslySetInnerHTML={{ __html: previewBody }}
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
