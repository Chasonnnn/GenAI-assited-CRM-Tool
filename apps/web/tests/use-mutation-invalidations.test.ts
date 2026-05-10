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
import { useSendEmail } from '@/lib/hooks/use-email-templates'
import {
    formKeys,
    useApproveFormSubmission,
    usePromoteIntakeLead,
    useRejectFormSubmission,
    useResolveSubmissionMatch,
    useRetrySubmissionMatch,
    useSendFormIntakeLink,
    useUpdateSubmissionAnswers,
} from '@/lib/hooks/use-forms'
import { metaFormsKeys } from '@/lib/hooks/use-meta-forms'
import { surrogateKeys } from '@/lib/hooks/use-surrogates'
import { useSendZoomInvite } from '@/lib/hooks/use-user-integrations'
import { useZapierOutboundTest, useZapierTestLead, zapierKeys } from '@/lib/hooks/use-zapier'

type MutationOptions = {
    onSuccess?: (data: unknown, variables: unknown) => void
}

describe('mutation invalidation contracts', () => {
    let capturedOptions: MutationOptions | null = null
    const invalidateQueries = vi.fn()

    beforeEach(() => {
        capturedOptions = null
        invalidateQueries.mockReset()

        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
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
