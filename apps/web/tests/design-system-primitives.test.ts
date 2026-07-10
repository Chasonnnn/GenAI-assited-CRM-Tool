import { createRequire } from "node:module"
import { readdirSync, readFileSync } from "node:fs"
import path from "node:path"
import type * as TypeScript from "typescript"
import { describe, expect, it } from "vitest"

const require = createRequire(import.meta.url)
const ts: typeof TypeScript = require("typescript")
const webRoot = path.resolve(import.meta.dirname, "..")
const sourceRoots = ["app", "components"]
const allowedNativeInputTypes = new Set(["color", "file", "hidden"])
const expectedNativeInputExceptions = [
    "app/(app)/ai-studio/page.tsx <input type=file>",
    "app/(app)/automation/email-templates/page.tsx <input type=file>",
    "app/(app)/settings/page.tsx <input type=color>",
    "app/(app)/settings/page.tsx <input type=file>",
    "app/(app)/settings/page.tsx <input type=file>",
    "app/(app)/settings/pipelines/page.tsx <input type=color>",
    "app/intake/[slug]/page.client.tsx <input type=file>",
    "app/ops/templates/system/[systemKey]/page.client.tsx <input type=file>",
    "components/email/EmailAttachmentsPanel.tsx <input type=file>",
    "components/forms/builder/AutomationFormSettingsPanel.tsx <input type=file>",
    "components/import/CSVUpload.tsx <input type=file>",
    "components/matches/UploadFileDialog.tsx <input type=file>",
    "components/surrogates/SurrogateApplicationTab.tsx <input type=file>",
    "components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx <input type=hidden>",
    "components/surrogates/interviews/InterviewTab/AttachmentsDialog.tsx <input type=file>",
].sort()

function listTsxFiles(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const absolutePath = path.join(directory, entry.name)
        if (entry.isDirectory()) return listTsxFiles(absolutePath)
        return entry.isFile() && entry.name.endsWith(".tsx") ? [absolutePath] : []
    })
}

function listTypeScriptFiles(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const absolutePath = path.join(directory, entry.name)
        if (entry.isDirectory()) return listTypeScriptFiles(absolutePath)
        return entry.isFile() && /\.tsx?$/.test(entry.name) ? [absolutePath] : []
    })
}

function getStringAttribute(
    node: TypeScript.JsxOpeningLikeElement,
    attributeName: string,
): string | undefined {
    const attribute = node.attributes.properties.find(
        (property): property is TypeScript.JsxAttribute =>
            ts.isJsxAttribute(property) && property.name.getText() === attributeName,
    )
    return attribute?.initializer && ts.isStringLiteral(attribute.initializer)
        ? attribute.initializer.text
        : undefined
}

describe("design-system primitive boundary", () => {
    it("uses shared Base UI-backed primitives for visible interactive controls", () => {
        const violations: string[] = []
        const nativeInputExceptions: string[] = []
        const files = sourceRoots.flatMap((root) => listTsxFiles(path.join(webRoot, root)))

        for (const absolutePath of files) {
            const relativePath = path.relative(webRoot, absolutePath)
            if (relativePath.startsWith(`components${path.sep}ui${path.sep}`)) continue

            const source = readFileSync(absolutePath, "utf8")
            if (source.includes("@base-ui/react")) {
                violations.push(`${relativePath} imports Base UI outside components/ui`)
            }
            const sourceFile = ts.createSourceFile(
                relativePath,
                source,
                ts.ScriptTarget.Latest,
                true,
                ts.ScriptKind.TSX,
            )

            const visit = (node: TypeScript.Node) => {
                if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
                    const tagName = node.tagName.getText(sourceFile)
                    const inputType = tagName === "input" ? getStringAttribute(node, "type") : undefined
                    const isAllowedNativeInput =
                        tagName === "input" &&
                        inputType !== undefined &&
                        allowedNativeInputTypes.has(inputType)

                    if (isAllowedNativeInput) {
                        nativeInputExceptions.push(`${relativePath} <input type=${inputType}>`)
                    }

                    if (
                        ["button", "select", "textarea", "dialog"].includes(tagName) ||
                        (tagName === "input" && !isAllowedNativeInput)
                    ) {
                        const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile))
                        violations.push(`${relativePath}:${line + 1} <${tagName}>`)
                    }
                }

                ts.forEachChild(node, visit)
            }

            visit(sourceFile)
        }

        expect(violations, violations.join("\n")).toEqual([])
        expect(nativeInputExceptions.sort()).toEqual(expectedNativeInputExceptions)
    })

    it("backs the shared Button and Input wrappers with installed Base UI primitives", () => {
        const buttonSource = readFileSync(path.join(webRoot, "components/ui/button.tsx"), "utf8")
        const inputSource = readFileSync(path.join(webRoot, "components/ui/input.tsx"), "utf8")

        expect(buttonSource).toContain('from "@base-ui/react/button"')
        expect(buttonSource).toContain("<ButtonPrimitive")
        expect(buttonSource).toContain('from "@base-ui/react/use-render"')
        expect(inputSource).toContain('from "@base-ui/react/input"')
        expect(inputSource).toContain("<InputPrimitive")
    })

    it("uses Base UI instead of cmdk for the shared command surface", () => {
        const commandSource = readFileSync(path.join(webRoot, "components/ui/command.tsx"), "utf8")

        expect(commandSource).toContain('from "@base-ui/react/combobox"')
        expect(commandSource).not.toContain('from "cmdk"')
    })

    it("uses Base UI instead of Sonner for the shared toast surface", () => {
        const toastSource = readFileSync(path.join(webRoot, "components/ui/toast.tsx"), "utf8")

        expect(toastSource).toContain('from "@base-ui/react/toast"')
        expect(toastSource).not.toContain('from "sonner"')
    })

    it("keeps cmdk and Sonner out of production source and dependencies", () => {
        const forbiddenImports: string[] = []
        for (const root of ["app", "components", "lib"]) {
            for (const absolutePath of listTypeScriptFiles(path.join(webRoot, root))) {
                const source = readFileSync(absolutePath, "utf8")
                if (/from ["'](?:cmdk|sonner)["']/.test(source)) {
                    forbiddenImports.push(path.relative(webRoot, absolutePath))
                }
            }
        }

        const packageJson = JSON.parse(readFileSync(path.join(webRoot, "package.json"), "utf8")) as {
            dependencies?: Record<string, string>
        }
        expect(forbiddenImports).toEqual([])
        expect(packageJson.dependencies?.cmdk).toBeUndefined()
        expect(packageJson.dependencies?.sonner).toBeUndefined()
    })
})
