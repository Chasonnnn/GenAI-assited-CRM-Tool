import type { ReactNode } from "react"
import { render } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ThemeProvider } from "@/components/theme-provider"

const state = vi.hoisted(() => ({ pathname: "/dashboard", props: [] as Array<Record<string, unknown>> }))

vi.mock("next/navigation", () => ({ usePathname: () => state.pathname }))
vi.mock("next-themes", () => ({
    ThemeProvider: ({ children, ...props }: { children: ReactNode } & Record<string, unknown>) => {
        state.props.push(props)
        return <>{children}</>
    },
}))

describe("ThemeProvider", () => {
    beforeEach(() => {
        state.props = []
    })

    it.each(["/intake/qa-expo", "/embed/forms/qa-expo"])("forces the light theme on the public form %s", (pathname) => {
        state.pathname = pathname
        render(<ThemeProvider attribute="class" enableSystem>content</ThemeProvider>)
        expect(state.props.at(-1)).toMatchObject({ forcedTheme: "light", attribute: "class", enableSystem: true })
    })

    it("leaves the chosen theme alone on app pages", () => {
        state.pathname = "/intended-parents"
        render(<ThemeProvider attribute="class" enableSystem>content</ThemeProvider>)
        expect(state.props.at(-1)?.forcedTheme).toBeUndefined()
    })
})
