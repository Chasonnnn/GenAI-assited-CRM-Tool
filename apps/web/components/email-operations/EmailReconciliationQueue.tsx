"use client"

import { useState } from "react"
import { AlertCircleIcon, InboxIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/formatters"
import type {
    EmailOperationMessage,
    EmailReconciliationCasePage,
} from "@/lib/api/email-operations"
import {
    EmailReconciliationActionDialogs,
    type EmailReconciliationActionSelection,
} from "./EmailReconciliationActionDialogs"
import {
    getReconciliationCaseLabel,
    getReconciliationReasonLabel,
} from "./email-operation-labels"

interface EmailReconciliationQuery {
    data:
        | {
              pages: EmailReconciliationCasePage[]
          }
        | undefined
    isLoading: boolean
    isError: boolean
    isFetching: boolean
    hasNextPage: boolean
    isFetchingNextPage: boolean
    fetchNextPage: () => unknown
    refetch: () => unknown
}

export function EmailReconciliationQueue({
    query,
    messages,
}: {
    query: EmailReconciliationQuery
    messages: EmailOperationMessage[]
}) {
    const [selection, setSelection] =
        useState<EmailReconciliationActionSelection | null>(null)

    const cases = query.data?.pages.flatMap((page) => page.items) ?? []
    const actionRequiredCount =
        query.data?.pages[0]?.counts.action_required ?? cases.length

    return (
        <>
            <Card>
                <CardHeader className="border-b">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <CardTitle>
                                <h2>Reconciliation queue</h2>
                            </CardTitle>
                            <CardDescription className="mt-1">
                                Resolve provider events and unknown delivery outcomes
                                without sending email.
                            </CardDescription>
                        </div>
                        <Badge
                            variant={
                                actionRequiredCount > 0
                                    ? "destructive"
                                    : "secondary"
                            }
                        >
                            {actionRequiredCount} needs action
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    {query.isLoading && !query.data ? (
                        <div
                            className="space-y-3 p-6"
                            role="status"
                            aria-label="Loading reconciliation cases"
                        >
                            <span className="sr-only">
                                Loading reconciliation cases
                            </span>
                            <Skeleton className="h-10 w-full" />
                            <Skeleton className="h-10 w-full" />
                        </div>
                    ) : query.isError && !query.data ? (
                        <div className="p-6">
                            <Alert variant="destructive">
                                <AlertCircleIcon aria-hidden="true" />
                                <AlertTitle>
                                    Reconciliation queue couldn’t load
                                </AlertTitle>
                                <AlertDescription>
                                    <p>
                                        Operator cases are temporarily unavailable.
                                        Try again before taking action.
                                    </p>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="mt-3"
                                        onClick={() => void query.refetch()}
                                    >
                                        Try again
                                    </Button>
                                </AlertDescription>
                            </Alert>
                        </div>
                    ) : cases.length === 0 ? (
                        <Empty className="py-10">
                            <EmptyHeader>
                                <EmptyMedia variant="icon">
                                    <InboxIcon aria-hidden="true" />
                                </EmptyMedia>
                                <EmptyTitle>No cases need action</EmptyTitle>
                                <EmptyDescription>
                                    New provider events and delivery outcomes will
                                    appear here only when operator review is required.
                                </EmptyDescription>
                            </EmptyHeader>
                        </Empty>
                    ) : (
                        <>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Case</TableHead>
                                        <TableHead>Reason</TableHead>
                                        <TableHead>Detected</TableHead>
                                        <TableHead className="text-right">
                                            Actions
                                        </TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {cases.map((reconciliationCase) => (
                                        <TableRow key={reconciliationCase.id}>
                                            <TableCell className="font-medium">
                                                {getReconciliationCaseLabel(
                                                    reconciliationCase.case_type,
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                {getReconciliationReasonLabel(
                                                    reconciliationCase.reason_code,
                                                )}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {formatDateTime(
                                                    reconciliationCase.detected_at,
                                                    "Unknown",
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex flex-wrap justify-end gap-2">
                                                    {reconciliationCase.available_actions.includes(
                                                        "retry_correlation",
                                                    ) ? (
                                                        <Button
                                                            type="button"
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() =>
                                                                setSelection({
                                                                    action: "retry_correlation",
                                                                    reconciliationCase,
                                                                })
                                                            }
                                                        >
                                                            Retry correlation
                                                        </Button>
                                                    ) : null}
                                                    {reconciliationCase.available_actions.includes(
                                                        "link_event",
                                                    ) ? (
                                                        <Button
                                                            type="button"
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() =>
                                                                setSelection({
                                                                    action: "link_event",
                                                                    reconciliationCase,
                                                                })
                                                            }
                                                        >
                                                            Link to message
                                                        </Button>
                                                    ) : null}
                                                    {reconciliationCase.available_actions.includes(
                                                        "dismiss",
                                                    ) ? (
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() =>
                                                                setSelection({
                                                                    action: "dismiss",
                                                                    reconciliationCase,
                                                                })
                                                            }
                                                        >
                                                            Dismiss case
                                                        </Button>
                                                    ) : null}
                                                    {reconciliationCase.available_actions.includes(
                                                        "confirm_sent",
                                                    ) ? (
                                                        <Button
                                                            type="button"
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() =>
                                                                setSelection({
                                                                    action: "confirm_sent",
                                                                    reconciliationCase,
                                                                })
                                                            }
                                                        >
                                                            Confirm sent
                                                        </Button>
                                                    ) : null}
                                                    {reconciliationCase.available_actions.includes(
                                                        "confirm_not_sent",
                                                    ) ? (
                                                        <Button
                                                            type="button"
                                                            variant="destructive"
                                                            size="sm"
                                                            onClick={() =>
                                                                setSelection({
                                                                    action: "confirm_not_sent",
                                                                    reconciliationCase,
                                                                })
                                                            }
                                                        >
                                                            Confirm not sent
                                                        </Button>
                                                    ) : null}
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                            {query.hasNextPage ? (
                                <div className="flex justify-center border-t p-4">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() => void query.fetchNextPage()}
                                        disabled={query.isFetchingNextPage}
                                    >
                                        {query.isFetchingNextPage
                                            ? "Loading more..."
                                            : "Load more reconciliation cases"}
                                    </Button>
                                </div>
                            ) : null}
                        </>
                    )}
                </CardContent>
            </Card>
            {selection ? (
                <EmailReconciliationActionDialogs
                    key={`${selection.reconciliationCase.id}:${selection.action}`}
                    selection={selection}
                    messages={messages}
                    onClose={() => setSelection(null)}
                />
            ) : null}
        </>
    )
}
