import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
    appointmentKeys,
    bookingKeys,
    useCancelByManageToken,
    useCreateBooking,
    useRescheduleByManageToken,
} from '@/lib/hooks/use-appointments'
import { complianceKeys, useExecutePurge } from '@/lib/hooks/use-compliance'
import { useDeleteEmailTemplate, useSendEmail } from '@/lib/hooks/use-email-templates'
import {
    formKeys,
    useApproveFormSubmission,
    usePromoteIntakeLead,
    useRejectFormSubmission,
    useResolveSubmissionMatch,
    useRetrySubmissionMatch,
    useRotateFormIntakeLink,
    useSendFormIntakeLink,
    useUpdateSubmissionAnswers,
} from '@/lib/hooks/use-forms'
import { useDisconnectMetaConnection } from '@/lib/hooks/use-meta-oauth'
import { metaFormsKeys } from '@/lib/hooks/use-meta-forms'
import { useCreateBulkTasks } from '@/lib/hooks/use-schedule-parser'
import { surrogateKeys } from '@/lib/hooks/use-surrogates'
import { taskKeys } from '@/lib/hooks/use-tasks'
import { useCreateZoomMeeting, useSendZoomInvite, useSyncGoogleCalendarNow } from '@/lib/hooks/use-user-integrations'
import { useDeleteWorkflow, useDuplicateWorkflow, useToggleWorkflow, useUpdateWorkflow } from '@/lib/hooks/use-workflows'
import { useZapierOutboundTest, useZapierTestLead, zapierKeys } from '@/lib/hooks/use-zapier'

type MutationOptions = {
    onSuccess?: (data: unknown, variables: unknown) => void
}

describe('mutation invalidation contracts', () => {
    let capturedOptions: MutationOptions | null = null
    const invalidateQueries = vi.fn()
    const removeQueries = vi.fn()
    const setQueryData = vi.fn()

    beforeEach(() => {
        capturedOptions = null
        invalidateQueries.mockReset()
        removeQueries.mockReset()
        setQueryData.mockReset()

        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
            removeQueries,
            setQueryData,
        } as unknown as ReturnType<typeof useQueryClient>)

        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedOptions = options as MutationOptions
            return {
                mutate: vi.fn(),
                mutateAsync: vi.fn(),
                isPending: false,
            } as unknown as ReturnType<typeof useMutation>
        })
    })

    it('refreshes public booking slots and appointment lists after a new booking', () => {
        useCreateBooking()

        capturedOptions?.onSuccess?.(
            {},
            {
                publicSlug: 'ewi-booking',
                data: {
                    appointment_type_id: 'type-1',
                    scheduled_start: '2026-06-02T15:00:00.000Z',
                },
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: bookingKeys.page('ewi-booking'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: [
                ...bookingKeys.all,
                'slots',
            ],
            exact: false,
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: appointmentKeys.lists(),
        })
    })

    it('refreshes the manage appointment cache after self-service reschedule', () => {
        useRescheduleByManageToken()

        capturedOptions?.onSuccess?.(
            {},
            {
                orgId: 'org-1',
                token: 'manage-token',
                scheduledStart: '2026-06-02T15:00:00.000Z',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: bookingKeys.manage('org-1', 'manage-token'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: appointmentKeys.lists(),
        })
    })

    it('refreshes the manage appointment cache after self-service cancellation', () => {
        useCancelByManageToken()

        capturedOptions?.onSuccess?.(
            {},
            {
                orgId: 'org-1',
                token: 'manage-token',
                reason: 'No longer available',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: bookingKeys.manage('org-1', 'manage-token'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: appointmentKeys.lists(),
        })
    })

    it('refreshes compliance lists after executing a purge job', () => {
        useExecutePurge()

        capturedOptions?.onSuccess?.({ job_id: 'job-1' }, {})

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: complianceKeys.purgePreview(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: complianceKeys.policies(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: complianceKeys.holds(),
        })
    })

    it('refreshes surrogate CRM surfaces after sending an email to a surrogate', () => {
        useSendEmail()

        capturedOptions?.onSuccess?.(
            {},
            {
                surrogate_id: 'surrogate-1',
                template_id: 'template-1',
                recipient_email: 'lead@example.com',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['analytics', 'activity-feed'],
            exact: false,
        })
    })

    it('removes deleted email template detail cache after deletion', () => {
        useDeleteEmailTemplate()

        capturedOptions?.onSuccess?.({}, 'template-1')

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['email-templates', 'list'],
        })
        expect(removeQueries).toHaveBeenCalledWith({
            queryKey: ['email-templates', 'detail', 'template-1'],
        })
    })

    it('refreshes surrogate CRM surfaces after sending a shared intake link', () => {
        useSendFormIntakeLink()

        capturedOptions?.onSuccess?.(
            {},
            {
                formId: 'form-1',
                linkId: 'link-1',
                surrogateId: 'surrogate-1',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['analytics', 'activity-feed'],
            exact: false,
        })
    })

    it('refreshes embed health after rotating an intake link token', () => {
        useRotateFormIntakeLink()

        capturedOptions?.onSuccess?.(
            {},
            {
                formId: 'form-1',
                linkId: 'link-1',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.intakeLinks('form-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.embedHealth('link-1'),
        })
    })

    it('refreshes workflow list, detail, and stats caches after workflow mutations', () => {
        useUpdateWorkflow()
        capturedOptions?.onSuccess?.(
            { id: 'workflow-1', name: 'Updated workflow' },
            { id: 'workflow-1', data: { name: 'Updated workflow' } }
        )

        useToggleWorkflow()
        capturedOptions?.onSuccess?.({ id: 'workflow-1', enabled: false }, 'workflow-1')

        useDuplicateWorkflow()
        capturedOptions?.onSuccess?.({ id: 'workflow-2', name: 'Copy' }, 'workflow-1')

        useDeleteWorkflow()
        capturedOptions?.onSuccess?.({}, 'workflow-1')

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['workflows', 'list'],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['workflows', 'detail', 'workflow-1'],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['workflows', 'stats'],
        })
        expect(setQueryData).toHaveBeenCalledWith(
            ['workflows', 'detail', 'workflow-2'],
            { id: 'workflow-2', name: 'Copy' }
        )
        expect(removeQueries).toHaveBeenCalledWith({
            queryKey: ['workflows', 'detail', 'workflow-1'],
        })
    })

    it('refreshes available Meta assets when disconnecting a Meta connection', () => {
        useDisconnectMetaConnection()

        capturedOptions?.onSuccess?.({}, 'connection-1')

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['meta-oauth', 'connections'],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['meta-oauth', 'available-assets', 'connection-1'],
        })
    })

    it('refreshes surrogate CRM surfaces after sending a Zoom invite', () => {
        useSendZoomInvite()

        capturedOptions?.onSuccess?.(
            {},
            {
                meeting_id: 'meeting-1',
                surrogate_id: 'surrogate-1',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['analytics', 'activity-feed'],
            exact: false,
        })
    })

    it('refreshes appointment and task caches after a manual Google sync', () => {
        useSyncGoogleCalendarNow()

        capturedOptions?.onSuccess?.(
            {
                connected: true,
                outbound_backfilled: 0,
                appointment_changes: 1,
                task_changes: 2,
                last_sync_at: '2026-05-10T06:00:00.000Z',
                warnings: [],
            },
            {}
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: appointmentKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: taskKeys.lists(),
        })
    })

    it('refreshes surrogate CRM surfaces after creating bulk AI tasks', () => {
        useCreateBulkTasks()

        capturedOptions?.onSuccess?.(
            {
                success: true,
                created: [{ task_id: 'task-1', title: 'Follow up' }],
                error: null,
            },
            {
                request_id: 'request-1',
                surrogate_id: 'surrogate-1',
                tasks: [],
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: taskKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.stats(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['analytics', 'activity-feed'],
            exact: false,
        })
    })

    it('refreshes meeting, task, note, and surrogate caches after creating a Zoom meeting', () => {
        useCreateZoomMeeting()

        capturedOptions?.onSuccess?.(
            {
                join_url: 'https://zoom.example/j/1',
                start_url: 'https://zoom.example/s/1',
                meeting_id: 1,
                password: null,
                note_id: 'note-1',
                task_id: 'task-1',
            },
            {
                entity_type: 'surrogate',
                entity_id: 'surrogate-1',
                topic: 'Consultation',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['user-integrations', 'zoom-meetings'],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['notes'],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: taskKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
    })

    it('refreshes lead and surrogate surfaces after sending a Zapier test lead', () => {
        useZapierTestLead()

        capturedOptions?.onSuccess?.(
            {
                status: 'created',
                duplicate: false,
                meta_lead_id: 'lead-1',
                surrogate_id: 'surrogate-1',
            },
            {}
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.stats(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.intelligentSummary(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: metaFormsKeys.all,
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
    })

    it('refreshes Zapier outbound event monitors after sending an outbound test', () => {
        useZapierOutboundTest()

        capturedOptions?.onSuccess?.({}, {})

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: [...zapierKeys.all, 'outbound-events'],
            exact: false,
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: [...zapierKeys.all, 'outbound-events-summary'],
            exact: false,
        })
    })

    it('refreshes form and surrogate caches after promoting an intake lead', () => {
        usePromoteIntakeLead()

        capturedOptions?.onSuccess?.(
            {
                intake_lead_id: 'lead-1',
                surrogate_id: 'surrogate-1',
                linked_submission_count: 2,
            },
            {
                leadId: 'lead-1',
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.intakeLead('lead-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.all,
            exact: false,
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
    })

    it('refreshes form submission lists and surrogate surfaces after reviewing a submission', () => {
        useApproveFormSubmission()

        capturedOptions?.onSuccess?.(
            {
                id: 'submission-1',
                form_id: 'form-1',
                surrogate_id: 'surrogate-1',
                intake_lead_id: 'lead-1',
            },
            {}
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.surrogateSubmission('form-1', 'surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.submissionLists('form-1'),
            exact: false,
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.intakeLead('lead-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
    })

    it('uses the same form submission invalidation contract for reject, match retry, and answer edits', () => {
        const submission = {
            id: 'submission-1',
            form_id: 'form-1',
            surrogate_id: 'surrogate-1',
            intake_lead_id: 'lead-1',
        }

        useRejectFormSubmission()
        capturedOptions?.onSuccess?.(submission, {})

        useResolveSubmissionMatch()
        capturedOptions?.onSuccess?.({ submission }, {})

        useRetrySubmissionMatch()
        capturedOptions?.onSuccess?.({ submission }, {})

        useUpdateSubmissionAnswers()
        capturedOptions?.onSuccess?.({ submission }, {})

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.submissionLists('form-1'),
            exact: false,
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: formKeys.submissionMatchCandidates('submission-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail('surrogate-1'),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity('surrogate-1'),
        })
    })
})
