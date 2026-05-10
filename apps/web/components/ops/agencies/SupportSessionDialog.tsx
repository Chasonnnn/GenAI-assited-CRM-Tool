"use client"

import { useEffect, useMemo, useReducer } from "react"
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
    getPlatformMe,
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
    disabled?: boolean
}

type SupportSessionState = {
    open: boolean
    role: SupportSessionRole
    mode: SupportSessionMode
    reasonCode: SupportSessionReasonCode
    reasonText: string
    submitting: boolean
    readOnlySupported: boolean | null
}

type SupportSessionAction =
    | { type: "setOpen"; open: boolean }
    | { type: "setRole"; role: SupportSessionRole }
    | { type: "setMode"; mode: SupportSessionMode }
    | { type: "setReasonCode"; reasonCode: SupportSessionReasonCode }
    | { type: "setReasonText"; reasonText: string }
    | { type: "setSubmitting"; submitting: boolean }
    | { type: "setReadOnlySupported"; readOnlySupported: boolean }

const INITIAL_SUPPORT_SESSION_STATE: SupportSessionState = {
    open: false,
    role: "admin",
    mode: "write",
    reasonCode: "bug_repro",
    reasonText: "",
    submitting: false,
    readOnlySupported: null,
}

function supportSessionReducer(
    state: SupportSessionState,
    action: SupportSessionAction,
): SupportSessionState {
    switch (action.type) {
        case "setOpen":
            return { ...state, open: action.open }
        case "setRole":
            return { ...state, role: action.role }
        case "setMode":
            return { ...state, mode: action.mode }
        case "setReasonCode":
            return { ...state, reasonCode: action.reasonCode }
        case "setReasonText":
            return { ...state, reasonText: action.reasonText }
        case "setSubmitting":
            return { ...state, submitting: action.submitting }
        case "setReadOnlySupported":
            return {
                ...state,
                readOnlySupported: action.readOnlySupported,
                mode: !action.readOnlySupported && state.mode === "read_only" ? "write" : state.mode,
            }
    }
}

function applyPopupStyles(element: HTMLElement, cssText: string) {
    element.style.cssText = cssText
}

export function SupportSessionDialog({
    orgId,
    orgName,
    portalBaseUrl,
    disabled = false,
}: SupportSessionDialogProps) {
    const [state, dispatch] = useReducer(supportSessionReducer, INITIAL_SUPPORT_SESSION_STATE)
    const { open, role, mode, reasonCode, reasonText, submitting, readOnlySupported } = state

    const reasonTextTrimmed = reasonText.trim()
    const reasonTextLength = reasonTextTrimmed.length
    const reasonTextTooLong = reasonTextLength > 500

    const normalizedPortalUrl = useMemo(() => {
        const candidate = portalBaseUrl?.trim()
        if (!candidate) return null
        try {
            return new URL(candidate).toString()
        } catch {
            try {
                return new URL(`https://${candidate}`).toString()
            } catch {
                return null
            }
        }
    }, [portalBaseUrl])

    const portalHost = useMemo(() => {
        if (!normalizedPortalUrl) return null
        try {
            return new URL(normalizedPortalUrl).host
        } catch {
            return normalizedPortalUrl.replace(/^https?:\/\//, "")
        }
    }, [normalizedPortalUrl])

    useEffect(() => {
        if (!open) return
        if (readOnlySupported !== null) return

        void getPlatformMe()
            .then((me) => dispatch({
                type: "setReadOnlySupported",
                readOnlySupported: me.support_session_allow_read_only === true,
            }))
            .catch(() => dispatch({ type: "setReadOnlySupported", readOnlySupported: false }))
    }, [open, readOnlySupported])

    const handleStartAndOpen = async () => {
        if (disabled) {
            toast.error("Support sessions are unavailable for this organization.")
            return
        }
        if (!normalizedPortalUrl) {
            toast.error("Portal URL not available for this organization.")
            return
        }
        if (reasonTextTooLong) {
            toast.error("Notes must be 500 characters or less.")
            return
        }

        // Open a placeholder tab synchronously to reduce popup-blocker issues.
        const popup = window.open("", "_blank")
        if (popup) {
            try {
                popup.opener = null
                popup.document.title = `Opening ${orgName}...`
                const body = popup.document.body
                body.innerHTML = ""
                applyPopupStyles(body, "font-family: ui-sans-serif, system-ui, -apple-system; padding: 24px;")

                const meta = popup.document.createElement("div")
                meta.textContent = "Ops Console"
                applyPopupStyles(meta, "font-size: 14px; opacity: 0.7;")

                const title = popup.document.createElement("h1")
                title.textContent = "Starting support session..."
                applyPopupStyles(title, "font-size: 18px; margin: 12px 0 4px;")

                const org = popup.document.createElement("div")
                org.textContent = orgName
                applyPopupStyles(org, "font-size: 14px; opacity: 0.85;")

                body.appendChild(meta)
                body.appendChild(title)
                body.appendChild(org)
            } catch {
                // Ignore popup doc write issues (browser-dependent).
            }
        }

        dispatch({ type: "setSubmitting", submitting: true })
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
            dispatch({ type: "setOpen", open: false })

            if (popup && !popup.closed) {
                popup.location.href = normalizedPortalUrl
            } else {
                const opened = window.open(normalizedPortalUrl, "_blank", "noopener,noreferrer")
                if (!opened) {
                    window.location.href = normalizedPortalUrl
                }
            }
        } catch (error) {
            if (popup) popup.close()
            const message = error instanceof Error ? error.message : "Failed to start support session"
            toast.error(message)
        } finally {
            dispatch({ type: "setSubmitting", submitting: false })
        }
    }

    return (
        <Dialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (submitting) return
                dispatch({ type: "setOpen", open: nextOpen })
            }}
        >
            <DialogTrigger
                className={buttonVariants({ variant: "outline", size: "sm" })}
                disabled={disabled || !normalizedPortalUrl}
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
                        <Select
                            value={role}
                            onValueChange={(v) => dispatch({ type: "setRole", role: v as SupportSessionRole })}
                        >
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
                        <Select
                            value={mode}
                            onValueChange={(v) => dispatch({ type: "setMode", mode: v as SupportSessionMode })}
                        >
                            <SelectTrigger id="support-mode">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="write">Full access</SelectItem>
                                {readOnlySupported === true ? (
                                    <SelectItem value="read_only">Read-only</SelectItem>
                                ) : null}
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            Read-only blocks mutations (POST/PATCH/PUT/DELETE) in the portal.
                        </p>
                        {readOnlySupported === false ? (
                            <p className="text-xs text-muted-foreground">
                                Read-only mode is disabled in this environment.
                            </p>
                        ) : null}
                        {disabled ? (
                            <p className="text-xs text-destructive">
                                This organization is scheduled for deletion; support sessions are disabled.
                            </p>
                        ) : null}
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="support-reason">Reason</Label>
                        <Select
                            value={reasonCode}
                            onValueChange={(v) => dispatch({
                                type: "setReasonCode",
                                reasonCode: v as SupportSessionReasonCode,
                            })}
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
                            onChange={(e) => dispatch({ type: "setReasonText", reasonText: e.target.value })}
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
                        onClick={() => dispatch({ type: "setOpen", open: false })}
                        disabled={submitting}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleStartAndOpen}
                        disabled={disabled || submitting || !normalizedPortalUrl || reasonTextTooLong}
                    >
                        {submitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ArrowUpRight className="mr-2 size-4" />}
                        Start session &amp; open
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
