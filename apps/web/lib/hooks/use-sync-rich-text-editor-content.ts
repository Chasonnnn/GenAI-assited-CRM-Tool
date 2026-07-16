import { useEffect } from "react"

type RichTextContentEditor = {
    getHTML: () => string
    commands: {
        setContent: (content: string) => unknown
    }
}

export function useSyncRichTextEditorContent(
    editor: RichTextContentEditor | null,
    content: string,
) {
    useEffect(() => {
        if (!editor || content === editor.getHTML()) return
        editor.commands.setContent(content)
    }, [content, editor])
}
