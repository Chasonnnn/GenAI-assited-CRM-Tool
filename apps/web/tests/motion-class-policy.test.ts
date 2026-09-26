import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const SOURCE_ROOTS = ["app", "components", "lib", "hooks"]

function readSources(): Array<{ path: string; text: string }> {
    return SOURCE_ROOTS.flatMap((root) =>
        readdirSync(join(process.cwd(), root), { recursive: true, encoding: "utf8" })
            .filter((file) => /\.(ts|tsx)$/.test(file) && !/\.test\.tsx?$/.test(file))
            .map((file) => {
                const path = join(root, file)
                return { path, text: readFileSync(join(process.cwd(), path), "utf8") }
            }),
    )
}

function findMatches(pattern: RegExp, allow: (path: string, match: string) => boolean = () => false) {
    return readSources().flatMap(({ path, text }) =>
        text.split("\n").flatMap((line, index) =>
            Array.from(line.matchAll(pattern))
                .map((match) => match[0])
                .filter((match) => !allow(path, match))
                .map((match) => `${path}:${index + 1} ${match}`),
        ),
    )
}

describe("motion class policy", () => {
    it("uses Base UI state attributes instead of Radix data-state selectors", () => {
        // TableRow keeps data-[state=selected] as an opt-in API for callers that set data-state.
        const allowTableSelection = (path: string, match: string) =>
            path === join("components", "ui", "table.tsx") && match.includes("state=selected")

        expect(findMatches(/\S*\[data-state=[^\]]*\]\S*|\S*data-\[state=[^\]]*\]\S*/g, allowTableSelection)).toEqual([])
    })

    it("has no mangled translate utilities", () => {
        expect(findMatches(/\S*tranzinc\S*/g)).toEqual([])
    })

    it("does not use accordion keyframes that read Radix height variables", () => {
        expect(findMatches(/\S*animate-(accordion|collapsible)-(down|up)\S*/g)).toEqual([])
    })

    it("lists translate, scale, and rotate wherever an arbitrary transition lists transform", () => {
        // Tailwind v4 translate-*, scale-*, and rotate-* utilities set individual properties, not transform.
        const incomplete = findMatches(/transition-\[[^\]]*\]/g, (_path, match) => {
            const properties = match.slice("transition-[".length, -1).split(",")
            return !properties.includes("transform")
                || ["translate", "scale", "rotate"].every((property) => properties.includes(property))
        })

        expect(incomplete).toEqual([])
    })

    it("defines orientation variants for data-horizontal and data-vertical classes", () => {
        const globals = readFileSync(join(process.cwd(), "app/globals.css"), "utf8")

        expect(globals.match(/^@custom-variant data-(horizontal|vertical) .*$/gm)).toEqual([
            '@custom-variant data-horizontal (&[data-orientation="horizontal"]);',
            '@custom-variant data-vertical (&[data-orientation="vertical"]);',
        ])
    })
})
