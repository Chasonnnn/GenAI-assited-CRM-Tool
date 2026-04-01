import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import {
    type CombinedActivity,
    useMatchDetailTabData,
} from "../app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabData"

type MatchDetailTabDataParams = Parameters<typeof useMatchDetailTabData>[0]

const DEFAULT_PARAMS: MatchDetailTabDataParams = {
    sourceFilter: "all",
    surrogateNotes: [],
    intendedParentNotes: [],
    surrogateFiles: [],
    intendedParentFiles: [],
    surrogateTasks: { items: [] },
    intendedParentTasks: { items: [] },
    surrogateActivity: { items: [] },
    intendedParentHistory: [],
    match: null,
}

function ActivityHarness(overrides: Partial<MatchDetailTabDataParams>) {
    const { filteredActivity } = useMatchDetailTabData({
        ...DEFAULT_PARAMS,
        ...overrides,
    })

    return (
        <pre data-testid="activity-json">{JSON.stringify(filteredActivity)}</pre>
    )
}

function readActivity(): CombinedActivity[] {
    const content = screen.getByTestId("activity-json").textContent ?? "[]"
    return JSON.parse(content) as CombinedActivity[]
}

describe("useMatchDetailTabData activity aggregation", () => {
    it("includes intended parent notes and files in the match activity feed", () => {
        render(
            <ActivityHarness
                intendedParentNotes={[
                    {
                        id: "ip-note-1",
                        content: "<p>IP note from detail page</p>",
                        created_at: "2026-03-25T16:05:00Z",
                    },
                ]}
                intendedParentFiles={[
                    {
                        id: "ip-file-1",
                        filename: "ivf-plan.pdf",
                        file_size: 1024,
                        created_at: "2026-03-25T16:06:00Z",
                    },
                ]}
            />,
        )

        expect(readActivity()).toEqual(
            expect.arrayContaining([
                expect.objectContaining({
                    source: "ip",
                    event_type: "Note",
                    description: "IP note from detail page",
                }),
                expect.objectContaining({
                    source: "ip",
                    event_type: "File uploaded",
                    description: "ivf-plan.pdf",
                }),
            ]),
        )
    })

    it("dedupes the synthetic match proposed row when the surrogate activity already contains it", () => {
        render(
            <ActivityHarness
                surrogateActivity={{
                    items: [
                        {
                            id: "surrogate-match-proposed",
                            activity_type: "match_proposed",
                            details: {
                                description: "Match was proposed",
                            },
                            actor_name: "Janet Zhu",
                            created_at: "2026-03-25T16:03:00Z",
                        },
                    ],
                }}
                match={{
                    proposed_at: "2026-03-25T16:03:00Z",
                    created_at: "2026-03-25T16:03:00Z",
                    updated_at: "2026-03-25T16:03:00Z",
                }}
            />,
        )

        const proposedEntries = readActivity().filter((entry) =>
            /match[_ ]proposed/i.test(entry.event_type),
        )

        expect(proposedEntries).toHaveLength(1)
    })

    it("humanizes surrogate activity labels and reuses detail previews", () => {
        render(
            <ActivityHarness
                surrogateActivity={{
                    items: [
                        {
                            id: "surrogate-file-1",
                            activity_type: "attachment_added",
                            details: {
                                filename: "medical-records.pdf",
                            },
                            actor_name: "Janet Zhu",
                            created_at: "2026-03-25T16:04:00Z",
                        },
                    ],
                }}
            />,
        )

        expect(readActivity()).toEqual([
            expect.objectContaining({
                source: "surrogate",
                event_type: "File uploaded",
                description: "medical-records.pdf",
            }),
        ])
    })
})
