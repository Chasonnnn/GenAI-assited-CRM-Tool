import { readFileSync } from "node:fs"
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
    it("keeps experimental profiles off by default and enables each one explicitly", () => {
        delete process.env.NEXT_ENABLE_INSTANT_NAVIGATIONS
        delete process.env.NEXT_EXPERIMENTAL_OFFLINE_RETRY
        delete process.env.NEXT_EXPERIMENTAL_RUST_REACT_COMPILER
        delete require.cache[require.resolve("../next.config.js")]
        const productionConfig = require("../next.config.js")

        expect(productionConfig.agentRules).toBe(false)
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

    it("keeps Next's generated route validator in the standalone type-check", () => {
        const tsconfig = JSON.parse(
            readFileSync(join(process.cwd(), "tsconfig.json"), "utf8"),
        ) as { include?: string[]; exclude?: string[] }

        expect(tsconfig.include).toContain(".next/types/**/*.ts")
        expect(tsconfig.exclude).not.toContain(".next/types/validator.ts")
    })

    it("persists Next's incremental build cache in the frontend CI job", () => {
        const workflow = readFileSync(join(process.cwd(), "../../.github/workflows/ci.yml"), "utf8")

        const key = "key: ${{ runner.os }}-nextjs-${{ hashFiles('apps/web/pnpm-lock.yaml') }}-${{ github.sha }}"
        const restore = workflow.split("uses: actions/cache/restore@v5", 2)[1]?.split("- name:", 1)[0] ?? ""
        const save = workflow.split("uses: actions/cache/save@v5", 2)[1]?.split("\n\n", 1)[0] ?? ""
        const saveStep = workflow.split("- name: Save Next.js incremental build cache", 2)[1]?.split("\n\n", 1)[0] ?? ""

        expect(restore).toContain("${{ github.workspace }}/apps/web/.next/cache")
        expect(restore).toContain(key)
        expect(restore).toContain("restore-keys: |\n            ${{ runner.os }}-nextjs-${{ hashFiles('apps/web/pnpm-lock.yaml') }}-\n")
        expect(save).toContain("${{ github.workspace }}/apps/web/.next/cache")
        expect(save).toContain(key)
        // Pull requests reuse the newest push cache instead of saving one per run.
        expect(saveStep).toContain("if: github.event_name == 'push'")
        // A source-file hash would also hash node_modules on every run.
        expect(workflow).not.toContain("hashFiles('apps/web/**")
    })
})
