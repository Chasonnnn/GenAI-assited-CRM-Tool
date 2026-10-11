"use client"

import { useState } from "react"
import { Loader2Icon } from "lucide-react"

import Link from "@/components/app-link"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "@/components/ui/toast"
import { getErrorMessage } from "@/lib/error-utils"
import { useMessagingTestPhones, useSendMessagingTemplateTest } from "@/lib/hooks/use-messaging-templates"
import { useTwilioSettings } from "@/lib/hooks/use-twilio"
import type { TestTemplateOption } from "@/lib/messaging/template-library"

export const TEST_PHONES_HREF = "/settings/integrations/messaging#test-phones"

export function maskedLast4(last4: string): string {
    return `•••-${last4}`
}

export function SendTestMessageDialog({
    open,
    onOpenChange,
    templates,
    defaultTemplateId,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    templates: TestTemplateOption[]
    defaultTemplateId?: string | null | undefined
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Send test message</DialogTitle>
                </DialogHeader>
                {open ? (
                    <SendTestMessageForm
                        templates={templates}
                        defaultTemplateId={defaultTemplateId ?? templates[0]?.id ?? null}
                        onDone={() => onOpenChange(false)}
                    />
                ) : null}
            </DialogContent>
        </Dialog>
    )
}

function SendTestMessageForm({
    templates,
    defaultTemplateId,
    onDone,
}: {
    templates: TestTemplateOption[]
    defaultTemplateId: string | null
    onDone: () => void
}) {
    const phonesQuery = useMessagingTestPhones()
    const settingsQuery = useTwilioSettings()
    const sendTest = useSendMessagingTemplateTest()
    const [templateId, setTemplateId] = useState<string | null>(defaultTemplateId)
    const template = templates.find((option) => option.id === templateId) ?? null
    const verifiedPhones = (phonesQuery.data ?? []).filter((phone) => phone.verified_at)
    const sendable = verifiedPhones.filter(
        (phone) => !template || !phone.stopped_purposes.includes(template.purpose),
    )
    const [phoneId, setPhoneId] = useState<string | null>(null)
    const selectedPhoneId = phoneId ?? sendable[0]?.id ?? null
    const sender = template ? settingsQuery.data?.routes[template.purpose]?.sender_phone_masked : null

    const send = async () => {
        if (!template || !selectedPhoneId) return
        const phone = verifiedPhones.find((candidate) => candidate.id === selectedPhoneId)
        try {
            await sendTest.mutateAsync({ templateId: template.id, testPhoneId: selectedPhoneId })
            toast.success(`Test message sent to ${phone?.label ?? "the test phone"}`)
            onDone()
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not send the test message."))
        }
    }

    return (
        <>
            <div className="space-y-5">
                <div className="space-y-2">
                    <Label htmlFor="test-message-template">Template</Label>
                    <Select
                        value={templateId}
                        onValueChange={(value) => {
                            setTemplateId(value)
                            setPhoneId(null)
                        }}
                    >
                        <SelectTrigger id="test-message-template" className="w-full">
                            <SelectValue>
                                {(value: string | null) =>
                                    templates.find((option) => option.id === value)?.label ?? "Select a template"
                                }
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {templates.map((option) => (
                                <SelectItem key={option.id} value={option.id}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <fieldset className="space-y-2">
                    <legend className="mb-2 text-sm font-medium">Send to</legend>
                    {phonesQuery.isLoading ? (
                        <p className="text-sm text-muted-foreground">Loading test phones</p>
                    ) : verifiedPhones.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No verified test phones.</p>
                    ) : (
                        <RadioGroup
                            aria-label="Send to"
                            value={selectedPhoneId}
                            onValueChange={(value) => setPhoneId(value)}
                            className="gap-2"
                        >
                            {verifiedPhones.map((phone) => {
                                const stopped = Boolean(
                                    template && phone.stopped_purposes.includes(template.purpose),
                                )
                                return (
                                    <Label
                                        key={phone.id}
                                        htmlFor={`test-phone-${phone.id}`}
                                        className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 font-normal has-[[data-disabled]]:cursor-not-allowed has-[[data-disabled]]:opacity-60"
                                    >
                                        <RadioGroupItem id={`test-phone-${phone.id}`} value={phone.id} disabled={stopped} />
                                        <span className="flex-1">{phone.label}</span>
                                        <span className="text-xs text-muted-foreground">
                                            {stopped ? "Replied STOP" : maskedLast4(phone.phone_last4)}
                                        </span>
                                    </Label>
                                )
                            })}
                        </RadioGroup>
                    )}
                    <Link href={TEST_PHONES_HREF} className="inline-block text-sm text-primary hover:underline">
                        Manage test phones
                    </Link>
                </fieldset>

                {template ? (
                    <p className="text-sm text-muted-foreground">
                        {sender ? `From ${sender} on the ${template.purpose} route.` : `Sends on the ${template.purpose} route.`}{" "}
                        Variables use sample values. Quiet hours do not apply.
                    </p>
                ) : null}
            </div>
            <DialogFooter>
                <Button type="button" variant="outline" onClick={onDone}>
                    Cancel
                </Button>
                <Button
                    type="button"
                    onClick={() => void send()}
                    disabled={!template || !selectedPhoneId || sendTest.isPending}
                >
                    {sendTest.isPending ? (
                        <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                    ) : null}
                    Send test
                </Button>
            </DialogFooter>
        </>
    )
}
