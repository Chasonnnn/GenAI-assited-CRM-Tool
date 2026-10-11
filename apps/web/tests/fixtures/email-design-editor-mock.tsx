import * as React from "react"
import { vi } from "vitest"

import type { EmailDesignEditorHandle } from "@/components/email/design/email-design-editor"
import type { EmailBodyDesign } from "@/lib/api/email-templates"
import type { EmailBodyValue } from "@/lib/email-design"

type MockDesignEditorProps = {
    initialValue: EmailBodyValue
    onChange: (value: EmailBodyValue) => void
    variables: Array<{ name: string }>
    onSelectVariable?: (variable: { name: string }) => void
    onFocus?: () => void
    fields?: React.ReactNode
    canvas?: (body: React.ReactNode) => React.ReactNode
    panel?: React.ReactNode
    settings?: React.ReactNode
    documentStyles?: boolean
    error?: React.ReactNode
}

/** Shared state for `vi.mock("@/components/email/design/email-design-editor", ...)`. */
export const emailDesignEditorMock = {
    render: vi.fn<(props: MockDesignEditorProps) => void>(),
    insertImage: vi.fn<(src: string, alt: string) => void>(),
    /** The design reported with every body change. */
    nextDesign: null as EmailBodyDesign | null,
    reset() {
        this.render.mockReset()
        this.insertImage.mockReset()
        this.nextDesign = null
    },
}

/** Replaces the TipTap editor with a textarea labelled "Email body". */
export const EmailDesignEditor = React.forwardRef<EmailDesignEditorHandle, MockDesignEditorProps>(
    function MockEmailDesignEditor(props, ref) {
        emailDesignEditorMock.render(props)
        const [body, setBody] = React.useState(props.initialValue.body)
        const update = (next: string) => {
            setBody(next)
            props.onChange({ body: next, bodyDesign: emailDesignEditorMock.nextDesign })
        }
        React.useImperativeHandle(ref, () => ({
            insertText: (text: string) => update(`${body}${text}`),
            insertImage: (src: string, alt: string) => emailDesignEditorMock.insertImage(src, alt),
        }))
        const textarea = (
            <textarea
                aria-label="Email body"
                value={body}
                onFocus={props.onFocus}
                onChange={(event) => update(event.target.value)}
            />
        )
        return (
            <>
                {props.canvas ? (
                    props.canvas(textarea)
                ) : (
                    <>
                        {props.fields}
                        {textarea}
                    </>
                )}
                {props.panel}
                {props.variables.map((variable) => (
                    <button
                        key={variable.name}
                        type="button"
                        onClick={() => props.onSelectVariable?.(variable)}
                    >
                        {`Insert {{${variable.name}}}`}
                    </button>
                ))}
                {props.settings}
                {props.error}
            </>
        )
    },
)
