import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { UploadFileDialog } from "@/components/matches/UploadFileDialog"

describe("UploadFileDialog", () => {
    it("adds an accessible label to the clear selected file button", () => {
        const file = new File(["name,formula\nAlice,=2+2\n"], "danger.csv", {
            type: "text/csv",
        })

        render(
            <UploadFileDialog
                open
                onOpenChange={vi.fn()}
                onUpload={vi.fn().mockResolvedValue(undefined)}
                isPending={false}
                surrogateName="Case A"
                ipName="IP A"
            />
        )

        const input = screen.getByLabelText("File") as HTMLInputElement
        fireEvent.change(input, { target: { files: [file] } })

        expect(
            screen.getByRole("button", { name: "Remove selected file danger.csv" })
        ).toBeInTheDocument()
    })
})
