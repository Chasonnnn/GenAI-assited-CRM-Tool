export interface InsertAtCursorResult {
    nextValue: string
    nextSelectionStart: number
    nextSelectionEnd: number
}

export function insertAtCursor(
    value: string,
    token: string,
    selectionStart: number,
    selectionEnd: number
): InsertAtCursorResult {
    const safeValue = value ?? ""
    const start = Math.max(0, Math.min(selectionStart, safeValue.length))
    const end = Math.max(start, Math.min(selectionEnd, safeValue.length))
    const nextValue = `${safeValue.slice(0, start)}${token}${safeValue.slice(end)}`
    const cursor = start + token.length

    return {
        nextValue,
        nextSelectionStart: cursor,
        nextSelectionEnd: cursor,
    }
}

