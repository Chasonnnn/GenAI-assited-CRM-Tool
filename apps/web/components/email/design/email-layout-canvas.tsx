"use client"

import type { CSSProperties, ReactNode } from "react"
import Image from "next/image"
import { Loader2Icon } from "lucide-react"

import { EmailHtmlFrame } from "@/components/email/design/email-html-frame"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { SegmentedControl, SegmentedControlItem } from "@/components/ui/segmented-control"
import { Switch } from "@/components/ui/switch"
import type { EmailLayout, EmailLayoutFrame, EmailLayoutKind } from "@/lib/api/email-templates"
import { EMAIL_BODY_STYLE } from "@/lib/email-design"
import { cn } from "@/lib/utils"

export type EmailCanvasViewport = "desktop" | "mobile"

type FrameState = {
    data: EmailLayoutFrame | undefined
    isError: boolean
    onRetry: () => void
}

type EmailLayoutCanvasProps = {
    layout: EmailLayout
    frame: FrameState
    viewport: EmailCanvasViewport
    /** From, To, and Subject rows above the email. */
    header: ReactNode
    /** The editable body. */
    children: ReactNode
    error?: ReactNode
}

/** Inline style text from EMAIL_BODY_STYLE, so the editable body reads in the sent text style. */
const BODY_STYLE: CSSProperties = Object.fromEntries(
    EMAIL_BODY_STYLE.split(";")
        .filter(Boolean)
        .map((declaration) => {
            const [property = "", ...value] = declaration.split(":")
            return [property.replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase()), value.join(":")]
        }),
)

function LayoutLogo({ frame, layout }: { frame: EmailLayoutFrame; layout: EmailLayout }) {
    if (!frame.logo_url) return null
    return (
        <Image
            src={frame.logo_url}
            alt={frame.logo_alt}
            width={200}
            height={64}
            unoptimized
            className={cn(
                "block h-auto max-h-16 w-auto max-w-[200px] object-contain",
                layout.logo_position === "center" && "mx-auto",
            )}
        />
    )
}

/**
 * The Edit canvas: the email as the recipient sees it, with the body editable in place.
 * Mirrors email_composition_service._wrap_layout; the server renders the signature and footer.
 */
export function EmailLayoutCanvas({ layout, frame, viewport, header, children, error }: EmailLayoutCanvasProps) {
    const data = frame.data
    const content = (
        <div style={BODY_STYLE}>
            {children}
            {data ? (
                <div aria-label="Signature and footer" className="pointer-events-none select-none">
                    <EmailHtmlFrame
                        html={`${data.signature_html}${data.footer_html}`}
                        title="Signature and unsubscribe footer"
                        autoHeight
                        minHeight={24}
                        className="bg-transparent"
                    />
                </div>
            ) : frame.isError ? (
                <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                    Signature could not load.
                    <Button type="button" size="sm" variant="outline" onClick={frame.onRetry}>
                        Retry
                    </Button>
                </div>
            ) : (
                <div role="status" className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                    Loading signature…
                </div>
            )}
        </div>
    )

    let email: ReactNode
    if (layout.kind === "card") {
        email = (
            <div data-email-layout="card" className="px-3 py-6" style={{ backgroundColor: layout.page_background }}>
                <div className="mx-auto max-w-[600px] rounded-lg bg-white">
                    {data?.logo_url ? (
                        <div className="px-6 pt-8">
                            <LayoutLogo frame={data} layout={layout} />
                        </div>
                    ) : null}
                    <div className="px-6 pt-7 pb-8">{content}</div>
                </div>
            </div>
        )
    } else if (layout.kind === "letterhead") {
        email = (
            <div data-email-layout="letterhead" className="px-4">
                <div className="mx-auto max-w-[600px]">
                    {data?.logo_url ? (
                        <div className="pt-6 pb-4">
                            <LayoutLogo frame={data} layout={layout} />
                        </div>
                    ) : null}
                    <div
                        data-testid="letterhead-rule"
                        className="border-t-[3px]"
                        style={{ borderTopColor: data?.accent_color ?? layout.accent_color ?? "#111827" }}
                    />
                    <div className="pt-5 pb-8">{content}</div>
                </div>
            </div>
        )
    } else {
        email = (
            <div data-email-layout="plain" className="px-6 pt-6 pb-8">
                <div className="mx-auto max-w-[600px]">{content}</div>
            </div>
        )
    }

    return (
        <div className="mx-auto flex w-full max-w-[680px] flex-col gap-3">
            <div
                className={cn(
                    "mx-auto w-full overflow-hidden rounded-lg border border-border bg-white text-black shadow-xs transition-[max-width]",
                    viewport === "mobile" ? "max-w-[375px]" : "max-w-[680px]",
                )}
            >
                <div className="border-b border-border bg-card px-4 py-1 text-foreground">{header}</div>
                {email}
            </div>
            {error}
        </div>
    )
}

const LAYOUT_CHOICES: Array<{ kind: EmailLayoutKind; label: string; description: string }> = [
    { kind: "plain", label: "Plain", description: "Text and formatting, with side space" },
    { kind: "card", label: "Card", description: "Grey page, white card, logo on top" },
    { kind: "letterhead", label: "Letterhead", description: "Logo and accent rule, no box" },
]

type EmailLayoutSettingsProps = {
    value: EmailLayout
    onChange: (layout: EmailLayout) => void
    /** The accent color the org signature gives Letterhead when none is chosen. */
    defaultAccent: string
    disabled?: boolean
}

export function EmailLayoutSettings({ value, onChange, defaultAccent, disabled = false }: EmailLayoutSettingsProps) {
    const update = (changes: Partial<EmailLayout>) => onChange({ ...value, ...changes })
    const framed = value.kind !== "plain"

    return (
        <section aria-labelledby="email-layout-title" className="grid gap-3 border-b border-border p-3 text-sm">
            <h2 id="email-layout-title" className="text-xs font-medium text-muted-foreground">
                Layout
            </h2>
            <RadioGroup
                aria-labelledby="email-layout-title"
                value={value.kind}
                disabled={disabled}
                onValueChange={(kind) => update({ kind: kind as EmailLayoutKind })}
                className="gap-1.5"
            >
                {LAYOUT_CHOICES.map((choice) => (
                    <label
                        key={choice.kind}
                        className={cn(
                            "grid cursor-pointer grid-cols-[auto_1fr] items-start gap-x-2.5 gap-y-0.5 rounded-md border border-border p-2.5",
                            "has-data-checked:border-primary has-data-checked:ring-1 has-data-checked:ring-primary",
                            disabled && "cursor-not-allowed opacity-60",
                        )}
                    >
                        <RadioGroupItem value={choice.kind} className="mt-0.5" />
                        <span className="font-medium">{choice.label}</span>
                        <span className="col-start-2 text-xs text-muted-foreground">{choice.description}</span>
                    </label>
                ))}
            </RadioGroup>
            {framed ? (
                <div className="grid gap-3">
                    <div className="flex items-center justify-between gap-3">
                        <Label htmlFor="email-layout-show-logo">Show logo</Label>
                        <Switch
                            id="email-layout-show-logo"
                            checked={value.show_logo}
                            disabled={disabled}
                            onCheckedChange={(showLogo) => update({ show_logo: showLogo })}
                        />
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <span id="email-layout-logo-position">Logo position</span>
                        <SegmentedControl
                            aria-labelledby="email-layout-logo-position"
                            value={value.logo_position}
                            disabled={disabled || !value.show_logo}
                            onValueChange={(position) => update({ logo_position: position as EmailLayout["logo_position"] })}
                        >
                            <SegmentedControlItem value="left">Left</SegmentedControlItem>
                            <SegmentedControlItem value="center">Center</SegmentedControlItem>
                        </SegmentedControl>
                    </div>
                    {value.kind === "letterhead" ? (
                        <div className="flex items-center justify-between gap-3">
                            <Label htmlFor="email-layout-accent">Accent color</Label>
                            <Input
                                id="email-layout-accent"
                                type="color"
                                value={value.accent_color ?? defaultAccent}
                                disabled={disabled}
                                onChange={(event) => update({ accent_color: event.target.value })}
                                className="h-8 w-12 cursor-pointer p-1"
                            />
                        </div>
                    ) : (
                        <div className="flex items-center justify-between gap-3">
                            <Label htmlFor="email-layout-page-background">Page background</Label>
                            <Input
                                id="email-layout-page-background"
                                type="color"
                                value={value.page_background}
                                disabled={disabled}
                                onChange={(event) => update({ page_background: event.target.value })}
                                className="h-8 w-12 cursor-pointer p-1"
                            />
                        </div>
                    )}
                </div>
            ) : null}
        </section>
    )
}
