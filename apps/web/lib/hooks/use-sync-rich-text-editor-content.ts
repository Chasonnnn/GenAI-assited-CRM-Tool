import { useEffect } from "react"

type RichTextContentEditor = {
    getHTML: () => string
    commands: {
        setContent: (
            content: string,
            options?: { emitUpdate?: boolean },
        ) => unknown
    }
}

export function useSyncRichTextEditorContent(
    editor: RichTextContentEditor | null,
    content: string,
) {
    useEffect(() => {
        if (!editor || content === editor.getHTML()) return
        editor.commands.setContent(content, { emitUpdate: false })
    }, [content, editor])
}
