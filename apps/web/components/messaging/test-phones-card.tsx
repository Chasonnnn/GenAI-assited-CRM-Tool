"use client"

import { useState, type FormEvent } from "react"
import { Loader2Icon } from "lucide-react"

import { maskedLast4 } from "@/components/messaging/send-test-message-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "@/components/ui/toast"
import { useCurrentMinuteTimestamp } from "@/components/ui/use-current-minute-timestamp"
import type { MessagingTestPhone } from "@/lib/api/twilio"
import { getErrorMessage } from "@/lib/error-utils"
import { formatDate } from "@/lib/formatters"
import {
    useAddMessagingTestPhone,
    useMessagingTestPhones,
    useRemoveMessagingTestPhone,
    useVerifyMessagingTestPhone,
} from "@/lib/hooks/use-messaging-templates"

function phoneStatus(phone: MessagingTestPhone, now: number | null): { label: string; className: string } {
    if (phone.stopped_purposes.length > 0) {
        return { label: "Replied STOP", className: "border-destructive/30 bg-destructive/10 text-destructive" }
    }
    if (phone.verified_at) {
        return {
            label: `Verified ${formatDate(phone.verified_at, { month: "short", day: "numeric" })}`,
            className: "border-success/30 bg-success/10 text-success",
        }
    }
    // Before the clock is known, a code with an expiry counts as sent.
    if (phone.code_expires_at && (now === null || Date.parse(phone.code_expires_at) > now)) {
        return { label: "Code sent", className: "border-warning/30 bg-warning/10 text-warning" }
    }
    return { label: "Code expired", className: "border-border bg-muted text-muted-foreground" }
}

function VerifyCell({ phone }: { phone: MessagingTestPhone }) {
    const [code, setCode] = useState("")
    const verify = useVerifyMessagingTestPhone()

    const submit = async (event: FormEvent) => {
        event.preventDefault()
        try {
            await verify.mutateAsync({ id: phone.id, code })
            toast.success(`${phone.label} verified`)
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not verify the phone."))
        }
    }


    return (
        <form onSubmit={(event) => void submit(event)} className="flex flex-wrap items-center gap-2">
            <Label htmlFor={`test-phone-code-${phone.id}`} className="sr-only">
                Verification code for {phone.label}
            </Label>
            <Input
                id={`test-phone-code-${phone.id}`}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="6-digit code"
                maxLength={6}
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                className="h-8 w-28"
            />
            <Button type="submit" size="sm" variant="outline" disabled={code.length !== 6 || verify.isPending}>
                Verify
            </Button>
        </form>
    )
}

export function TestPhonesCard() {
    const phonesQuery = useMessagingTestPhones()
    const addPhone = useAddMessagingTestPhone()
    const removePhone = useRemoveMessagingTestPhone()
    const [label, setLabel] = useState("")
    const [phone, setPhone] = useState("")
    const now = useCurrentMinuteTimestamp()

    const sendCode = async (event: FormEvent) => {
        event.preventDefault()
        try {
            await addPhone.mutateAsync({ label, phone })
            toast.success("Code sent")
            setLabel("")
            setPhone("")
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not send the code."))
        }
    }

    const remove = async (testPhone: MessagingTestPhone) => {
        try {
            await removePhone.mutateAsync(testPhone.id)
            toast.success(`${testPhone.label} removed`)
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not remove the phone."))
        }
    }

    return (
        <Card id="test-phones" role="region" aria-labelledby="test-phones-title" className="scroll-mt-6">
            <CardHeader>
                <CardTitle id="test-phones-title" className="text-lg">Test phones</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
                <form onSubmit={(event) => void sendCode(event)} className="flex flex-wrap items-end gap-3">
                    <div className="space-y-2">
                        <Label htmlFor="test-phone-label">Label</Label>
                        <Input
                            id="test-phone-label"
                            value={label}
                            maxLength={80}
                            onChange={(event) => setLabel(event.target.value)}
                            className="w-56"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="test-phone-number">Phone number</Label>
                        <Input
                            id="test-phone-number"
                            type="tel"
                            autoComplete="tel"
                            value={phone}
                            onChange={(event) => setPhone(event.target.value)}
                            className="w-48"
                        />
                    </div>
                    <Button type="submit" disabled={!label.trim() || !phone.trim() || addPhone.isPending}>
                        {addPhone.isPending ? (
                            <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        ) : null}
                        Send code
                    </Button>
                </form>

                {phonesQuery.isLoading ? (
                    <Skeleton className="h-24 w-full" />
                ) : phonesQuery.isError ? (
                    <p className="text-sm text-destructive">
                        {getErrorMessage(phonesQuery.error, "Test phones could not be loaded.")}
                    </p>
                ) : (phonesQuery.data ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">No test phones.</p>
                ) : (
                    <div className="overflow-x-auto rounded-lg border">
                        <Table aria-label="Test phones">
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Label</TableHead>
                                    <TableHead>Phone</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Added by</TableHead>
                                    <TableHead><span className="sr-only">Actions</span></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {(phonesQuery.data ?? []).map((testPhone) => {
                                    const status = phoneStatus(testPhone, now)
                                    const awaitingCode = !testPhone.verified_at && status.label === "Code sent"
                                    return (
                                        <TableRow key={testPhone.id}>
                                            <TableCell className="font-medium">{testPhone.label}</TableCell>
                                            <TableCell>{maskedLast4(testPhone.phone_last4)}</TableCell>
                                            <TableCell>
                                                <Badge variant="outline" className={status.className}>{status.label}</Badge>
                                            </TableCell>
                                            <TableCell>{testPhone.created_by_name ?? "—"}</TableCell>
                                            <TableCell>
                                                <div className="flex flex-wrap items-center justify-end gap-2">
                                                    {awaitingCode ? <VerifyCell phone={testPhone} /> : null}
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => void remove(testPhone)}
                                                        disabled={removePhone.isPending}
                                                    >
                                                        Remove
                                                    </Button>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    )
                                })}
                            </TableBody>
                        </Table>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
