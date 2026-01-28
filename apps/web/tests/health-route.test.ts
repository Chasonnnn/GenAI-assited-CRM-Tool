import { GET } from "@/app/health/route"

describe("health route", () => {
    it("returns ok", async () => {
        const res = await GET()
        expect(res.status).toBe(200)
        const body = await res.json()
        expect(body).toEqual({ ok: true })
    })
})
