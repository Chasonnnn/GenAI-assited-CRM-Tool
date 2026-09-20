import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

function readWebSource(path: string): string {
    return readFileSync(join(process.cwd(), path), "utf8")
}

describe("UI description policy", () => {
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
