import { describe, expect, it } from "vitest"

import type { FunnelStage, StatusCount } from "@/lib/api/analytics"
import type { PipelineStage } from "@/lib/api/pipelines"
import {
    buildFunnelChartData,
    buildStatusChartData,
} from "@/lib/reports-stage-colors"

const pipelineStages: PipelineStage[] = [
    {
        id: "stage-1",
        stage_key: "new_unread",
        slug: "new_unread",
        label: "New Unread",
        color: "#3B82F6",
        order: 1,
        stage_type: "intake",
        is_active: true,
    },
    {
        id: "stage-2",
        stage_key: "contacted",
        slug: "contacted",
        label: "Outreach Verified",
        color: "#0e7490",
        order: 2,
        stage_type: "intake",
        is_active: true,
    },
    {
        id: "stage-3",
        stage_key: "application_packet_received",
        slug: "application_packet_received",
        label: "Application Packet Received",
        color: "#6d28d9",
        order: 3,
        stage_type: "intake",
        is_active: true,
    },
] as PipelineStage[]

describe("reports stage colors", () => {
    it("uses pipeline stage colors for status chart data", () => {
        const byStatus: StatusCount[] = [
            { status: "Outreach Verified", stage_id: "stage-2", count: 4, order: 2 },
            { status: "Application Packet Received", stage_id: "stage-3", count: 2, order: 3 },
        ]

        expect(buildStatusChartData(byStatus, pipelineStages)).toEqual([
            { status: "Outreach Verified", count: 4, fill: "#0e7490" },
            { status: "Application Packet Received", count: 2, fill: "#6d28d9" },
        ])
    })

    it("uses pipeline stage colors for funnel data keyed by slug", () => {
        const funnel: FunnelStage[] = [
            {
                stage: "new_unread",
                label: "New Unread",
                count: 10,
                percentage: 100,
            },
            {
                stage: "application_packet_received",
                label: "Application Packet Received",
                count: 3,
                percentage: 30,
            },
        ]

        expect(buildFunnelChartData(funnel, pipelineStages)).toEqual([
            {
                stage: "new_unread",
                label: "New Unread",
                count: 10,
                percentage: 100,
                fill: "#3B82F6",
            },
            {
                stage: "application_packet_received",
                label: "Application Packet Received",
                count: 3,
                percentage: 30,
                fill: "#6d28d9",
            },
        ])
    })
})
