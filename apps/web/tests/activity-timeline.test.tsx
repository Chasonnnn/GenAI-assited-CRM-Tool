import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ActivityTimeline } from '@/components/surrogates/ActivityTimeline'
import type { PipelineStage } from '@/lib/api/pipelines'
import type { SurrogateActivity, SurrogateStatusHistory } from '@/lib/api/surrogates'
import type { TaskListItem } from '@/lib/types/task'

const mockUseSurrogateHistory = vi.fn()

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogateHistory: () => mockUseSurrogateHistory(),
}))

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        prefetch: vi.fn(),
    }),
}))

vi.mock('date-fns', async () => {
    const actual = await vi.importActual<typeof import('date-fns')>('date-fns')
    return {
        ...actual,
        formatDistanceToNow: (date: Date) => `at ${date.toISOString()}`,
    }
})

function makeStage(overrides: Partial<PipelineStage> = {}): PipelineStage {
    return {
        id: 's1',
        slug: 'new_unread',
        label: 'New Unread',
        color: '#3b82f6',
        stage_type: 'intake',
        order: 1,
        is_active: true,
        ...overrides,
    }
}

function makeHistory(overrides: Partial<SurrogateStatusHistory> = {}): SurrogateStatusHistory {
    return {
        id: 'h1',
        from_stage_id: null,
        to_stage_id: 's1',
        from_label_snapshot: null,
        to_label_snapshot: 'New Unread',
        changed_by_user_id: null,
        changed_by_name: null,
        reason: null,
        changed_at: '2024-01-01T00:00:00.000Z',
        effective_at: '2024-01-01T00:00:00.000Z',
        recorded_at: '2024-01-01T00:00:00.000Z',
        ...overrides,
    }
}

function makeActivity(overrides: Partial<SurrogateActivity> = {}): SurrogateActivity {
    return {
        id: 'a1',
        activity_type: 'note_added',
        actor_user_id: null,
        actor_name: null,
        details: { preview: 'Note preview' },
        created_at: '2024-02-02T00:00:00.000Z',
        ...overrides,
    }
}

function makeTask(overrides: Partial<TaskListItem> = {}): TaskListItem {
    return {
        id: 't1',
        title: 'Follow up',
        description: null,
        task_type: 'follow_up',
        surrogate_id: 'surr1',
        surrogate_number: 'S10001',
        owner_type: 'user',
        owner_id: 'u1',
        owner_name: 'Owner',
        created_by_user_id: 'u1',
        created_by_name: 'Owner',
        due_date: '2024-02-10',
        due_time: null,
        duration_minutes: null,
        is_completed: false,
        status: 'pending',
        workflow_action_type: null,
        workflow_action_preview: null,
        due_at: null,
        completed_at: null,
        completed_by_name: null,
        created_at: '2024-02-01T00:00:00.000Z',
        ...overrides,
    }
}

describe('ActivityTimeline', () => {
    beforeEach(() => {
        mockUseSurrogateHistory.mockReturnValue({ data: [] })
    })

    it('expands a non-current stage when clicked', () => {
        const stages = [
            makeStage({ id: 's1', label: 'New Unread', order: 1 }),
            makeStage({ id: 's2', label: 'Ready to Match', order: 2, slug: 'ready_to_match' }),
        ]

        // Note: recorded_at must match effective_at to avoid backdated detection
        mockUseSurrogateHistory.mockReturnValue({
            data: [
                makeHistory({ id: 'h1', to_stage_id: 's1', changed_at: '2024-01-01T00:00:00.000Z', recorded_at: '2024-01-01T00:00:00.000Z' }),
                makeHistory({ id: 'h2', to_stage_id: 's2', changed_at: '2024-02-01T00:00:00.000Z', effective_at: '2024-02-01T00:00:00.000Z', recorded_at: '2024-02-01T00:00:00.000Z' }),
            ],
        })

        const activities = [
            makeActivity({
                id: 'a1',
                activity_type: 'note_added',
                details: { preview: 'Stage 2 note' },
                created_at: '2024-02-02T00:00:00.000Z',
            }),
        ]

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s1"
                stages={stages}
                activities={activities}
                tasks={[]}
            />
        )

        // Non-current, non-backdated stage starts collapsed
        expect(screen.queryByText('Stage 2 note')).not.toBeInTheDocument()

        const stageButton = screen.getByText('Ready to Match').closest('button')
        expect(stageButton).toBeTruthy()
        fireEvent.click(stageButton!)

        expect(screen.getByText('Stage 2 note')).toBeInTheDocument()
    })

    it('buckets activities using effective_at when backdated', () => {
        const stages = [
            makeStage({ id: 's1', label: 'New Unread', order: 1 }),
            makeStage({ id: 's2', label: 'Ready to Match', order: 2, slug: 'ready_to_match' }),
        ]

        mockUseSurrogateHistory.mockReturnValue({
            data: [
                makeHistory({
                    id: 'h1',
                    to_stage_id: 's1',
                    changed_at: '2024-01-01T00:00:00.000Z',
                    effective_at: '2024-01-01T00:00:00.000Z',
                }),
                makeHistory({
                    id: 'h2',
                    to_stage_id: 's2',
                    changed_at: '2024-01-10T00:00:00.000Z',
                    effective_at: '2024-01-05T00:00:00.000Z',
                }),
            ],
        })

        const activities = [
            makeActivity({
                id: 'a1',
                activity_type: 'note_added',
                details: { preview: 'Backdated note' },
                created_at: '2024-01-06T00:00:00.000Z',
            }),
        ]

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s2"
                stages={stages}
                activities={activities}
                tasks={[]}
            />
        )

        expect(screen.getByText('Backdated note')).toBeInTheDocument()
    })

    it('uses provider for email previews', () => {
        const stages = [makeStage({ id: 's1', label: 'New Unread', order: 1 })]

        mockUseSurrogateHistory.mockReturnValue({
            data: [makeHistory({ id: 'h1', to_stage_id: 's1' })],
        })

        const activities = [
            makeActivity({
                id: 'a1',
                activity_type: 'email_sent',
                details: { provider: 'gmail' },
                created_at: '2024-02-02T00:00:00.000Z',
            }),
        ]

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s1"
                stages={stages}
                activities={activities}
                tasks={[]}
            />
        )

        expect(screen.getByText(/via gmail/i)).toBeInTheDocument()
    })

    it('shows contact note preview in activity tracker entries', () => {
        const stages = [makeStage({ id: 's1', label: 'New Unread', order: 1 })]

        mockUseSurrogateHistory.mockReturnValue({
            data: [makeHistory({ id: 'h1', to_stage_id: 's1' })],
        })

        const activities = [
            makeActivity({
                id: 'a1',
                activity_type: 'contact_attempt',
                details: {
                    outcome: 'no_answer',
                    contact_methods: ['phone'],
                    note_preview: 'Left voicemail and asked for callback',
                },
                created_at: '2024-02-02T00:00:00.000Z',
            }),
        ]

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s1"
                stages={stages}
                activities={activities}
                tasks={[]}
            />
        )

        expect(screen.getByText(/no_answer/i)).toBeInTheDocument()
        expect(screen.getByText(/left voicemail and asked for callback/i)).toBeInTheDocument()
    })

    it('separates overdue tasks from upcoming tasks', () => {
        const stages = [makeStage({ id: 's1', label: 'New Unread', order: 1 })]

        mockUseSurrogateHistory.mockReturnValue({
            data: [makeHistory({ id: 'h1', to_stage_id: 's1' })],
        })

        const tasks = [
            makeTask({ id: 't1', title: 'Overdue task', due_date: '2000-01-01' }),
            makeTask({ id: 't2', title: 'Upcoming task', due_date: '2099-01-01' }),
        ]

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s1"
                stages={stages}
                activities={[]}
                tasks={tasks}
            />
        )

        expect(screen.getByText('Next Steps')).toBeInTheDocument()
        expect(screen.getByText('Overdue')).toBeInTheDocument()
        expect(screen.getByText('Upcoming')).toBeInTheDocument()
        expect(screen.getByText('Overdue task')).toBeInTheDocument()
        expect(screen.getByText('Upcoming task')).toBeInTheDocument()
    })

    it('drops unmatched activities instead of showing Unknown Stage', () => {
        const stages = [makeStage({ id: 's1', label: 'New Unread', order: 1 })]

        mockUseSurrogateHistory.mockReturnValue({ data: [] })

        const activities = [
            makeActivity({
                id: 'a1',
                activity_type: 'note_added',
                details: { preview: 'Unmatched note' },
                created_at: '2024-02-02T00:00:00.000Z',
            }),
        ]

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s1"
                stages={stages}
                activities={activities}
                tasks={[]}
            />
        )

        expect(screen.queryByText('Unknown Stage')).not.toBeInTheDocument()
    })

    it('shows terminal status transitions as explicit from-to labels', () => {
        const stages = [
            makeStage({ id: 's1', label: 'New Unread', order: 1 }),
            makeStage({
                id: 's2',
                slug: 'disqualified',
                label: 'Disqualified',
                stage_type: 'terminal',
                order: 99,
            }),
        ]

        mockUseSurrogateHistory.mockReturnValue({
            data: [
                makeHistory({
                    id: 'h1',
                    to_stage_id: 's1',
                    to_label_snapshot: 'New Unread',
                    changed_at: '2024-01-01T00:00:00.000Z',
                    effective_at: '2024-01-01T00:00:00.000Z',
                    recorded_at: '2024-01-01T00:00:00.000Z',
                }),
                makeHistory({
                    id: 'h2',
                    from_stage_id: 's1',
                    to_stage_id: 's2',
                    from_label_snapshot: 'New Unread',
                    to_label_snapshot: 'Disqualified',
                    changed_at: '2024-02-01T00:00:00.000Z',
                    effective_at: '2024-02-01T00:00:00.000Z',
                    recorded_at: '2024-02-01T00:00:00.000Z',
                }),
            ],
        })

        render(
            <ActivityTimeline
                surrogateId="surr1"
                currentStageId="s2"
                stages={stages}
                activities={[]}
                tasks={[]}
            />
        )

        expect(screen.getByText('Disqualified')).toBeInTheDocument()
        expect(screen.getByText('New Unread -> Disqualified')).toBeInTheDocument()
    })
})
