import { useState } from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { DonorChecklistAnswer, DonorEligibilityChecklist } from "@/components/donors/DonorEligibilityChecklist"
import { RecordEditingContext } from "@/components/records/RecordEditingContext"
import type { DonorChecklistItem } from "@/lib/types/donor-profile"
import { donorProfileFixture } from "./fixtures/donor-profile"

function AnswerHarness({ item, save }: { item: DonorChecklistItem; save: (value: string | null) => Promise<void> }) {
    const [value, setValue] = useState(item.value)
    return <DonorChecklistAnswer item={{ ...item, value }} onSave={async next => { await save(next); setValue(next) }} />
}

const nicotine = donorProfileFixture.eligibility_checklist.find(item => item.key === "nicotine")!
const infectious = donorProfileFixture.eligibility_checklist.find(item => item.key === "infectious_disease")!

describe("Donor eligibility answers", () => {
    it("cycles Not answered, Yes and No with one click and no dropdown", async () => {
        const save = vi.fn().mockResolvedValue(undefined)
        render(<AnswerHarness item={nicotine} save={save} />)
        for (const next of ["Yes", "No", null]) {
            await act(async () => { fireEvent.click(screen.getByRole("button")) })
            expect(save).toHaveBeenLastCalledWith(next)
            expect(screen.getByRole("button")).toHaveTextContent(next ?? "Not answered")
            expect(screen.queryByRole("combobox")).not.toBeInTheDocument()
        }
    })

    it("preserves Prefer to discuss as a distinct answer before returning to unanswered", async () => {
        const save = vi.fn().mockResolvedValue(undefined)
        render(<AnswerHarness item={{ ...infectious, value: "No" }} save={save} />)
        await act(async () => { fireEvent.click(screen.getByRole("button")) })
        expect(save).toHaveBeenLastCalledWith("Prefer to discuss with the team")
        expect(screen.getByRole("button")).toHaveTextContent("Prefer to discuss with the team")
        await act(async () => { fireEvent.click(screen.getByRole("button")) })
        expect(save).toHaveBeenLastCalledWith(null)
        expect(screen.getByRole("button")).toHaveTextContent("Not answered")
    })

    it("prevents duplicate updates while pending and preserves the saved value on failure", async () => {
        let reject!: (reason: Error) => void
        const save = vi.fn(() => new Promise<void>((_, rejectPromise) => { reject = rejectPromise }))
        render(<AnswerHarness item={{ ...nicotine, value: "No" }} save={save} />)
        fireEvent.click(screen.getByRole("button"))
        fireEvent.click(screen.getByRole("button"))
        expect(save).toHaveBeenCalledTimes(1)
        expect(screen.getByRole("button")).toBeDisabled()
        expect(screen.getByRole("button")).toHaveTextContent("No")
        await act(async () => { reject(new Error("Network unavailable")) })
        expect(screen.getByRole("alert")).toHaveTextContent("Unable to save answer")
        expect(screen.getByRole("button")).toBeEnabled()
        expect(screen.getByRole("button")).toHaveTextContent("No")
    })

    it("uses a native button and enforces read-only permissions", async () => {
        const save = vi.fn().mockResolvedValue(undefined)
        const editable = render(<AnswerHarness item={nicotine} save={save} />)
        expect(screen.getByRole("button").tagName).toBe("BUTTON")
        fireEvent.click(screen.getByRole("button"))
        await waitFor(() => expect(save).toHaveBeenCalledWith("Yes"))
        editable.unmount()
        save.mockClear()
        render(<RecordEditingContext value={false}><AnswerHarness item={nicotine} save={save} /></RecordEditingContext>)
        fireEvent.click(screen.getByRole("button"))
        expect(screen.getByRole("button")).toBeDisabled()
        expect(save).not.toHaveBeenCalled()
    })

    it("shows the six form questions without inventing eligibility thresholds", () => {
        render(<DonorEligibilityChecklist items={donorProfileFixture.eligibility_checklist} onUpdate={vi.fn()} />)
        expect(screen.getByText("Education level:")).toBeInTheDocument()
        expect(screen.getByText("University / college:")).toBeInTheDocument()
        expect(screen.getByText("Infectious disease / STI history:")).toBeInTheDocument()
        expect(screen.queryByText(/Citizen|Age Eligible|Pass|Fail|Eligible \(/)).not.toBeInTheDocument()
    })
})
