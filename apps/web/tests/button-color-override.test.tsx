import { readFileSync } from "node:fs"
import { join } from "node:path"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogContent,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"

import {
    classTokens,
    countByFile,
    exceedAllowlist,
    scanJsxElements,
    scanObjectCalls,
    SOURCE_SCAN_TIMEOUT_MS,
    utilityOf,
} from "./fixtures/jsx-class-scan"

const PRIMARY_GRADIENT = /bg-\[linear-gradient/

describe("Button semantic variants", () => {
    it("renders success as a solid token color without the primary gradient", () => {
        render(<Button variant="success">Accept match</Button>)

        const button = screen.getByRole("button", { name: "Accept match" })
        expect(button).toHaveClass("bg-success", "text-success-foreground", "dark:bg-success/60")
        expect(button.className).not.toMatch(PRIMARY_GRADIENT)
    })

    it("renders destructive-outline with destructive text and border", () => {
        render(<Button variant="destructive-outline">Reject</Button>)

        const button = screen.getByRole("button", { name: "Reject" })
        expect(button).toHaveClass("border", "border-destructive/40", "text-destructive", "bg-background")
        expect(button.className).not.toMatch(PRIMARY_GRADIENT)
    })

    it("renders destructive-ghost as text-only until hover", () => {
        render(<Button variant="destructive-ghost">Delete task</Button>)

        const button = screen.getByRole("button", { name: "Delete task" })
        expect(button).toHaveClass("text-destructive", "hover:bg-destructive/10")
        expect(button.className).not.toMatch(/(^|\s)bg-/)
    })

    it("lets a muted class rest a destructive-ghost icon button until hover", () => {
        render(
            <Button variant="destructive-ghost" size="icon-sm" className="text-muted-foreground" aria-label="Delete note" />,
        )

        const button = screen.getByRole("button", { name: "Delete note" })
        expect(button).toHaveClass("text-muted-foreground", "hover:text-destructive")
        expect(button).not.toHaveClass("text-destructive")
    })

    it("renders a destructive AlertDialogAction without the primary gradient", () => {
        render(
            <AlertDialog open>
                <AlertDialogContent>
                    <AlertDialogTitle>Delete task?</AlertDialogTitle>
                    <AlertDialogAction variant="destructive">Delete</AlertDialogAction>
                </AlertDialogContent>
            </AlertDialog>,
        )

        const action = screen.getByRole("button", { name: "Delete" })
        expect(action).toHaveClass("bg-destructive")
        expect(action.className).not.toMatch(PRIMARY_GRADIENT)
    })

    it("lets a background color class on a default Button replace the gradient", () => {
        render(
            <AlertDialog open>
                <AlertDialogContent>
                    <AlertDialogTitle>Delete now?</AlertDialogTitle>
                    <AlertDialogAction className="bg-destructive hover:bg-destructive/90">Delete now</AlertDialogAction>
                </AlertDialogContent>
            </AlertDialog>,
        )

        const action = screen.getByRole("button", { name: "Delete now" })
        expect(action).toHaveClass("bg-destructive", "hover:bg-destructive/90")
        expect(action.className).not.toMatch(PRIMARY_GRADIENT)
    })

    it("removes the gradient for buttonVariants className colors and keeps it for hover-only colors", () => {
        const banner = buttonVariants({ className: "bg-white text-teal-600 hover:bg-teal-50" })
        expect(banner).not.toMatch(PRIMARY_GRADIENT)
        expect(banner).toContain("bg-white")
        expect(banner).toContain("text-teal-600")
        expect(banner).not.toContain("text-primary-foreground")

        const hoverOnly = buttonVariants({ className: "hover:bg-primary/90" })
        expect(hoverOnly).toMatch(PRIMARY_GRADIENT)
        expect(hoverOnly).toContain("hover:bg-primary/90")
    })

    it("defines the foreground tokens that colored call-site buttons use", () => {
        // Allowlisted buttons set "bg-destructive text-destructive-foreground". Without the token the
        // text inherits the dark foreground on a red fill once the gradient is removed.
        const globals = readFileSync(join(process.cwd(), "app/globals.css"), "utf8")
        const blockOf = (selector: string) => globals.match(new RegExp(`^${selector} \\{[\\s\\S]*?^\\}`, "m"))?.[0] ?? ""

        expect(blockOf("@theme inline")).toContain("--color-destructive-foreground: var(--destructive-foreground);")
        expect(blockOf(":root")).toMatch(/--destructive-foreground: oklch\(/)
        expect(blockOf("\\.dark")).toMatch(/--destructive-foreground: oklch\(/)
    })

    it("keeps the gradient on the default variant only", () => {
        expect(buttonVariants()).toMatch(PRIMARY_GRADIENT)
        for (const variant of ["destructive", "destructive-outline", "destructive-ghost", "success", "outline", "secondary", "ghost", "link"] as const) {
            expect(buttonVariants({ variant })).not.toMatch(PRIMARY_GRADIENT)
        }
    })
})

// A bg-* class on the default variant now replaces the gradient (see button-variants.ts), but it
// hardcodes a color outside the variant set. Pick a variant instead (destructive, success, outline, ...).
const NON_COLOR_BG_UTILITY =
    /^bg-(\[(linear|radial|conic|url)|linear|radial|conic|gradient|clip|origin|blend|repeat|no-repeat$|none$|fixed$|local$|scroll$|cover$|contain$|auto$|center$|top|bottom|left|right)/

function backgroundColorClasses(text: string): string[] {
    return classTokens(text).filter((token) => {
        const utility = utilityOf(token)
        return utility.startsWith("bg-") && !NON_COLOR_BG_UTILITY.test(utility)
    })
}

function isDefaultVariant(variant: string | true | undefined): boolean {
    return variant === undefined || variant === "default"
}

// Existing call sites, per file. Remove a file's entry when its buttons use a variant; the count
// may only go down.
const DEFAULT_VARIANT_BG_ALLOWLIST: Readonly<Record<string, number>> = {
    "app/invite/[id]/page.client.tsx": 1,
    "app/login/LoginPageClient.tsx": 1,
}

describe("default-variant background policy", () => {
    it("does not set bg-* classes on default-variant Button, AlertDialogAction or buttonVariants", () => {
        const jsxOffenders = scanJsxElements(["Button", "AlertDialogAction"]).filter(
            ({ attributes }) =>
                attributes.unstyled === undefined &&
                isDefaultVariant(attributes.variant) &&
                typeof attributes.className === "string" &&
                backgroundColorClasses(attributes.className).length > 0,
        )
        const callOffenders = scanObjectCalls("buttonVariants").filter(
            ({ properties }) =>
                isDefaultVariant(properties.variant) &&
                typeof properties.className === "string" &&
                backgroundColorClasses(properties.className).length > 0,
        )
        const offenders = [...jsxOffenders, ...callOffenders]

        expect(
            exceedAllowlist(countByFile(offenders), DEFAULT_VARIANT_BG_ALLOWLIST),
            offenders.map(({ file, line }) => `${file}:${line}`).sort().join("\n"),
        ).toEqual([])
    }, SOURCE_SCAN_TIMEOUT_MS)
})
