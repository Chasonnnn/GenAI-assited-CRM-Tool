import { createRequire } from "node:module"
import { readdirSync, readFileSync } from "node:fs"
import path from "node:path"
import type * as TypeScript from "typescript"

// Shared by the class-policy tests (dialog width, button colors) so each policy reads the same
// source set and reports locations in the same "file:line" format.

const require = createRequire(import.meta.url)
const ts: typeof TypeScript = require("typescript")

const webRoot = path.resolve(import.meta.dirname, "..", "..")
const SOURCE_ROOTS = ["app", "components"]

export type JsxElementUsage = {
    file: string
    line: number
    tag: string
    /** Attribute source text: string literal contents, expression source, or true for bare flags. */
    attributes: Record<string, string | true>
}

export type ObjectCallUsage = {
    file: string
    line: number
    /** Property source text of the first object-literal argument. */
    properties: Record<string, string>
}

type SourceFile = { file: string; sourceFile: TypeScript.SourceFile }

function listTsxFiles(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const absolutePath = path.join(directory, entry.name)
        if (entry.isDirectory()) return listTsxFiles(absolutePath)
        return entry.isFile() && entry.name.endsWith(".tsx") ? [absolutePath] : []
    })
}

// Parsed once per test file; each policy scans the same sources.
let cachedSourceFiles: SourceFile[] | undefined

/** Timeout for tests that parse every source file; the full parallel suite slows parsing down. */
export const SOURCE_SCAN_TIMEOUT_MS = 30_000

function readSourceFiles(): SourceFile[] {
    cachedSourceFiles ??= parseSourceFiles()
    return cachedSourceFiles
}

function parseSourceFiles(): SourceFile[] {
    return SOURCE_ROOTS.flatMap((root) => listTsxFiles(path.join(webRoot, root)))
        .map((absolutePath) => path.relative(webRoot, absolutePath).split(path.sep).join("/"))
        .filter((file) => !file.startsWith("components/ui/"))
        .map((file) => ({
            file,
            sourceFile: ts.createSourceFile(
                file,
                readFileSync(path.join(webRoot, file), "utf8"),
                ts.ScriptTarget.Latest,
                true,
                ts.ScriptKind.TSX,
            ),
        }))
}

function lineOf(sourceFile: TypeScript.SourceFile, node: TypeScript.Node) {
    return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
}

function initializerText(sourceFile: TypeScript.SourceFile, initializer: TypeScript.Node): string {
    if (ts.isStringLiteral(initializer)) return initializer.text
    if (ts.isJsxExpression(initializer) && initializer.expression) {
        const expression = initializer.expression
        return ts.isStringLiteral(expression) ? expression.text : expression.getText(sourceFile)
    }
    return initializer.getText(sourceFile)
}

/** JSX elements with one of `tags` in app/ and components/ (excluding components/ui). */
export function scanJsxElements(tags: readonly string[]): JsxElementUsage[] {
    const usages: JsxElementUsage[] = []
    for (const { file, sourceFile } of readSourceFiles()) {
        const visit = (node: TypeScript.Node) => {
            if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
                const tag = node.tagName.getText(sourceFile)
                if (tags.includes(tag)) {
                    const attributes: Record<string, string | true> = {}
                    for (const property of node.attributes.properties) {
                        if (!ts.isJsxAttribute(property)) continue
                        attributes[property.name.getText(sourceFile)] = property.initializer
                            ? initializerText(sourceFile, property.initializer)
                            : true
                    }
                    usages.push({ file, line: lineOf(sourceFile, node), tag, attributes })
                }
            }
            ts.forEachChild(node, visit)
        }
        visit(sourceFile)
    }
    return usages
}

/** Calls such as `buttonVariants({ variant, className })` whose first argument is an object literal. */
export function scanObjectCalls(callee: string): ObjectCallUsage[] {
    const usages: ObjectCallUsage[] = []
    for (const { file, sourceFile } of readSourceFiles()) {
        const visit = (node: TypeScript.Node) => {
            if (ts.isCallExpression(node) && node.expression.getText(sourceFile) === callee) {
                const [argument] = node.arguments
                const properties: Record<string, string> = {}
                if (argument && ts.isObjectLiteralExpression(argument)) {
                    for (const property of argument.properties) {
                        if (ts.isPropertyAssignment(property)) {
                            properties[property.name.getText(sourceFile)] = ts.isStringLiteral(property.initializer)
                                ? property.initializer.text
                                : property.initializer.getText(sourceFile)
                        }
                    }
                }
                usages.push({ file, line: lineOf(sourceFile, node), properties })
            }
            ts.forEachChild(node, visit)
        }
        visit(sourceFile)
    }
    return usages
}

/** Class tokens from source text (string contents or a cn(...) expression). */
export function classTokens(text: string): string[] {
    return text.split(/[\s"'`{}(),?]+/).filter(Boolean)
}

/** The utility part of a class token, without variant prefixes or the important marker. */
export function utilityOf(token: string): string {
    return token.slice(token.lastIndexOf(":") + 1).replace(/^!/, "")
}

export function countByFile(entries: ReadonlyArray<{ file: string }>): Record<string, number> {
    const counts: Record<string, number> = {}
    for (const { file } of entries) counts[file] = (counts[file] ?? 0) + 1
    return counts
}

/** Files whose count exceeds the allowlist, formatted for a readable failure. */
export function exceedAllowlist(
    counts: Record<string, number>,
    allowlist: Readonly<Record<string, number>>,
): string[] {
    return Object.entries(counts)
        .filter(([file, count]) => count > (allowlist[file] ?? 0))
        .map(([file, count]) => `${file}: ${count} (allowed ${allowlist[file] ?? 0})`)
        .sort()
}
