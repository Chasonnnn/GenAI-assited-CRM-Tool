import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AddTaskDialog } from "@/components/matches/AddTaskDialog"
import { UploadFileDialog } from "@/components/matches/UploadFileDialog"

describe("match dialog loading states", () => {
    it("shows a spinner while a match task is being created", () => {
        render(
            <AddTaskDialog
                open
                onOpenChange={vi.fn()}
                onSubmit={vi.fn().mockResolvedValue(undefined)}
                isPending
                surrogateName="Case A"
                ipName="IP A"
            />
        )

        const submitButton = screen.getByRole("button", { name: "Creating..." })

        expect(submitButton).toBeDisabled()
        expect(submitButton.querySelector("svg")).toHaveClass("animate-spin")
    })

    it("shows a spinner while a match file is being uploaded", () => {
        render(
            <UploadFileDialog
                open
                onOpenChange={vi.fn()}
                onUpload={vi.fn().mockResolvedValue(undefined)}
                isPending
                surrogateName="Case A"
                ipName="IP A"
            />
        )

        const submitButton = screen.getByRole("button", { name: "Uploading..." })

        expect(submitButton).toBeDisabled()
        expect(submitButton.querySelector("svg")).toHaveClass("animate-spin")
    })
})
