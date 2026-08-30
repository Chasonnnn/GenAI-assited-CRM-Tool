import { describe, expect, it } from "vitest"

import {
    getTaskRelatedRecordSelection,
    getTaskRelatedRecords,
    toTaskRelatedRecordPayload,
} from "@/lib/task-related-record"

describe("task related-record presentation", () => {
    it("presents donor subtype, donor number, and detail route", () => {
        expect(getTaskRelatedRecords({
            donor_id: "donor-1",
            donor_number: "D10001",
            donor_type: "egg",
            donor_name: "Maya Thompson",
        })).toEqual([
            {
                kind: "donor",
                id: "donor-1",
                href: "/donors/donor-1",
                label: "Egg Donor D10001",
            },
        ])
    })

    it("fails closed when donor metadata is inaccessible or deleted", () => {
        expect(getTaskRelatedRecords({
            donor_id: "donor-1",
            donor_number: null,
            donor_type: null,
            donor_name: null,
        })).toEqual([
            {
                kind: "donor",
                id: "donor-1",
                href: null,
                label: "Donor unavailable",
            },
        ])
    })

    it("uses one selection contract for create, edit, and clear", () => {
        const selection = getTaskRelatedRecordSelection({ donor_id: "donor-1" })
        expect(selection).toBe("donor:donor-1")
        expect(toTaskRelatedRecordPayload(selection)).toEqual({
            surrogate_id: null,
            intended_parent_id: null,
            donor_id: "donor-1",
        })
        expect(toTaskRelatedRecordPayload("none")).toEqual({
            surrogate_id: null,
            intended_parent_id: null,
            donor_id: null,
        })
    })
})
