"use client"

import { EntityTasksSection } from "@/components/tasks/EntityTasksSection"
import type { Donor } from "@/lib/types/donor"

export function DonorTasksSection({ donor, canView, canCreate }: {
    donor: Donor
    canView: boolean
    canCreate: boolean
}) {
    return <EntityTasksSection
        key={donor.id}
        subject={{ donor_id: donor.id }}
        record={{ donor_id: donor.id, donor_number: donor.donor_number, donor_type: donor.donor_type, donor_name: donor.full_name }}
        canView={canView}
        canCreate={canCreate}
        archived={donor.is_archived}
    />
}
