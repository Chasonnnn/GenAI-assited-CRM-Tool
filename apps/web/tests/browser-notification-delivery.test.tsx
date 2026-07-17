import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useBrowserNotificationDelivery } from "@/lib/hooks/use-browser-notification-delivery"

const notification = {
    id: "notification-1",
    title: "Surrogate assigned",
    body: "A surrogate was assigned.",
    entity_type: "surrogate",
    entity_id: "surrogate-1",
    type: "surrogate_assigned",
}

describe("useBrowserNotificationDelivery", () => {
    beforeEach(() => {
        Object.defineProperty(document, "hidden", {
            configurable: true,
            value: true,
        })
    })

    it("delivers each hidden-tab notification only once", () => {
        const showNotification = vi.fn()
        const { rerender } = renderHook(
            ({ latest }) =>
                useBrowserNotificationDelivery({
                    latest,
                    permission: "granted",
                    showNotification,
                }),
            {
                initialProps: { latest: notification },
            },
        )

        expect(showNotification).toHaveBeenCalledTimes(1)
        expect(showNotification).toHaveBeenCalledWith("Surrogate assigned", {
            tag: "notification-1",
            body: "A surrogate was assigned.",
            entityType: "surrogate",
            entityId: "surrogate-1",
            notificationType: "surrogate_assigned",
        })

        rerender({ latest: { ...notification } })

        expect(showNotification).toHaveBeenCalledTimes(1)
    })
})
