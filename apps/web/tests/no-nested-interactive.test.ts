import fs from "node:fs"
import path from "node:path"
import ts from "typescript"
import { describe, it, expect } from "vitest"

const INTERACTIVE_TAGS = new Set([
  "a",
  "button",
  "Link",
  "Button",
  "AlertDialogTrigger",
  "DialogTrigger",
  "SheetTrigger",
  "PopoverTrigger",
  "DropdownMenuTrigger",
  "DropdownMenuItem",
  "DropdownMenuSubTrigger",
  "DropdownMenuCheckboxItem",
  "DropdownMenuRadioItem",
  "MenubarTrigger",
  "MenubarItem",
  "MenubarSubTrigger",
  "MenubarCheckboxItem",
  "MenubarRadioItem",
  "TabsTrigger",
  "SidebarMenuButton",
  "SidebarMenuSubButton",
  "SidebarMenuAction",
])

const ROOT = path.resolve(__dirname, "..")
const EXCLUDED_DIRS = new Set(["node_modules", ".next", "dist", "tests"])

function collectTsxFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    if (EXCLUDED_DIRS.has(entry.name)) {
      continue
    }

    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...collectTsxFiles(fullPath))
      continue
    }

    if (entry.isFile() && fullPath.endsWith(".tsx")) {
      files.push(fullPath)
    }
  }

  return files
}

function getTagName(tag: ts.JsxTagNameExpression): string | null {
  if (ts.isIdentifier(tag)) {
    return tag.text
  }
  if (tag.kind === ts.SyntaxKind.JsxMemberExpression) {
    return (tag as ts.JsxMemberExpression).name.text
  }
  return null
}

function findFirstInteractiveDescendant(node: ts.Node): { tagName: string; node: ts.Node } | null {
  if (ts.isJsxElement(node)) {
    const tagName = getTagName(node.openingElement.tagName)
    if (tagName && INTERACTIVE_TAGS.has(tagName)) {
      return { tagName, node }
    }
  }

  if (ts.isJsxSelfClosingElement(node)) {
    const tagName = getTagName(node.tagName)
    if (tagName && INTERACTIVE_TAGS.has(tagName)) {
      return { tagName, node }
    }
  }

  let found: { tagName: string; node: ts.Node } | null = null
  node.forEachChild((child) => {
    if (found) {
      return
    }
    found = findFirstInteractiveDescendant(child)
  })

  return found
}

describe("navigation markup", () => {
  it("does not nest interactive elements", () => {
    const violations: string[] = []
    const files = collectTsxFiles(ROOT)

    for (const file of files) {
      const contents = fs.readFileSync(file, "utf8")
      const source = ts.createSourceFile(
        file,
        contents,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX
      )

      const visit = (node: ts.Node) => {
        if (ts.isJsxElement(node)) {
          const parentTag = getTagName(node.openingElement.tagName)
          if (parentTag && INTERACTIVE_TAGS.has(parentTag)) {
            for (const child of node.children) {
              const descendant = findFirstInteractiveDescendant(child)
              if (descendant) {
                const pos = source.getLineAndCharacterOfPosition(
                  descendant.node.getStart()
                )
                violations.push(
                  `${file}:${pos.line + 1}:${pos.character + 1} ` +
                    `${parentTag} contains ${descendant.tagName}`
                )
                break
              }
            }
          }
        }
        node.forEachChild(visit)
      }

      visit(source)
    }

    expect(violations).toEqual([])
  })
})
