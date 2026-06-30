import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { ShareApplicationDialog } from "../components/forms/builder/ShareApplicationDialog"
import type { FormEmbedHealthRead, FormIntakeLinkRead } from "@/lib/api/forms"

const link: FormIntakeLinkRead = {
    id: "link-1",
    form_id: "form-1",
    slug: "lead-form",
    campaign_name: "Website",
    event_name: null,
    utm_defaults: null,
    is_active: true,
    expires_at: null,
    max_submissions: null,
    submissions_count: 0,
    embed_enabled: true,
    allowed_embed_origins: ["https://www.ewisurrogacy.com"],
    tracking_mode: "enhanced_match_lead",
    consent_text: "I agree to be contacted.",
    privacy_policy_url: null,
    thank_you_config: {},
    embed_theme_json: {},
    published_version_id: "version-1",
    intake_url: "https://app.surrogacyforce.com/intake/lead-form",
    created_at: "2026-05-08T00:00:00Z",
    updated_at: "2026-05-08T00:00:00Z",
}

const health: FormEmbedHealthRead = {
    status: "ready",
    updated_at: "2026-05-08T12:00:00Z",
    checks: [
        {
            key: "embed_enabled",
            label: "Embed enabled",
            status: "pass",
            message: "Iframe embedding is enabled.",
        },
        {
            key: "tracking_policy",
            label: "Tracking policy",
            status: "pass",
            message: "Field classification is compatible with the selected tracking mode.",
        },
    ],
}

describe("ShareApplicationDialog", () => {
    it("keeps the share modal constrained and wrap-safe", () => {
        render(
            <ShareApplicationDialog
                open
                selectedQrLink={link}
                onOpenChange={vi.fn()}
                onCopyLink={vi.fn()}
                onDownloadQrSvg={vi.fn()}
                onDownloadQrPng={vi.fn()}
                onUpdateEmbedSettings={vi.fn()}
                embedHealth={health}
            />,
        )

        const dialog = document.body.querySelector('[data-slot="alert-dialog-content"]')
        const tabs = document.body.querySelector('[data-slot="tabs"]')
        const tabList = document.body.querySelector('[data-slot="tabs-list"]')
        const footer = document.body.querySelector('[data-slot="alert-dialog-footer"]')

        expect(dialog).toHaveClass(
            "w-[calc(100vw-2rem)]",
            "max-w-2xl",
            "data-[size=default]:sm:max-w-2xl",
            "overflow-x-hidden",
            "overflow-y-auto",
        )
        expect(tabs).toHaveClass("min-w-0", "overflow-hidden")
        expect(tabList).toHaveClass("min-w-0")
        expect(footer).toHaveClass("flex-col", "sm:flex-wrap")
    })

    it("renders embed health check time as a stable calendar date", () => {
        render(
            <ShareApplicationDialog
                open
                selectedQrLink={link}
                onOpenChange={vi.fn()}
                onCopyLink={vi.fn()}
                onDownloadQrSvg={vi.fn()}
                onDownloadQrPng={vi.fn()}
                onUpdateEmbedSettings={vi.fn()}
                embedHealth={health}
            />,
        )

        fireEvent.click(screen.getByRole("tab", { name: "Embed" }))

        expect(screen.getByText("May 8, 2026", { exact: false })).toBeInTheDocument()
        expect(screen.queryByText("12:00:00 PM", { exact: false })).not.toBeInTheDocument()
    })

    it("shows embed setup health and lets admins refresh diagnostics", () => {
        const onRefreshEmbedHealth = vi.fn()

        render(
            <ShareApplicationDialog
                open
                selectedQrLink={link}
                onOpenChange={vi.fn()}
                onCopyLink={vi.fn()}
                onDownloadQrSvg={vi.fn()}
                onDownloadQrPng={vi.fn()}
                onUpdateEmbedSettings={vi.fn()}
                embedHealth={health}
                onRefreshEmbedHealth={onRefreshEmbedHealth}
            />,
        )

        fireEvent.click(screen.getByRole("tab", { name: "Embed" }))

        expect(screen.getByText("Ready to embed")).toBeInTheDocument()
        expect(screen.getByText("Embed enabled")).toBeInTheDocument()
        expect(screen.getByText("Tracking policy")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /check setup/i }))

        expect(onRefreshEmbedHealth).toHaveBeenCalledTimes(1)
    })

    it("trims pasted embed origins before saving settings", () => {
        const onUpdateEmbedSettings = vi.fn().mockResolvedValue(undefined)

        render(
            <ShareApplicationDialog
                open
                selectedQrLink={link}
                onOpenChange={vi.fn()}
                onCopyLink={vi.fn()}
                onDownloadQrSvg={vi.fn()}
                onDownloadQrPng={vi.fn()}
                onUpdateEmbedSettings={onUpdateEmbedSettings}
                embedHealth={health}
            />,
        )

        fireEvent.click(screen.getByRole("tab", { name: "Embed" }))
        fireEvent.change(screen.getByLabelText("Allowed origins"), {
            target: { value: " https://www.ewisurrogacy.com,\n\n https://ewiapply.com " },
        })
        fireEvent.change(screen.getByLabelText("Consent text"), { target: { value: "   " } })
        fireEvent.click(screen.getByRole("button", { name: "Save Embed Settings" }))

        expect(onUpdateEmbedSettings).toHaveBeenCalledWith({
            link,
            embedEnabled: true,
            allowedOrigins: ["https://www.ewisurrogacy.com", "https://ewiapply.com"],
            trackingMode: "enhanced_match_lead",
            consentText: null,
        })
    })

    it("shows embed settings for the currently selected share link", () => {
        const alternateLink: FormIntakeLinkRead = {
            ...link,
            id: "link-2",
            embed_enabled: false,
            allowed_embed_origins: ["https://apply.example.com"],
            tracking_mode: "privacy_safe_lead",
            consent_text: "Use my information for application follow-up.",
        }

        const { rerender } = render(
            <ShareApplicationDialog
                open
                selectedQrLink={link}
                onOpenChange={vi.fn()}
                onCopyLink={vi.fn()}
                onDownloadQrSvg={vi.fn()}
                onDownloadQrPng={vi.fn()}
                onUpdateEmbedSettings={vi.fn()}
                embedHealth={health}
            />,
        )

        fireEvent.click(screen.getByRole("tab", { name: "Embed" }))
        expect(screen.getByLabelText("Allowed origins")).toHaveValue("https://www.ewisurrogacy.com")

        rerender(
            <ShareApplicationDialog
                open
                selectedQrLink={alternateLink}
                onOpenChange={vi.fn()}
                onCopyLink={vi.fn()}
                onDownloadQrSvg={vi.fn()}
                onDownloadQrPng={vi.fn()}
                onUpdateEmbedSettings={vi.fn()}
                embedHealth={health}
            />,
        )

        expect(screen.getByLabelText("Allowed origins")).toHaveValue("https://apply.example.com")
        expect(screen.getByLabelText("Consent text")).toHaveValue("Use my information for application follow-up.")
        expect(screen.getAllByText("Privacy-safe Lead").length).toBeGreaterThan(0)
    })
})
