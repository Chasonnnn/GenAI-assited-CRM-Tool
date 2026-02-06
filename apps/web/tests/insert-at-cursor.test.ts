import { describe, expect, it } from "vitest"
import { insertAtCursor } from "@/lib/insert-at-cursor"

describe("insertAtCursor", () => {
    it("inserts a token at the cursor position", () => {
        const result = insertAtCursor("Hello", " {{full_name}}", 5, 5)
        expect(result.nextValue).toBe("Hello {{full_name}}")
        expect(result.nextSelectionStart).toBe(5 + " {{full_name}}".length)
        expect(result.nextSelectionEnd).toBe(5 + " {{full_name}}".length)
    })

    it("replaces the selected range with the token", () => {
        const result = insertAtCursor("Hello world", "{{name}}", 6, 11)
        expect(result.nextValue).toBe("Hello {{name}}")
        expect(result.nextSelectionStart).toBe(14)
        expect(result.nextSelectionEnd).toBe(14)
    })

    it("supports insertion at the beginning of the string", () => {
        const result = insertAtCursor("World", "Hello ", 0, 0)
        expect(result.nextValue).toBe("Hello World")
        expect(result.nextSelectionStart).toBe(6)
        expect(result.nextSelectionEnd).toBe(6)
    })
})
