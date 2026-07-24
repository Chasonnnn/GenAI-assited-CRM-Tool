import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    confirmEmailReconciliationNotSent,
    confirmEmailReconciliationSent,
    dismissEmailReconciliationCase,
    getEmailOperationMessage,
    getEmailOperationsLiveReadiness,
    getEmailOperationsMessages,
    getEmailOperationsReadiness,
    getEmailReconciliationCases,
    linkEmailReconciliationEvent,
    requestEmailOperationsReadinessCheck,
    retryEmailReconciliationCorrelation,
} from "@/lib/api/email-operations"

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
    },
}))

describe("email operations API", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPost.mockReset()
        mockGet.mockResolvedValue({})
        mockPost.mockResolvedValue({})
    })

    it("uses the readiness and message endpoints with an encoded cursor", async () => {
        await getEmailOperationsReadiness()
        await getEmailOperationsMessages({ limit: 25, cursor: "cursor+with/slash=" })
        await getEmailOperationMessage("message/id")

        expect(mockGet).toHaveBeenNthCalledWith(1, "/email-operations/readiness")
        expect(mockGet).toHaveBeenNthCalledWith(
            2,
            "/email-operations/messages?limit=25&cursor=cursor%2Bwith%2Fslash%3D",
        )
        expect(mockGet).toHaveBeenNthCalledWith(
            3,
            "/email-operations/messages/message%2Fid",
        )
    })

    it("requests one read-only readiness check without a request payload", async () => {
        await requestEmailOperationsReadinessCheck()

        expect(mockPost).toHaveBeenCalledTimes(1)
        expect(mockPost).toHaveBeenCalledWith("/email-operations/readiness/check")
    })

    it("reads live readiness from its cache-only endpoint", async () => {
        await getEmailOperationsLiveReadiness()

        expect(mockGet).toHaveBeenCalledTimes(1)
        expect(mockGet).toHaveBeenCalledWith("/email-operations/readiness/live")
    })

    it("lists action-required reconciliation cases with an encoded cursor and retries by version", async () => {
        await getEmailReconciliationCases({
            status: "action_required",
            limit: 25,
            cursor: "case+cursor/slash=",
        })
        await retryEmailReconciliationCorrelation({
            caseId: "case/id",
            expectedVersion: 7,
        })

        expect(mockGet).toHaveBeenCalledWith(
            "/email-operations/reconciliation-cases?limit=25&status=action_required&cursor=case%2Bcursor%2Fslash%3D",
        )
        expect(mockPost).toHaveBeenCalledWith(
            "/email-operations/reconciliation-cases/case%2Fid/retry-correlation",
            { expected_version: 7 },
        )
    })

    it("dismisses a reconciliation case with a controlled reason and version fence", async () => {
        await dismissEmailReconciliationCase({
            caseId: "case/dismiss",
            expectedVersion: 3,
            resolutionCode: "unsupported_event",
        })

        expect(mockPost).toHaveBeenCalledWith(
            "/email-operations/reconciliation-cases/case%2Fdismiss/dismiss",
            {
                expected_version: 3,
                resolution_code: "unsupported_event",
            },
        )
    })

    it("links an orphan event to an existing message with a version fence", async () => {
        await linkEmailReconciliationEvent({
            caseId: "case/link",
            expectedVersion: 6,
            emailLogId: "b225811e-3875-4ec9-998a-e201e5c47b79",
        })

        expect(mockPost).toHaveBeenCalledWith(
            "/email-operations/reconciliation-cases/case%2Flink/link-event",
            {
                expected_version: 6,
                email_log_id: "b225811e-3875-4ec9-998a-e201e5c47b79",
            },
        )
    })

    it("confirms a delivery was sent with required provider evidence and a version fence", async () => {
        await confirmEmailReconciliationSent({
            caseId: "case/sent",
            expectedVersion: 8,
            providerMessageId: "provider-message-123",
        })

        expect(mockPost).toHaveBeenCalledWith(
            "/email-operations/reconciliation-cases/case%2Fsent/resolve-delivery",
            {
                expected_version: 8,
                outcome: "confirm_sent",
                provider_message_id: "provider-message-123",
            },
        )
    })

    it("confirms a delivery was not sent without accepting provider evidence", async () => {
        await confirmEmailReconciliationNotSent({
            caseId: "case/not-sent",
            expectedVersion: 9,
        })

        expect(mockPost).toHaveBeenCalledWith(
            "/email-operations/reconciliation-cases/case%2Fnot-sent/resolve-delivery",
            {
                expected_version: 9,
                outcome: "confirm_not_sent",
            },
        )
    })
})
