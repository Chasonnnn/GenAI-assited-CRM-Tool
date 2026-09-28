"use client"

import Link from "next/link"
import type { Route } from "next"
import { FileTextIcon } from "lucide-react"

import { EmptyState } from "@/components/empty-state"
import { LoadErrorState } from "@/components/error-state"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
    formatSubmissionDateTime,
    submissionStatusBadgeClass,
    submissionStatusLabel,
} from "@/lib/forms/submission-presentation"
import { useDonorSubmissions } from "@/lib/hooks/use-forms"

export function DonorApplicationsSection({
    donorId,
    canOpenSubmissions,
}: {
    donorId: string
    canOpenSubmissions: boolean
}) {
    const query = useDonorSubmissions(donorId)
    const submissions = query.data ?? []

    let content
    if (query.isLoading) {
        content = (
            <div className="space-y-2" role="status" aria-label="Loading applications">
                <Skeleton className="h-8" />
                <Skeleton className="h-8" />
            </div>
        )
    } else if (query.isError) {
        content = (
            <LoadErrorState
                title="Couldn't load applications"
                onRetry={() => void query.refetch()}
                isRetrying={query.isFetching}
            />
        )
    } else if (submissions.length === 0) {
        content = <EmptyState icon={FileTextIcon} title="No applications" />
    } else {
        content = (
            <Table aria-label="Donor applications">
                <TableHeader>
                    <TableRow>
                        <TableHead>Submitted</TableHead>
                        <TableHead>Form</TableHead>
                        <TableHead>Status</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {submissions.map((submission) => (
                        <TableRow key={submission.id}>
                            <TableCell>{formatSubmissionDateTime(submission.submitted_at)}</TableCell>
                            <TableCell>
                                {canOpenSubmissions ? (
                                    <Link
                                        href={`/automation/form-submissions?form=${encodeURIComponent(submission.form_id)}` as Route}
                                        className="text-primary hover:underline"
                                    >
                                        {submission.form_name}
                                    </Link>
                                ) : (
                                    submission.form_name
                                )}
                            </TableCell>
                            <TableCell>
                                <Badge variant="outline" className={submissionStatusBadgeClass(submission.status)}>
                                    {submissionStatusLabel(submission.status)}
                                </Badge>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>
                    <h2>Applications</h2>
                </CardTitle>
            </CardHeader>
            <CardContent>{content}</CardContent>
        </Card>
    )
}
