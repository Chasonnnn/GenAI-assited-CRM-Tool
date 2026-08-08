import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

import AppError from "@/app/(app)/error"
import RootError from "@/app/error"
import OpsError from "@/app/ops/error"

describe("Next.js error boundaries", () => {
    it.each([
        ["root", RootError],
        ["authenticated app", AppError],
        ["ops", OpsError],
    ])("uses the stable retry contract for the %s boundary", (_name, Boundary) => {
        const retry = vi.fn()

        render(<Boundary error={new Error("temporary failure")} retry={retry} />)
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))

        expect(retry).toHaveBeenCalledOnce()
    })
})
