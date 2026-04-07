import * as React from "react"
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { BulkChangeStageModal } from "@/components/surrogates/BulkChangeStageModal"

vi.mock("@/components/ui/select", () => {
    const SelectContext = React.createContext<{
        value: string
        onValueChange: (value: string) => void
    }>({
        value: "",
        onValueChange: () => undefined,
    })

    function Select({
        value,
        onValueChange,
        children,
    }: {
        value: string
        onValueChange: (value: string) => void
        children: React.ReactNode
    }) {
        return (
            <SelectContext.Provider value={{ value, onValueChange }}>
                <div>{children}</div>
            </SelectContext.Provider>
        )
    }

    function SelectTrigger({
        id,
        children,
        ...props
    }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
        return (
            <button id={id} type="button" role="combobox" {...props}>
                {children}
            </button>
        )
    }

    function SelectValue({
        placeholder,
        children,
    }: {
        placeholder?: string
        children?: ((value: string | null) => React.ReactNode) | React.ReactNode
    }) {
        const { value } = React.useContext(SelectContext)
        if (!value) return <span>{placeholder}</span>
        if (typeof children === "function") {
            return <span>{children(value)}</span>
        }
        return <span>{value}</span>
    }

    function SelectContent({ children }: { children: React.ReactNode }) {
        return <div role="listbox">{children}</div>
    }

    function SelectItem({
        value,
        children,
    }: {
        value: string
        children: React.ReactNode
    }) {
        const { onValueChange } = React.useContext(SelectContext)
        return (
            <button type="button" role="option" onClick={() => onValueChange(value)}>
                {children}
            </button>
        )
    }

    return {
        Select,
        SelectTrigger,
        SelectValue,
        SelectContent,
        SelectItem,
    }
})

const stages = [
    { id: "s1", slug: "new_unread", stage_key: "new_unread", label: "New Unread", color: "#3b82f6", order: 1, stage_type: "intake", is_active: true },
    { id: "s2", slug: "contacted", stage_key: "contacted", label: "Contacted", color: "#0ea5e9", order: 2, stage_type: "intake", is_active: true },
    { id: "s3", slug: "on_hold", stage_key: "on_hold", label: "On Hold", color: "#f59e0b", order: 3, stage_type: "paused", is_active: true },
    { id: "s4", slug: "delivered", stage_key: "delivered", label: "Delivered", color: "#22c55e", order: 4, stage_type: "post_approval", is_active: true },
] as const

describe("BulkChangeStageModal", () => {
    it("filters out on-hold and delivery stages from the target stage picker", () => {
        render(
            <BulkChangeStageModal
                open
                onOpenChange={vi.fn()}
                selectedCount={2}
                stages={[...stages]}
                isPending={false}
                onSubmit={vi.fn()}
            />,
        )

        fireEvent.click(screen.getByRole("combobox", { name: "Target stage" }))

        expect(screen.getByRole("option", { name: "New Unread" })).toBeInTheDocument()
        expect(screen.getByRole("option", { name: "Contacted" })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "On Hold" })).not.toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Delivered" })).not.toBeInTheDocument()
    })

    it("submits the selected immediate stage", async () => {
        const onSubmit = vi.fn().mockResolvedValue(undefined)

        render(
            <BulkChangeStageModal
                open
                onOpenChange={vi.fn()}
                selectedCount={2}
                stages={[...stages]}
                isPending={false}
                onSubmit={onSubmit}
            />,
        )

        const trigger = screen.getByRole("combobox", { name: "Target stage" })
        fireEvent.click(trigger)
        fireEvent.click(screen.getByRole("option", { name: "Contacted" }))
        fireEvent.click(screen.getByRole("button", { name: "Change stage" }))

        await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("s2"))
    })
})
