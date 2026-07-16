"use client"

import { useEffect } from "react"

import type { TipTapDoc } from "@/lib/api/interviews"

const EMPTY_TIPTAP_DOCUMENT: TipTapDoc = {
    type: "doc",
    content: [],
}

type TipTapJsonEditor = {
    getJSON: () => unknown
    commands: {
        setContent: (content: TipTapDoc) => unknown
    }
}

export function useSyncTipTapJsonContent(
    editor: TipTapJsonEditor | null,
    content: TipTapDoc | null | undefined,
) {
    useEffect(() => {
        if (!editor) return
        const nextContent = content ?? EMPTY_TIPTAP_DOCUMENT
        if (JSON.stringify(editor.getJSON()) === JSON.stringify(nextContent)) return
        editor.commands.setContent(nextContent)
    }, [content, editor])
}
