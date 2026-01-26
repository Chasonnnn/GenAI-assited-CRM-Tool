import fs from "node:fs"
import path from "node:path"
import { describe, it, expect } from "vitest"

const ROOT = path.resolve(__dirname, "..")
const EXCLUDED_DIRS = new Set(["node_modules", ".next", "dist", "tests"])

function collectSourceFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    if (EXCLUDED_DIRS.has(entry.name)) {
      continue
    }

    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...collectSourceFiles(fullPath))
      continue
    }

    if (entry.isFile() && (fullPath.endsWith(".ts") || fullPath.endsWith(".tsx"))) {
      files.push(fullPath)
    }
  }

  return files
}

describe("next navigation", () => {
  it("does not clobber Next.js router history state", () => {
    const violations: string[] = []
    const files = collectSourceFiles(ROOT)

    for (const file of files) {
      const contents = fs.readFileSync(file, "utf8")

      if (contents.includes("window.history.pushState({},") || contents.includes("window.history.replaceState({},")) {
        violations.push(file)
      }
    }

    expect(violations).toEqual([])
  })
})

