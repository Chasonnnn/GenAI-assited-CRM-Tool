import { describe, expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

type PackageJson = {
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
})
