import type { ButtonHTMLAttributes, ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { InterviewVersionHistory } from "../components/surrogates/interviews/InterviewVersionHistory"

const mockUseInterviewVersions = vi.fn()

vi.mock("@/components/ui/dropdown-menu", () => ({
    DropdownMenu: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        ...props
    }: { children?: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
    DropdownMenuContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({ children }: { children?: ReactNode }) => <button type="button">{children}</button>,
}))

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) => (open ? <div>{children}</div> : null),
    DialogContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/lib/hooks/use-interviews", () => ({
    useInterviewVersions: (interviewId: string) => mockUseInterviewVersions(interviewId),
    useInterviewVersionDiff: () => ({ data: null, isLoading: false }),
    useRestoreInterviewVersion: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("InterviewVersionHistory", () => {
    it("adds descriptive aria-labels to version action triggers", () => {
        mockUseInterviewVersions.mockReturnValue({
            data: [
                {
                    version: 3,
                    source: "manual",
                    author_name: "Case Manager",
                    created_at: "2026-02-10T12:00:00Z",
                    content_size_bytes: 512,
                },
            ],
            isLoading: false,
        })

        render(
            <InterviewVersionHistory
                interviewId="int-1"
                currentVersion={3}
                open
                onOpenChange={() => undefined}
                canRestore={false}
            />,
        )

        expect(
            screen.getByRole("button", { name: "Version history actions for version 3" }),
        ).toBeInTheDocument()
    })
})
