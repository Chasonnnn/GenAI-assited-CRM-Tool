import { afterEach, describe, expect, it, vi } from "vitest"

import { getAppointmentForManage } from "@/lib/api/appointments"

describe("public appointments API", () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it("turns FastAPI validation details into a readable management-link error", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({
                        detail: [
                            {
                                loc: ["path", "org_id"],
                                msg: "Input should be a valid UUID",
                                type: "uuid_parsing",
                            },
                        ],
                    }),
                    {
                        status: 422,
                        statusText: "Unprocessable Content",
                        headers: { "Content-Type": "application/json" },
                    }
                )
            )
        )

        await expect(
            getAppointmentForManage("not-a-valid-org", "not-a-valid-token")
        ).rejects.toMatchObject({
            status: 422,
            message: "org_id: Input should be a valid UUID",
        })
    })
})
