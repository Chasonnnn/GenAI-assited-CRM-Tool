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
})
