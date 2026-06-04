import { describe, expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

type PackageJson = {
    dependencies?: Record<string, string>
    devDependencies?: Record<string, string>
    pnpm?: {
        overrides?: Record<string, string>
    }
}

function compareVersions(left: string, right: string): number {
    const leftParts = left.split(".").map((part) => Number.parseInt(part, 10))
    const rightParts = right.split(".").map((part) => Number.parseInt(part, 10))
    const length = Math.max(leftParts.length, rightParts.length)

    for (let index = 0; index < length; index += 1) {
        const leftPart = leftParts[index] ?? 0
        const rightPart = rightParts[index] ?? 0

        if (leftPart !== rightPart) {
            return leftPart - rightPart
        }
    }

    return 0
}

describe("Dependency security guards", () => {
    it("pins flatted to a non-vulnerable version in pnpm overrides", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const flattedOverride = packageJson.pnpm?.overrides?.flatted

        expect(flattedOverride).toBeDefined()
        expect(compareVersions(flattedOverride!, "3.4.0")).toBeGreaterThanOrEqual(0)
    })

    it("pins brace-expansion to a non-vulnerable version in pnpm overrides", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const braceExpansionOverride = packageJson.pnpm?.overrides?.["brace-expansion"]

        expect(braceExpansionOverride).toBeDefined()
        expect(compareVersions(braceExpansionOverride!, "5.0.6")).toBeGreaterThanOrEqual(0)
    })

    it("pins DOMPurify to a non-vulnerable version", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const dompurifyVersion = packageJson.dependencies?.dompurify?.replace(/^[^\d]*/, "")

        expect(dompurifyVersion).toBeDefined()
        expect(compareVersions(dompurifyVersion!, "3.4.6")).toBeGreaterThanOrEqual(0)
    })

    it("pins PostCSS to a non-vulnerable version in pnpm overrides", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const postcssOverride = packageJson.pnpm?.overrides?.postcss

        expect(postcssOverride).toBeDefined()
        expect(compareVersions(postcssOverride!, "8.5.10")).toBeGreaterThanOrEqual(0)
    })

    it("pins ws to a non-vulnerable version in pnpm overrides", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const wsOverride = packageJson.pnpm?.overrides?.ws

        expect(wsOverride).toBeDefined()
        expect(compareVersions(wsOverride!, "8.20.1")).toBeGreaterThanOrEqual(0)
    })

    it("pins picomatch to a non-vulnerable version in pnpm overrides", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const picomatchOverride = packageJson.pnpm?.overrides?.picomatch

        expect(picomatchOverride).toBeDefined()
        expect(compareVersions(picomatchOverride!, "4.0.4")).toBeGreaterThanOrEqual(0)
    })

    it("pins vite to a non-vulnerable version in pnpm overrides", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const viteOverride = packageJson.pnpm?.overrides?.vite

        expect(viteOverride).toBeDefined()
        expect(compareVersions(viteOverride!, "7.3.2")).toBeGreaterThanOrEqual(0)
    })

    it("pins Vitest to a non-vulnerable version", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as PackageJson

        const vitestVersion = packageJson.devDependencies?.vitest?.replace(/^[^\d]*/, "")

        expect(vitestVersion).toBeDefined()
        expect(compareVersions(vitestVersion!, "4.1.0")).toBeGreaterThanOrEqual(0)
    })

    it("resolves only non-vulnerable flatted versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}flatted@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "3.4.0")).toBeGreaterThanOrEqual(0)
        }
    })

    it("resolves only non-vulnerable brace-expansion versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}brace-expansion@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "5.0.6")).toBeGreaterThanOrEqual(0)
        }
    })

    it("resolves only non-vulnerable PostCSS versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}postcss@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "8.5.10")).toBeGreaterThanOrEqual(0)
        }
    })

    it("resolves only non-vulnerable ws versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}ws@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "8.20.1")).toBeGreaterThanOrEqual(0)
        }
    })

    it("resolves only non-vulnerable picomatch versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}picomatch@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "4.0.4")).toBeGreaterThanOrEqual(0)
        }
    })

    it("resolves only non-vulnerable vite versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}vite@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "7.3.2")).toBeGreaterThanOrEqual(0)
        }
    })

    it("resolves only non-vulnerable Vitest versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\s{2}vitest@(\d+\.\d+\.\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "4.1.0")).toBeGreaterThanOrEqual(0)
        }
    })
})
