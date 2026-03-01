import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { FieldRow } from "@/components/surrogates/profile/ProfileCard/FieldRow"
import type { FormSchema } from "@/lib/api/forms"

const modeState = {
    mode: { type: "edit", editingField: null as string | null },
    setEditingField: vi.fn(),
}

const editsState = {
    editedFields: {} as Record<string, unknown>,
    setFieldValue: vi.fn(),
    cancelFieldEdit: vi.fn(),
    hiddenFields: [] as string[],
    toggleHidden: vi.fn(),
    revealedFields: new Set<string>(),
    toggleReveal: vi.fn(),
    stagedChanges: [] as Array<{ field_key: string }>,
}

vi.mock("@/components/surrogates/profile/ProfileCard/context", () => ({
    useProfileCardMode: () => modeState,
    useProfileCardEdits: () => editsState,
}))

describe("ProfileCard FieldRow accessibility", () => {
    const textField: FormSchema["pages"][number]["fields"][number] = {
        key: "email",
        label: "Email",
        type: "text",
    }

    beforeEach(() => {
        modeState.mode = { type: "edit", editingField: null }
        modeState.setEditingField.mockReset()
        editsState.editedFields = {}
        editsState.setFieldValue.mockReset()
        editsState.cancelFieldEdit.mockReset()
        editsState.hiddenFields = []
        editsState.toggleHidden.mockReset()
        editsState.revealedFields = new Set()
        editsState.toggleReveal.mockReset()
        editsState.stagedChanges = []
    })

    it("adds an aria-label to the edit icon button", () => {
        render(
            <FieldRow
                fieldKey="email"
                field={textField}
                mergedValue="test@example.com"
                baseValue="test@example.com"
            />,
        )

        expect(screen.getByRole("button", { name: "Edit Email" })).toBeInTheDocument()
    })

    it("adds an aria-label to the cancel icon button", () => {
        modeState.mode = { type: "edit", editingField: "email" }
        editsState.editedFields = { email: "edited@example.com" }

        render(
            <FieldRow
                fieldKey="email"
                field={textField}
                mergedValue="test@example.com"
                baseValue="test@example.com"
            />,
        )

        expect(screen.getByRole("button", { name: "Cancel editing Email" })).toBeInTheDocument()
    })
})
