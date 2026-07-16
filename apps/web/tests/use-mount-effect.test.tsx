import { render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useMountEffect } from "@/lib/hooks/use-mount-effect"

function MountLifecycleProbe({ onMount }: { onMount: () => void | (() => void) }) {
    useMountEffect(onMount)
    return null
}

describe("useMountEffect", () => {
    it("sets up once per mount and cleans up once on unmount", () => {
        const cleanup = vi.fn()
        const onMount = vi.fn(() => cleanup)
        const { rerender, unmount } = render(<MountLifecycleProbe onMount={onMount} />)

        rerender(<MountLifecycleProbe onMount={() => undefined} />)

        expect(onMount).toHaveBeenCalledTimes(1)
        expect(cleanup).not.toHaveBeenCalled()

        unmount()

        expect(cleanup).toHaveBeenCalledTimes(1)
    })
})
