import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
    usePermissionCheck: vi.fn(),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => mocks.usePermissionCheck(),
}))

import { SettingsPageGate } from "../app/(app)/settings/settings-page-gate"

function permissionCheck(overrides: Partial<{ isLoading: boolean; isError: boolean; granted: string[] }> = {}) {
    const granted = overrides.granted ?? []
    return {
        isLoading: overrides.isLoading ?? false,
        isError: overrides.isError ?? false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => granted.includes(permission),
    }
}

function renderGate() {
    return render(
        <SettingsPageGate
            title="Compliance"
            permission="manage_compliance"
            deniedDescription="Compliance needs the Manage compliance permission. Ask an admin to update your role."
        >
            <p>Compliance content</p>
        </SettingsPageGate>
    )
}

describe("SettingsPageGate", () => {
    beforeEach(() => {
        mocks.usePermissionCheck.mockReset()
    })

    it("renders the page content when the viewer holds the permission", () => {
        mocks.usePermissionCheck.mockReturnValue(permissionCheck({ granted: ["manage_compliance"] }))

        renderGate()

        expect(screen.getByText("Compliance content")).toBeInTheDocument()
        expect(screen.queryByText("Permission required")).not.toBeInTheDocument()
    })

    it("keeps the header and shows the denied state without mounting the content", () => {
        mocks.usePermissionCheck.mockReturnValue(permissionCheck({ granted: ["view_roles"] }))

        renderGate()

        expect(screen.getByRole("heading", { level: 1, name: "Compliance" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 2, name: "Permission required" })).toBeInTheDocument()
        expect(screen.getByText(/Manage compliance permission/)).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Settings" })).toHaveAttribute("href", "/settings")
        expect(screen.queryByText("Compliance content")).not.toBeInTheDocument()
    })

    it("shows a loader, not the denied state, while permissions load", () => {
        mocks.usePermissionCheck.mockReturnValue(permissionCheck({ isLoading: true }))

        renderGate()

        expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument()
        expect(screen.queryByText("Permission required")).not.toBeInTheDocument()
        expect(screen.queryByText("Compliance content")).not.toBeInTheDocument()
    })

    it("offers a retry when the permission lookup fails", () => {
        const check = permissionCheck({ isError: true })
        mocks.usePermissionCheck.mockReturnValue(check)

        renderGate()

        expect(screen.getByRole("heading", { level: 2, name: "Couldn't check your access" })).toBeInTheDocument()
        expect(screen.queryByText("Permission required")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(check.retry).toHaveBeenCalledTimes(1)
    })
})
