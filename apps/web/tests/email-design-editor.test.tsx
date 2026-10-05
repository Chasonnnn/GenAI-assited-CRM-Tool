import { createRef } from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeAll, describe, expect, it, vi } from "vitest"

import {
    EmailDesignEditor,
    type EmailDesignEditorHandle,
} from "@/components/email/design/email-design-editor"
import type { EmailBodyValue } from "@/lib/email-design"

beforeAll(() => {
    // jsdom has no layout; ProseMirror measures ranges when it scrolls the selection into view.
    const emptyRects = () => Object.assign([], { item: () => null }) as unknown as DOMRectList
    Range.prototype.getClientRects ??= emptyRects
    Range.prototype.getBoundingClientRect ??= () => new DOMRect()
})

const DESIGN = {
    type: "doc" as const,
    content: [{ type: "paragraph", content: [{ type: "text", text: "Hi {{first_name}}" }] }],
}

function renderEditor(initialValue: EmailBodyValue) {
    const onChange = vi.fn<(value: EmailBodyValue) => void>()
    const ref = createRef<EmailDesignEditorHandle>()
    render(
        <EmailDesignEditor ref={ref} initialValue={initialValue} onChange={onChange} variables={[]} />,
    )
    return { onChange, ref }
}

async function settle() {
    await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0))
    })
}

describe("EmailDesignEditor", () => {
    it("opens a legacy body as an HTML block without reporting a change", async () => {
        const { onChange } = renderEditor({ body: "<p>Legacy {{first_name}}</p>", bodyDesign: null })

        expect(await screen.findByRole("button", { name: "Edit HTML" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Convert to blocks" })).toBeInTheDocument()
        expect(screen.getByTitle("HTML block")).toBeInTheDocument()
        await settle()
        expect(onChange).not.toHaveBeenCalled()
    })

    it("opens a stored design without reporting a change", async () => {
        const { onChange } = renderEditor({ body: "<p>Hi {{first_name}}</p>", bodyDesign: DESIGN })

        expect(await screen.findByText("{{first_name}}")).toHaveClass("email-variable-token")
        await settle()
        expect(onChange).not.toHaveBeenCalled()
    })

    it("compiles the design when content changes", async () => {
        const { onChange, ref } = renderEditor({ body: "<p>Hi {{first_name}}</p>", bodyDesign: DESIGN })
        await screen.findByText("{{first_name}}")

        act(() => ref.current?.insertText(" {{org_name}}"))

        await waitFor(() => expect(onChange).toHaveBeenCalled())
        const value = onChange.mock.lastCall?.[0]
        expect(value?.bodyDesign?.type).toBe("doc")
        expect(value?.body).toContain("{{org_name}}")
        expect(value?.body).not.toContain("<!--body-->")
    })

    it("saves edited HTML block content as raw HTML without a design", async () => {
        const { onChange } = renderEditor({ body: "<p>Old</p>", bodyDesign: null })

        fireEvent.click(await screen.findByRole("button", { name: "Edit HTML" }))
        const textarea = await screen.findByRole("textbox", { name: "HTML" })
        expect(textarea).toHaveValue("<p>Old</p>")
        fireEvent.change(textarea, { target: { value: "<p>New {{first_name}}</p>" } })
        fireEvent.click(screen.getByRole("button", { name: "Apply" }))

        await waitFor(() =>
            expect(onChange).toHaveBeenLastCalledWith({
                body: "<p>New {{first_name}}</p>",
                bodyDesign: null,
            }),
        )
    })

    it("shows the original and converted renders before replacing an HTML block", async () => {
        renderEditor({ body: "<h1>Title</h1><p>Body</p>", bodyDesign: null })

        fireEvent.click(await screen.findByRole("button", { name: "Convert to blocks" }))

        expect(await screen.findByTitle("Original HTML")).toBeInTheDocument()
        expect(await screen.findByTitle("Converted blocks")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Use blocks" })).toBeEnabled()
    })

    it("preserves emoji images, text styles, and links through conversion and editing", async () => {
        const { onChange, ref } = renderEditor({
            body: '<p>Hello 😊</p><img src="https://example.com/smile.png" alt="😊" width="24" height="24"><p style="margin-top:24px">Follow up <a href="https://example.com/form">Application</a></p><img src="https://example.com/heart.png" alt="💛" width="24" height="24">',
            bodyDesign: null,
        })
        fireEvent.click(await screen.findByRole("button", { name: "Convert to blocks" }))
        const preview = await screen.findByTitle("Converted blocks")
        const previewDoc = new DOMParser().parseFromString(
            preview.getAttribute("srcdoc") ?? "", "text/html",
        )
        expect(Array.from(previewDoc.images, (img) => img.alt)).toEqual(["😊", "💛"])
        expect(previewDoc.images[0]?.getAttribute("width")).toBe("24")
        const greeting = Array.from(previewDoc.querySelectorAll("p")).find((p) => p.textContent === "Hello 😊")
        expect(greeting?.style.fontSize).toBe("inherit")
        expect(greeting?.style.lineHeight).toBe("inherit")
        expect(greeting?.style.paddingTop).toBe("0px")
        expect(greeting?.parentElement?.style.fontFamily).toContain("Times New Roman")
        expect(previewDoc.querySelector('a[href="https://example.com/form"]')?.textContent).toBe("Application")
        expect(Array.from(previewDoc.querySelectorAll("p")).find((p) => p.textContent?.startsWith("Follow up"))?.getAttribute("style")).toContain("margin-top:24px")

        fireEvent.click(screen.getByRole("button", { name: "Use blocks" }))
        await waitFor(() => expect(onChange).toHaveBeenCalled())
        act(() => ref.current?.insertText(" {{first_name}}"))
        await waitFor(() => expect(onChange.mock.lastCall?.[0].body).toContain("{{first_name}}"))
        const saved = new DOMParser().parseFromString(onChange.mock.lastCall?.[0].body ?? "", "text/html")
        expect(Array.from(saved.images, (img) => img.alt)).toEqual(["😊", "💛"])
        expect(saved.body.textContent).toContain("Hello 😊")
        expect(saved.querySelector('a[href="https://example.com/form"]')?.textContent).toBe("Application")
    })

    it("warns before converting HTML with stylesheet rules the blocks cannot preserve", async () => {
        const { onChange } = renderEditor({
            body: '<style>.legacy { letter-spacing: 2px; }</style><p class="legacy">Styled text</p>',
            bodyDesign: null,
        })
        fireEvent.click(await screen.findByRole("button", { name: "Convert to blocks" }))
        await screen.findByTitle("Converted blocks")
        expect(screen.getByRole("alert")).toHaveTextContent("Stylesheet rules may change")
        fireEvent.click(screen.getByRole("button", { name: "Keep HTML" }))
        await settle()
        for (const [value] of onChange.mock.calls) {
            expect(value).toEqual({
                body: '<style>.legacy { letter-spacing: 2px; }</style><p class="legacy">Styled text</p>',
                bodyDesign: null,
            })
        }
    })
})
