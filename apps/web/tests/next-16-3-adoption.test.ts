import { existsSync, readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { join } from "node:path"

import { afterEach, describe, expect, it } from "vitest"

const require = createRequire(import.meta.url)
const originalInstantNavigationFlag = process.env.NEXT_ENABLE_INSTANT_NAVIGATIONS
const originalOfflineFlag = process.env.NEXT_EXPERIMENTAL_OFFLINE_RETRY
const originalRustCompilerFlag = process.env.NEXT_EXPERIMENTAL_RUST_REACT_COMPILER

afterEach(() => {
    if (originalInstantNavigationFlag === undefined) {
        delete process.env.NEXT_ENABLE_INSTANT_NAVIGATIONS
    } else {
        process.env.NEXT_ENABLE_INSTANT_NAVIGATIONS = originalInstantNavigationFlag
    }
    if (originalOfflineFlag === undefined) {
        delete process.env.NEXT_EXPERIMENTAL_OFFLINE_RETRY
    } else {
        process.env.NEXT_EXPERIMENTAL_OFFLINE_RETRY = originalOfflineFlag
    }
    if (originalRustCompilerFlag === undefined) {
        delete process.env.NEXT_EXPERIMENTAL_RUST_REACT_COMPILER
    } else {
        process.env.NEXT_EXPERIMENTAL_RUST_REACT_COMPILER = originalRustCompilerFlag
    }
    delete require.cache[require.resolve("../next.config.js")]
})

describe("Next.js 16.3 adoption contracts", () => {
    it("uses the native TypeScript 7 CLI beside the TypeScript 6 compatibility API", () => {
        const packageJson = JSON.parse(
            readFileSync(join(process.cwd(), "package.json"), "utf8"),
        ) as {
            scripts: Record<string, string>
            devDependencies: Record<string, string>
        }

        expect(packageJson.devDependencies["@typescript/native"]).toBe(
            "npm:typescript@7.0.2",
        )
        expect(packageJson.devDependencies.typescript).toBe(
            "npm:@typescript/typescript6@6.0.2",
        )
        expect(packageJson.scripts.typecheck).toBe("tsc --noEmit")
        expect(packageJson.scripts["typecheck:compat"]).toBe("tsc6 --noEmit")
        expect(packageJson.scripts.build).toBe("next build --webpack")
    })

    it("routes frontend agents to the version-matched bundled Next.js documentation", () => {
        const agentsPath = join(process.cwd(), "AGENTS.md")
        const claudePath = join(process.cwd(), "CLAUDE.md")

        expect(existsSync(agentsPath)).toBe(true)
        expect(existsSync(claudePath)).toBe(true)

        const agents = readFileSync(agentsPath, "utf8")
        const claude = readFileSync(claudePath, "utf8")

        expect(agents).toContain("../../AGENTS.md")
        expect(agents).toContain("<!-- BEGIN:nextjs-agent-rules -->")
        expect(agents).toContain("node_modules/next/dist/docs/")
        expect(agents).toContain("<!-- END:nextjs-agent-rules -->")
        expect(claude.trim()).toBe("@AGENTS.md")
    })

    it("keeps experimental profiles off by default and enables each one explicitly", () => {
        delete process.env.NEXT_ENABLE_INSTANT_NAVIGATIONS
        delete process.env.NEXT_EXPERIMENTAL_OFFLINE_RETRY
        delete process.env.NEXT_EXPERIMENTAL_RUST_REACT_COMPILER
        delete require.cache[require.resolve("../next.config.js")]
        const productionConfig = require("../next.config.js")

        expect(productionConfig.cacheComponents).toBe(false)
        expect(productionConfig.partialPrefetching).toBe(false)
        expect(productionConfig.experimental.useOffline).toBe(false)
        expect(productionConfig.experimental.turbopackRustReactCompiler).toBe(false)
        expect(productionConfig.experimental.useTypeScriptCli).toBe(false)

        process.env.NEXT_ENABLE_INSTANT_NAVIGATIONS = "true"
        process.env.NEXT_EXPERIMENTAL_OFFLINE_RETRY = "true"
        process.env.NEXT_EXPERIMENTAL_RUST_REACT_COMPILER = "true"
        delete require.cache[require.resolve("../next.config.js")]
        const adoptionConfig = require("../next.config.js")

        expect(adoptionConfig.cacheComponents).toBe(true)
        expect(adoptionConfig.partialPrefetching).toBe(true)
        expect(adoptionConfig.experimental.useOffline).toBe(true)
        expect(adoptionConfig.experimental.turbopackRustReactCompiler).toBe(true)
    })

    it("records the tenant-safety migration boundary before the feature can be promoted", () => {
        const adoptionGuide = readFileSync(join(process.cwd(), "docs/next-16-3-adoption.md"), "utf8")

        expect(adoptionGuide).toContain("17 production-prerender blockers")
        expect(adoptionGuide).toContain("NEXT_ENABLE_INSTANT_NAVIGATIONS=true")
        expect(adoptionGuide).toContain("Do not enable in production")
        expect(adoptionGuide).toContain("organization_id")
    })

    it("documents the TypeScript 7 split-toolchain boundary", () => {
        const adoptionGuide = readFileSync(join(process.cwd(), "docs/next-16-3-adoption.md"), "utf8")

        expect(adoptionGuide).toContain("## TypeScript 7 split toolchain")
        expect(adoptionGuide).toContain('"@typescript/native": "npm:typescript@7.0.2"')
        expect(adoptionGuide).toContain('"typescript": "npm:@typescript/typescript6@6.0.2"')
        expect(adoptionGuide).toContain("pnpm run typecheck:compat")
        expect(adoptionGuide).toContain("experimental.useTypeScriptCli: false")
        expect(adoptionGuide).not.toContain("## TypeScript 7 hold")
    })

    it("documents the production bundler boundary", () => {
        const adoptionGuide = readFileSync(join(process.cwd(), "docs/next-16-3-adoption.md"), "utf8")

        expect(adoptionGuide).toContain("## Production bundler boundary")
        expect(adoptionGuide).toContain("next build --webpack")
        expect(adoptionGuide).toContain("React Compiler")
        expect(adoptionGuide).toContain("Turbopack")
    })

    it("keeps Next's generated route validator in the standalone type-check", () => {
        const tsconfig = JSON.parse(
            readFileSync(join(process.cwd(), "tsconfig.json"), "utf8"),
        ) as { include?: string[]; exclude?: string[] }

        expect(tsconfig.include).toContain(".next/types/**/*.ts")
        expect(tsconfig.exclude).not.toContain(".next/types/validator.ts")
    })

    it("persists Next's incremental build cache in the frontend CI job", () => {
        const workflow = readFileSync(join(process.cwd(), "../../.github/workflows/ci.yml"), "utf8")

        expect(workflow).toContain("uses: actions/cache@v5")
        expect(workflow).toContain("${{ github.workspace }}/apps/web/.next/cache")
        expect(workflow).toContain("hashFiles('apps/web/pnpm-lock.yaml')")
        expect(workflow).toContain("hashFiles('apps/web/**/*.js', 'apps/web/**/*.jsx', 'apps/web/**/*.ts', 'apps/web/**/*.tsx')")
    })
})
