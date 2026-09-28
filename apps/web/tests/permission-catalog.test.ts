import { describe, expect, it } from "vitest"

import { groupRolePermissions } from "@/components/permissions/permission-catalog"
import type { PermissionTopic, RolePermission } from "@/lib/api/permissions"

function permission(
    key: string,
    label: string,
    topic: PermissionTopic,
    section: string,
    shortLabel: string,
): RolePermission {
    return {
        key,
        label,
        description: "",
        is_granted: false,
        developer_only: false,
        topic,
        section,
        short_label: shortLabel,
    }
}

describe("groupRolePermissions", () => {
    it("lists the intended parent stage permission with its record-type siblings", () => {
        const topics = groupRolePermissions({
            role: "case_manager",
            label: "Case Manager",
            policy_version: 1,
            permissions_by_category: {
                "Intended Parents": [
                    permission("edit_intended_parents", "Edit Intended Parents", "Intended Parents", "Records", "Edit"),
                    permission("change_intended_parent_status", "Change Intended Parent Status", "Intended Parents", "Progress & ownership", "Change status"),
                    permission("view_intended_parents", "View Intended Parents", "Intended Parents", "Records", "View"),
                ],
                Donors: [
                    permission("assign_donors", "Assign Donors", "Donors", "Progress & ownership", "Assign"),
                    permission("change_donor_status", "Change Donor Status", "Donors", "Progress & ownership", "Change status"),
                ],
            },
        })

        expect(Object.keys(topics["Intended Parents"])).toEqual(["Records", "Progress & ownership"])
        expect(topics["Intended Parents"]["Records"]?.map((row) => row.short_label)).toEqual(["View", "Edit"])
        expect(topics["Intended Parents"]["Progress & ownership"]?.map((row) => row.short_label)).toEqual(["Change status"])
        expect(topics.Donors["Progress & ownership"]?.map((row) => row.short_label)).toEqual(["Change status", "Assign"])
    })
})
