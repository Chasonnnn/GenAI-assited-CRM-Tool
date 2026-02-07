"use client"

import { useMemo, useState } from "react"
import { toast } from "sonner"
import { ArrowUpRight, Eye, Loader2 } from "lucide-react"

import { Button, buttonVariants } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import {
    createSupportSession,
    type SupportSessionMode,
    type SupportSessionReasonCode,
    type SupportSessionRole,
} from "@/lib/api/platform"

const ROLE_LABELS: Record<SupportSessionRole, string> = {
    intake_specialist: "Intake Specialist",
    case_manager: "Case Manager",
    admin: "Admin",
    developer: "Developer",
}

const MODE_LABELS: Record<SupportSessionMode, string> = {
    write: "Full access",
    read_only: "Read-only",
}

const REASON_LABELS: Record<SupportSessionReasonCode, string> = {
    onboarding_setup: "Onboarding setup",
    billing_help: "Billing help",
    data_fix: "Data fix",
    bug_repro: "Bug reproduction",
    incident_response: "Incident response",
    other: "Other",
}

type SupportSessionDialogProps = {
    orgId: string
    orgName: string
    portalBaseUrl: string | null | undefined
}

export function SupportSessionDialog({ orgId, orgName, portalBaseUrl }: SupportSessionDialogProps) {
    const [open, setOpen] = useState(false)
    const [role, setRole] = useState<SupportSessionRole>("admin")
    const [mode, setMode] = useState<SupportSessionMode>("write")
    const [reasonCode, setReasonCode] = useState<SupportSessionReasonCode>("bug_repro")
    const [reasonText, setReasonText] = useState("")
    const [submitting, setSubmitting] = useState(false)

    const reasonTextTrimmed = reasonText.trim()
    const reasonTextLength = reasonTextTrimmed.length
    const reasonTextTooLong = reasonTextLength > 500

    const portalHost = useMemo(() => {
        if (!portalBaseUrl) return null
        try {
            return new URL(portalBaseUrl).host
        } catch {
            return portalBaseUrl.replace(/^https?:\/\//, "")
        }
    }, [portalBaseUrl])

    const handleStartAndOpen = async () => {
        if (!portalBaseUrl) {
            toast.error("Portal URL not available for this organization.")
            return
        }
        if (reasonTextTooLong) {
            toast.error("Notes must be 500 characters or less.")
            return
        }

        // Open a placeholder tab synchronously to reduce popup-blocker issues.
        const popup = window.open("about:blank", "_blank", "noopener,noreferrer")
        if (popup) {
            try {
                popup.opener = null
                popup.document.title = `Opening ${orgName}...`
                const body = popup.document.body
                body.innerHTML = ""
                body.style.fontFamily = "ui-sans-serif, system-ui, -apple-system"
                body.style.padding = "24px"

                const meta = popup.document.createElement("div")
                meta.textContent = "Ops Console"
                meta.style.fontSize = "14px"
                meta.style.opacity = "0.7"

                const title = popup.document.createElement("h1")
                title.textContent = "Starting support session..."
                title.style.fontSize = "18px"
                title.style.margin = "12px 0 4px"

                const org = popup.document.createElement("div")
                org.textContent = orgName
                org.style.fontSize = "14px"
                org.style.opacity = "0.85"

                body.appendChild(meta)
                body.appendChild(title)
                body.appendChild(org)
            } catch {
                // Ignore popup doc write issues (browser-dependent).
            }
        }

        setSubmitting(true)
        try {
            const session = await createSupportSession({
                org_id: orgId,
                role,
                mode,
                reason_code: reasonCode,
                reason_text: reasonTextTrimmed ? reasonTextTrimmed : null,
            })

            toast.success(
                `Support session started: ${ROLE_LABELS[session.role]} (${MODE_LABELS[session.mode]})`
            )
            setOpen(false)

            if (popup) {
                popup.location.href = portalBaseUrl
            } else {
                toast.error("Popup blocked. Support session started; open the portal link manually.")
            }
        } catch (error) {
            if (popup) popup.close()
            const message = error instanceof Error ? error.message : "Failed to start support session"
            toast.error(message)
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <Dialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (submitting) return
                setOpen(nextOpen)
            }}
        >
            <DialogTrigger
                className={buttonVariants({ variant: "outline", size: "sm" })}
                disabled={!portalBaseUrl}
            >
                <Eye className="mr-2 size-4" />
                View as role
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle>View as role</DialogTitle>
                    <DialogDescription>
                        Create a time-boxed support session for <span className="font-medium">{orgName}</span>{" "}
                        and open the portal with a role override.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <div className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-200">
                        <div className="flex items-center justify-between gap-3">
                            <span className="text-xs text-stone-500 dark:text-stone-400">Portal</span>
                            <span className="font-mono text-xs">{portalHost ?? "Unavailable"}</span>
                        </div>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="support-role">Role</Label>
                        <Select value={role} onValueChange={(v) => setRole(v as SupportSessionRole)}>
                            <SelectTrigger id="support-role">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {(Object.keys(ROLE_LABELS) as SupportSessionRole[]).map((r) => (
                                    <SelectItem key={r} value={r}>
                                        {ROLE_LABELS[r]}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="support-mode">Access mode</Label>
                        <Select value={mode} onValueChange={(v) => setMode(v as SupportSessionMode)}>
                            <SelectTrigger id="support-mode">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="write">Full access</SelectItem>
                                <SelectItem value="read_only">Read-only</SelectItem>
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            Read-only blocks mutations (POST/PATCH/PUT/DELETE) in the portal.
                        </p>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="support-reason">Reason</Label>
                        <Select
                            value={reasonCode}
                            onValueChange={(v) => setReasonCode(v as SupportSessionReasonCode)}
                        >
                            <SelectTrigger id="support-reason">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {(Object.keys(REASON_LABELS) as SupportSessionReasonCode[]).map((code) => (
                                    <SelectItem key={code} value={code}>
                                        {REASON_LABELS[code]}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="support-notes">Notes (optional)</Label>
                        <Textarea
                            id="support-notes"
                            value={reasonText}
                            onChange={(e) => setReasonText(e.target.value)}
                            placeholder="Add context for the audit trail (max 500 chars)."
                        />
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>Included in ops audit logs.</span>
                            <span className={reasonTextTooLong ? "text-destructive" : ""}>
                                {reasonTextLength}/500
                            </span>
                        </div>
                        {reasonTextTooLong ? (
                            <p className="text-xs text-destructive">Notes must be 500 characters or less.</p>
                        ) : null}
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => setOpen(false)}
                        disabled={submitting}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleStartAndOpen}
                        disabled={submitting || !portalBaseUrl || reasonTextTooLong}
                    >
                        {submitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ArrowUpRight className="mr-2 size-4" />}
                        Start session &amp; open
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
