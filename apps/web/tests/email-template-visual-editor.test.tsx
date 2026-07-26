import { createRef } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
    EmailTemplateVisualEditor,
    type EmailTemplateVisualEditorHandle,
} from "@/components/email/email-template-visual-editor"

const APPOINTMENT_TEMPLATE = `<div style="background-color:#fee2e2;padding:30px">
        <h1 style="color:#991b1b">Appointment Cancelled</h1>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
            <tbody><tr><td style="padding:8px">{{appointment_type}}</td></tr></tbody>
        </table>
        <p><br></p>
        <a href="{{appointment_manage_url}}">Manage appointment</a>
        <img src="{{org_logo_url}}" alt="Organization logo" width="120" style="max-width:120px;height:auto">
    </div>`

describe("EmailTemplateVisualEditor", () => {
    afterEach(() => {
        Reflect.deleteProperty(document, "execCommand")
    })

    it("keeps the original source byte-for-byte until the user changes the body", () => {
        const editorRef = createRef<EmailTemplateVisualEditorHandle>()
        const onChange = vi.fn()

        render(
            <EmailTemplateVisualEditor
                ref={editorRef}
                content={APPOINTMENT_TEMPLATE}
                onChange={onChange}
                ariaLabel="Email body"
            />,
        )

        expect(editorRef.current?.getHtml()).toBe(APPOINTMENT_TEMPLATE)
        expect(onChange).not.toHaveBeenCalled()
        const table = screen
            .getByRole("textbox", { name: "Email body" })
            .querySelector("table")
        expect(
            Array.from(table?.childNodes ?? []).some(
                (node) =>
                    node.nodeType === Node.TEXT_NODE &&
                    !node.textContent?.trim(),
            ),
        ).toBe(false)
    })

    it("preserves advanced appointment layout after a visual text edit", () => {
        const editorRef = createRef<EmailTemplateVisualEditorHandle>()
        const onChange = vi.fn()

        render(
            <EmailTemplateVisualEditor
                ref={editorRef}
                content={APPOINTMENT_TEMPLATE}
                onChange={onChange}
                ariaLabel="Email body"
            />,
        )

        const editor = screen.getByRole("textbox", { name: "Email body" })
        const heading = editor.querySelector("h1")
        expect(heading).not.toBeNull()
        if (!heading) return

        heading.textContent = "Appointment Cancelled — updated"
        fireEvent.input(editor)

        const edited = editorRef.current?.getHtml() ?? ""
        expect(edited).toContain("Appointment Cancelled — updated")
        expect(edited).toContain("<table")
        expect(edited).toContain("<tbody><tr><td")
        expect(edited).toContain("{{appointment_type}}")
        expect(edited).toContain("{{appointment_manage_url}}")
        expect(edited).toContain("{{org_logo_url}}")
        expect(edited).toMatch(/<p>(?:<br>|&nbsp;)<\/p>/)
        expect(edited).toMatch(/max-width:\s*120px/)
        expect(onChange).toHaveBeenLastCalledWith(edited)
    })

    it("does not rewrite the source for a toolbar command that changes nothing", () => {
        const editorRef = createRef<EmailTemplateVisualEditorHandle>()
        const onChange = vi.fn()
        Object.defineProperty(document, "execCommand", {
            configurable: true,
            value: vi.fn(() => false),
        })

        render(
            <EmailTemplateVisualEditor
                ref={editorRef}
                content={APPOINTMENT_TEMPLATE}
                onChange={onChange}
                ariaLabel="Email body"
            />,
        )
        fireEvent.click(screen.getByRole("button", { name: "Undo" }))

        expect(editorRef.current?.getHtml()).toBe(APPOINTMENT_TEMPLATE)
        expect(onChange).not.toHaveBeenCalled()
    })

    it("removes executable markup introduced after the editor mounts", () => {
        const editorRef = createRef<EmailTemplateVisualEditorHandle>()
        const onChange = vi.fn()

        render(
            <EmailTemplateVisualEditor
                ref={editorRef}
                content="<p>Safe</p>"
                onChange={onChange}
                ariaLabel="Email body"
            />,
        )

        const editor = screen.getByRole("textbox", { name: "Email body" })
        editor.innerHTML =
            '<div onclick="alert(1)"><script>alert(1)</script><a href="javascript:alert(1)">Safe text</a></div>'
        fireEvent.input(editor)

        expect(editor.querySelector("script")).toBeNull()
        expect(editor.querySelector("[onclick]")).toBeNull()
        expect(editor.querySelector("a")).not.toHaveAttribute("href")
        expect(editorRef.current?.getHtml()).not.toMatch(
            /<script|onclick|javascript:/i,
        )
        expect(onChange).toHaveBeenCalledOnce()
    })

    it("sanitizes rich clipboard HTML before inserting it", () => {
        const execCommand = vi.fn(() => false)
        Object.defineProperty(document, "execCommand", {
            configurable: true,
            value: execCommand,
        })

        render(
            <EmailTemplateVisualEditor
                content="<p>Safe</p>"
                onChange={vi.fn()}
                ariaLabel="Email body"
            />,
        )

        fireEvent.paste(screen.getByRole("textbox", { name: "Email body" }), {
            clipboardData: {
                getData: (type: string) =>
                    type === "text/html"
                        ? '<img src="x" onerror="alert(1)"><script>alert(1)</script><p>Paste me</p>'
                        : "Paste me",
            },
        })

        expect(execCommand).toHaveBeenCalledWith(
            "insertHTML",
            false,
            expect.not.stringMatching(/<script|onerror/i),
        )
    })

    it("does not mount executable markup in the visual authoring surface", () => {
        render(
            <EmailTemplateVisualEditor
                content={'<div onclick="alert(1)"><script>alert(1)</script><a href="javascript:alert(1)">Safe text</a></div>'}
                onChange={vi.fn()}
                ariaLabel="Email body"
            />,
        )

        const editor = screen.getByRole("textbox", { name: "Email body" })
        expect(editor.querySelector("script")).toBeNull()
        expect(editor.querySelector("[onclick]")).toBeNull()
        expect(editor.querySelector("a")).not.toHaveAttribute("href")
        expect(editor).toHaveTextContent("Safe text")
    })
})
