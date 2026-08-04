import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

function readWebSource(path: string): string {
    return readFileSync(join(process.cwd(), path), "utf8")
}

const removalsByFile: Record<string, string[]> = {
    "components/automation/workflow-templates-panel.tsx": [
        "Use templates to quickly create workflows",
    ],
    "app/(app)/matches/page.tsx": ["Surrogate and intended parent matching"],
    "app/(app)/automation/campaigns/page.tsx": [
        "Send targeted emails to groups of surrogates",
    ],
    "app/(app)/surrogates/import/page.tsx": ["Bulk import surrogates from CSV files"],
    "app/(app)/settings/notifications/page.tsx": [
        "Manage how you receive notifications and alerts",
        "Receive real-time notifications in your browser when important events occur.",
        "Choose which updates appear in-app for",
    ],
    "app/(app)/settings/queues/page.tsx": ["Manage case queues for your organization"],
    "app/(app)/settings/team/page.tsx": ["Manage team members, roles, and permissions"],
    "app/(app)/settings/security/page.tsx": [
        "Manage your Duo enrollment and account recovery settings.",
    ],
    "app/(app)/settings/sessions/page.tsx": [
        "Manage devices where you're currently logged in.",
        "This is the device you're using right now.",
    ],
    "app/(app)/settings/integrations/zoom/page.tsx": [
        "Manage your Zoom connection and view appointment history",
        "Recent Zoom appointments created via the app",
    ],
    "app/(app)/settings/integrations/meta/page.client.tsx": [
        "Connect Meta accounts to sync lead forms and conversions.",
        "Connect Meta accounts and manage assets for lead ads.",
        "Configure CAPI settings and sync visibility.",
    ],
    "app/(app)/ai-assistant/page.tsx": ["Get help with your tasks and workflows"],
    "app/(app)/search/page.tsx": [
        "Search across surrogates, notes, files, and intended parents",
    ],
    "components/reports/MetaSpendDashboard.tsx": [
        "Daily spend over time",
        "Spend breakdown by campaign",
        "Analyze spend by different dimensions",
        "Lead conversion by form",
        "Lead distribution by platform",
        "Top ads by lead volume",
    ],
    "components/appointments/AppointmentSettings.tsx": [
        "Share this link to let clients book appointments with you",
        "Set your regular working hours for each day of the week",
        "Different appointment types clients can book",
    ],
    "app/(app)/settings/page.tsx": [
        "Profile and access settings",
        "2FA and session controls",
        "Configure org-wide intelligent suggestion thresholds and digest behavior.",
        "Organization-wide email signature configuration. These settings apply to all users.",
    ],
    "components/ops/agencies/AgencyAuditTab.tsx": [
        "Platform admin actions related to this organization",
    ],
    "app/(app)/settings/audit/page.tsx": [
        "Track all changes and actions in your organization",
    ],
    "app/(app)/settings/integrations/page.tsx": ["Enable AI-powered features"],
    "app/(app)/settings/integrations/meta/forms/page.tsx": [
        "Map Meta lead forms to surrogate fields.",
        "Choose a form to configure mappings.",
    ],
    "app/(app)/settings/integrations/meta/forms/[id]/page.tsx": [
        "Map Meta fields to surrogate fields.",
    ],
    "app/ops/login/page.client.tsx": ["Sign in to manage agencies and platform operations"],
    "app/ops/templates/workflows/[id]/page.client.tsx": [
        "Snapshot of current configuration.",
        "Template best practices.",
    ],
    "components/matches/ProposeMatchDialog.tsx": ["Create a match proposal for"],
    "components/matches/ProposeMatchFromIPDialog.tsx": ["Create a match proposal for"],
    "components/email/EmailComposeDialog.tsx": ["Compose and send an email to"],
    "components/matches/AddNoteDialog.tsx": [
        "Add a note to the surrogate or intended parent record.",
    ],
    "components/matches/UploadFileDialog.tsx": [
        "Upload a file to the Surrogate or Intended Parent record.",
    ],
    "components/ops/agencies/AgencyInvitesTab.tsx": ["Send an invitation to join"],
    "app/(app)/settings/team/roles/page.tsx": [
        "Configure default permissions for each role in your organization.",
    ],
    "app/(app)/settings/team/roles/[role]/page.client.tsx": [
        "Toggle permissions on/off to customize this role's default access.",
        "View default permissions for this role. Only Developers can modify.",
    ],
}

describe("UI description policy", () => {
    it("documents the concise UI copy default in the canonical agent policy", () => {
        const policy = readFileSync(join(process.cwd(), "../../agents.md"), "utf8")

        expect(policy).toContain(
            "UI descriptions: Do not add subtitles, helper text, or descriptive copy beneath headings, labels, cards, or settings by default.",
        )
        expect(policy).toContain(
            "Only add supporting copy when the user explicitly asks for it or when it is necessary to prevent misunderstanding or error",
        )
    })

    it("removes all approved redundant descriptions", () => {
        const approvedCopyVariants = Object.values(removalsByFile).reduce(
            (count, snippets) => count + snippets.length,
            0,
        )
        const roleDetailConditionalAlternatives = 1
        const approvedPlacementCount = approvedCopyVariants - roleDetailConditionalAlternatives

        expect(approvedPlacementCount).toBe(49)

        for (const [path, snippets] of Object.entries(removalsByFile)) {
            const source = readWebSource(path)
            for (const snippet of snippets) {
                expect(source, `${path}: ${snippet}`).not.toContain(snippet)
            }
        }
    })

    it("keeps approved consequence, boundary, validation, and recovery copy", () => {
        expect(readWebSource("app/ops/agencies/new/page.client.tsx")).toContain(
            "Create a new agency and send an invitation to their first administrator.",
        )
        expect(readWebSource("components/ops/agencies/AgencyOverviewTab.tsx")).toContain(
            "Soft delete this organization for 30 days, then permanently remove all data.",
        )
        expect(readWebSource("components/email/organization-email-template-studio.tsx")).toContain(
            "Changes stay isolated from production until you publish.",
        )
        expect(readWebSource("components/email-operations/EmailReconciliationActionDialogs.tsx")).toContain(
            "It does not send or",
        )
        expect(readWebSource("components/import/CSVUpload.tsx")).toContain(
            "Rows with validation errors will be skipped and logged.",
        )
        expect(readWebSource("app/(app)/settings/integrations/page.tsx")).toContain(
            "An admin must accept the AI data processing consent before enabling AI features.",
        )
        expect(readWebSource("app/login/LoginPageClient.tsx")).toContain(
            "Sign in with Google SSO, then complete Duo verification",
        )
    })
})
