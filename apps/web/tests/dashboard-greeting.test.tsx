import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import {
    DashboardGreeting,
    getFirstName,
    getGreeting,
} from "../app/(app)/dashboard/components/dashboard-greeting"

const at = (hour: number, minute = 0) => new Date(2026, 9, 3, hour, minute)

describe("getGreeting", () => {
    it.each([
        [5, "Good morning"],
        [11, "Good morning"],
        [12, "Good afternoon"],
        [16, "Good afternoon"],
        [17, "Good evening"],
        [23, "Good evening"],
        [2, "Good evening"],
    ])("uses the time of day at %i:00", (hour, expected) => {
        expect(getGreeting(at(hour), null)).toBe(expected)
    })

    it("says welcome back within two hours of the last visit", () => {
        const now = at(9)
        expect(getGreeting(now, at(7, 1).getTime())).toBe("Welcome back")
        expect(getGreeting(now, at(7).getTime())).toBe("Good morning")
    })

    it("ignores a last visit in the future", () => {
        expect(getGreeting(at(9), at(10).getTime())).toBe("Good morning")
    })
})

describe("getFirstName", () => {
    it("takes the first word of the display name", () => {
        expect(getFirstName("  Haocheng Zhang ")).toBe("Haocheng")
        expect(getFirstName("")).toBeNull()
        expect(getFirstName(undefined)).toBeNull()
    })
})

describe("DashboardGreeting", () => {
    beforeEach(() => {
        window.localStorage.clear()
        vi.useFakeTimers({ toFake: ["Date"] })
        vi.setSystemTime(at(9))
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("greets by time of day on the first visit and records the visit per user", () => {
        render(<DashboardGreeting userId="user-1" displayName="Haocheng Zhang" />)

        expect(screen.getByText("Good morning, Haocheng")).toBeInTheDocument()
        expect(window.localStorage.getItem("dashboard-last-visit-user-1")).toBe(String(at(9).getTime()))
    })

    it("says welcome back after a recent visit and keeps the greeting stable on re-render", () => {
        window.localStorage.setItem("dashboard-last-visit-user-1", String(at(8).getTime()))

        const { rerender } = render(<DashboardGreeting userId="user-1" displayName="Haocheng Zhang" />)
        rerender(<DashboardGreeting userId="user-1" displayName="Haocheng Zhang" />)

        expect(screen.getByText("Welcome back, Haocheng")).toBeInTheDocument()
    })

    it("does not use another user's last visit", () => {
        window.localStorage.setItem("dashboard-last-visit-user-2", String(at(8).getTime()))

        render(<DashboardGreeting userId="user-1" displayName="Haocheng Zhang" />)

        expect(screen.getByText("Good morning, Haocheng")).toBeInTheDocument()
    })

    it("falls back to the time of day when storage is unavailable", () => {
        const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("blocked")
        })
        const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
            throw new Error("blocked")
        })

        render(<DashboardGreeting userId="user-1" displayName={undefined} />)

        expect(screen.getByText("Good morning")).toBeInTheDocument()
        getItem.mockRestore()
        setItem.mockRestore()
    })
})
