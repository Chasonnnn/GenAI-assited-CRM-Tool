import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

const mockNotFound = vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND")
})

vi.mock("next/navigation", async () => {
    const actual = await vi.importActual("next/navigation")
    return {
        ...actual,
        notFound: () => mockNotFound(),
    }
})

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

import RecordNotFoundPage from "@/app/(app)/record-not-found/[kind]/page"

async function renderKind(kind: string) {
    render(await RecordNotFoundPage({ params: Promise.resolve({ kind }) }))
}

describe("RecordNotFoundPage", () => {
    it.each([
        ["campaign", "Campaign not found", "Back to Campaigns", "/automation/campaigns"],
        ["form", "Form not found", "Back to Forms", "/automation/forms"],
        ["match", "Match not found", "Back to Matches", "/intended-parents/matches"],
        ["member", "Member not found", "Back to Team", "/settings/team"],
        ["role", "Role not found", "Back to Role Permissions", "/settings/team/roles"],
    ])("renders the %s state with its back link", async (kind, title, backLabel, backHref) => {
        await renderKind(kind)

        expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: backLabel })).toHaveAttribute("href", backHref)
    })

    it.each(["unknown", "toString", "__proto__"])("falls back to the app not-found for %s", async (kind) => {
        await expect(RecordNotFoundPage({ params: Promise.resolve({ kind }) })).rejects.toThrow(
            "NEXT_NOT_FOUND",
        )
    })
})
