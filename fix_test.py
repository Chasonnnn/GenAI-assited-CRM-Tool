import re
with open("apps/web/tests/dependency-security.test.ts", "r") as f:
    content = f.read()

new_tests = """
    it("pins browserslist to a non-vulnerable version in pnpm overrides", () => {
        const browserslistOverride = readPnpmOverrides().browserslist

        expect(browserslistOverride).toBeDefined()
        expect(compareVersions(browserslistOverride!.replace(/^[^\\d]*/, ""), "4.28.7")).toBeGreaterThanOrEqual(0)
    })

    it("resolves only non-vulnerable browserslist versions in pnpm-lock.yaml", () => {
        const lockfile = readFileSync(join(process.cwd(), "pnpm-lock.yaml"), "utf8")
        const resolvedVersions = Array.from(
            lockfile.matchAll(/^\\s{2}browserslist@(\\d+\\.\\d+\\.\\d+):/gm),
            (match) => match[1],
        )

        expect(resolvedVersions.length).toBeGreaterThan(0)

        for (const resolvedVersion of resolvedVersions) {
            expect(compareVersions(resolvedVersion, "4.28.7")).toBeGreaterThanOrEqual(0)
        }
    })
"""

if 'it("resolves only non-vulnerable browserslist versions in pnpm-lock.yaml", () => {' not in content:
    content = content.replace("describe(\"Dependency Security\", () => {", "describe(\"Dependency Security\", () => {" + new_tests)

with open("apps/web/tests/dependency-security.test.ts", "w") as f:
    f.write(content)
