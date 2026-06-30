import type { CommentPosition } from "./context"

export function getMinSidebarHeight(positions: CommentPosition[]): number {
    if (positions.length === 0) return 100
    let maxBottom = 0
    for (const position of positions) {
        maxBottom = Math.max(maxBottom, position.top + position.height)
    }
    return maxBottom + 40
}
