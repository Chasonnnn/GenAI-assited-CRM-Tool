import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogTitle,
} from "@/components/ui/dialog"

import {
    classTokens,
    countByFile,
    exceedAllowlist,
    scanJsxElements,
    SOURCE_SCAN_TIMEOUT_MS,
} from "./fixtures/jsx-class-scan"

function renderDialog(props: React.ComponentProps<typeof DialogContent>) {
    render(
        <Dialog open>
            <DialogContent {...props}>
                <DialogTitle>Edit surrogate</DialogTitle>
            </DialogContent>
        </Dialog>,
    )
    return screen.getByRole("dialog")
}

describe("DialogContent width", () => {
    it("defaults to the md width with a mobile gutter and no breakpoint-only max width", () => {
        const dialog = renderDialog({})

        expect(dialog).toHaveAttribute("data-size", "md")
        expect(dialog).toHaveClass("max-w-md", "w-[calc(100%-2rem)]")
        expect(dialog.className).not.toMatch(/(^|\s)sm:max-w-/)
    })

    it("applies the size prop as the only named max width", () => {
        const dialog = renderDialog({ size: "2xl" })

        expect(dialog).toHaveAttribute("data-size", "2xl")
        expect(dialog).toHaveClass("max-w-2xl")
        expect(dialog).not.toHaveClass("max-w-md")
    })

    it("lets an unprefixed className max width replace the default at every breakpoint", () => {
        const dialog = renderDialog({ className: "max-w-2xl max-h-[90vh]" })

        expect(dialog).toHaveClass("max-w-2xl", "max-h-[90vh]")
        expect(dialog).not.toHaveClass("max-w-md")
        expect(dialog.className).not.toMatch(/(^|\s)sm:max-w-md/)
    })

    it("keeps breakpoint-prefixed className widths working", () => {
        const dialog = renderDialog({ className: "sm:max-w-lg" })

        expect(dialog).toHaveClass("max-w-md", "sm:max-w-lg")
    })

    it("keeps a custom width class in place of the gutter width", () => {
        const dialog = renderDialog({ className: "w-[95vw]" })

        expect(dialog).toHaveClass("w-[95vw]")
        expect(dialog).not.toHaveClass("w-[calc(100%-2rem)]")
    })
})

describe("DialogFooter start slot", () => {
    it("renders start actions before Cancel/Save in their own group", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>Edit task</DialogTitle>
                    <DialogFooter start={<Button variant="destructive-ghost">Delete task</Button>}>
                        <Button variant="outline">Cancel</Button>
                        <Button>Save changes</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>,
        )

        const deleteButton = screen.getByRole("button", { name: "Delete task" })
        const startGroup = deleteButton.parentElement
        expect(startGroup).toHaveAttribute("data-slot", "dialog-footer-start")
        expect(startGroup).toHaveClass("sm:mr-auto")

        const footerButtons = Array.from(
            startGroup?.parentElement?.querySelectorAll("button") ?? [],
        ).map((button) => button.textContent)
        expect(footerButtons).toEqual(["Delete task", "Cancel", "Save changes"])
    })

    it("renders no start group when start is not set", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>Edit task</DialogTitle>
                    <DialogFooter>
                        <Button>Save changes</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>,
        )

        expect(document.querySelector('[data-slot="dialog-footer-start"]')).toBeNull()
    })
})

// Call sites that still set an unprefixed named max width in className. It renders correctly now,
// but new code uses the size prop. Remove a file's entry when its dialogs move to `size`.
const UNPREFIXED_MAX_WIDTH_ALLOWLIST: Readonly<Record<string, number>> = {
    "app/(app)/automation/campaigns/[id]/page.client.tsx": 1,
    "app/(app)/automation/campaigns/page.tsx": 1,
    "app/(app)/automation/email-templates/page.tsx": 2,
    "app/(app)/automation/page.client.tsx": 3,
    "app/(app)/donors/[id]/page.tsx": 1,
    "app/(app)/donors/page.client.tsx": 1,
    "app/(app)/intended-parents/[id]/components/IntendedParentDetailSections.tsx": 1,
    "app/(app)/intended-parents/page.client.tsx": 1,
    "app/(app)/matches/page.tsx": 1,
    "app/(app)/settings/integrations/page.tsx": 3,
    "app/(app)/settings/queues/page.tsx": 1,
    "app/(app)/settings/security/page.tsx": 1,
    "app/(app)/surrogates/page.client.tsx": 1,
    "app/auth/duo/callback/page.client.tsx": 1,
    "app/ops/templates/system/[systemKey]/page.client.tsx": 1,
    "components/ai/ScheduleParserDialog.tsx": 1,
    "components/appointments/UnifiedCalendar.tsx": 1,
    "components/email/EmailComposeDialog.tsx": 1,
    "components/forms/builder/TemplateFormPublishDialog.tsx": 1,
    "components/matches/ProposeMatchDialog.tsx": 1,
    "components/matches/ProposeMatchFromIPDialog.tsx": 1,
    "components/ops/templates/PublishDialog.tsx": 1,
    "components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx": 1,
    "components/surrogates/interviews/InterviewTab/EditorDialog.tsx": 1,
    "components/surrogates/interviews/InterviewVersionHistory.tsx": 2,
    "components/surrogates/journey/MilestoneImageSelector.tsx": 1,
}

describe("DialogContent width policy", () => {
    it("uses the size prop instead of an unprefixed named max-w class", () => {
        const offenders = scanJsxElements(["DialogContent"]).filter(({ attributes }) => {
            const className = attributes.className
            if (typeof className !== "string") return false
            return classTokens(className).some((token) =>
                /^max-w-(xs|sm|md|lg|xl|[2-7]xl)$/.test(token),
            )
        })

        expect(
            exceedAllowlist(countByFile(offenders), UNPREFIXED_MAX_WIDTH_ALLOWLIST),
            offenders.map(({ file, line }) => `${file}:${line}`).join("\n"),
        ).toEqual([])
    }, SOURCE_SCAN_TIMEOUT_MS)
})
