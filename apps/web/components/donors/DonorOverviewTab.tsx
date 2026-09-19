"use client"

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TabsContent } from "@/components/ui/tabs"
import { InlineEditField } from "@/components/inline-edit-field"
import { InlineDateField } from "@/components/inline-date-field"
import { CombinedMedicalInsuranceCard } from "@/components/surrogates/CombinedMedicalInsuranceCard"
import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import {
    CalendarDaysIcon,
    ChevronDownIcon,
    CopyIcon,
    InfoIcon,
    CheckIcon,
    PencilIcon,
    PlusIcon,
    RulerIcon,
    ScaleIcon,
    Trash2Icon,
    UserIcon,
    UsersIcon,
    WeightIcon,
} from "lucide-react"
import { computeBmi, formatDate } from "@/components/surrogates/detail/surrogate-detail-utils"
import { getMaritalStatusOptions } from "@/lib/intended-parent-marital-status"
import type { Donor, DonorUpdate } from "@/lib/types/donor"
import type { DonorProfile } from "@/lib/types/donor-profile"
import { useDonorProfile, useRevealDonorSensitiveInfo, useUpdateDonor } from "@/lib/hooks/use-donors"
import { toast } from "@/components/ui/toast"
import { RecordEditingContext } from "@/components/records/RecordEditingContext"
import { PersonalInfoRow, InlineSelectField, ProfileMetric, InlineHeightField, InlineRaceField, InlineWeightField, PersonalInfoColumn, SectionActionIcon, getAgeLabel, SsnField } from "@/components/records/RecordProfileFields"
import { DonorEligibilityChecklist } from "@/components/donors/DonorEligibilityChecklist"

export function DonorOverviewTab({ donor, canEdit, activityPanel }: {
    donor: Donor
    canEdit: boolean
    activityPanel: React.ReactNode
}) {
    const query = useDonorProfile(donor.id)
    return <TabsContent value="overview" className="space-y-4">
        {query.isPending ? <p role="status" className="text-sm text-muted-foreground">Loading donor information…</p>
            : query.isError ? <div role="alert" className="space-y-3"><p>Unable to load donor information.</p><Button variant="outline" onClick={() => { void query.refetch() }}>Retry donor information</Button></div>
            : <RecordEditingContext value={canEdit && !donor.is_archived}>
                <DonorOverviewContent key={donor.id} donor={donor} profile={query.data} canEdit={canEdit && !donor.is_archived} activityPanel={activityPanel} />
            </RecordEditingContext>}
    </TabsContent>
}

function DonorOverviewContent({ donor, profile, canEdit, activityPanel }: {
    donor: Donor
    profile: DonorProfile
    canEdit: boolean
    activityPanel: React.ReactNode
}) {
    const id = donor.id
    const record = { ...donor, ...profile }
    const donorData = record
    const updateDonorMutation = useUpdateDonor()
    const revealSensitiveInfoMutation = useRevealDonorSensitiveInfo()
    const onUpdate = async (data: DonorUpdate) => {
        if (!canEdit) throw new Error("You cannot edit this donor")
        await updateDonorMutation.mutateAsync({ id, data })
    }
    const [copiedEmail, setCopiedEmail] = React.useState(false)
    const [revealedSsn, setRevealedSsn] = React.useState<string | null>(null)
    const [revealedPartnerSsn, setRevealedPartnerSsn] = React.useState<string | null>(null)
    const [donorPersonalSectionAdded, setDonorPersonalSectionAdded] = React.useState(false)
    const [donorPersonalSectionHidden, setDonorPersonalSectionHidden] = React.useState(false)
    const [partnerSectionAdded, setPartnerSectionAdded] = React.useState(false)
    const [partnerSectionHidden, setPartnerSectionHidden] = React.useState(false)
    const [isDeletingPersonalSection, setIsDeletingPersonalSection] = React.useState(false)
    const [personalSectionPendingDelete, setPersonalSectionPendingDelete] = React.useState<"donor" | "partner" | null>(null)

    const bmiValue = computeBmi(donorData.height_ft, donorData.weight_lb)
    const educationOptions = profile.eligibility_checklist.find(item => item.key === "education")?.options ?? []

    const maritalStatusOptions = getMaritalStatusOptions(donorData.marital_status)
    const hasDonorPersonalInfo = Boolean(
        donorData.donor_type ||
        donorData.education ||
        donorData.marital_status ||
        donorData.ssn_masked ||
        donorData.address_line1 ||
        donorData.address_line2 ||
        donorData.address_city ||
        donorData.address_state ||
        donorData.address_postal
    )
    const hasPartnerInfo = Boolean(
        donorData.partner_name ||
        donorData.partner_date_of_birth ||
        donorData.partner_email ||
        donorData.partner_phone ||
        donorData.partner_ssn_masked ||
        donorData.partner_address_line1 ||
        donorData.partner_address_line2 ||
        donorData.partner_city ||
        donorData.partner_state ||
        donorData.partner_postal
    )
    const showDonorPersonalInfo =
        (hasDonorPersonalInfo || donorPersonalSectionAdded) && !donorPersonalSectionHidden
    const showPartnerInfo = (hasPartnerInfo || partnerSectionAdded) && !partnerSectionHidden
    const hasAnyPersonalInfoSection = showDonorPersonalInfo || showPartnerInfo

    const copyEmail = async () => {
        try {
            await navigator.clipboard.writeText(donorData.email)
            setCopiedEmail(true)
            setTimeout(() => setCopiedEmail(false), 2000)
        } catch { toast.error("Unable to copy email") }
    }

    const updateProfile = async (data: DonorUpdate) => {
        await onUpdate(data)
    }

    const revealSensitiveInfo = async () => {
        try {
            const payload = await revealSensitiveInfoMutation.mutateAsync(id)
            setRevealedSsn(payload.ssn)
            setRevealedPartnerSsn(payload.partner_ssn)
            revealSensitiveInfoMutation.reset()
        } catch {
            toast.error("Unable to reveal sensitive information")
        }
    }

    const addDonorPersonalSection = () => {
        setDonorPersonalSectionHidden(false)
        setDonorPersonalSectionAdded(true)
    }

    const addPartnerSection = () => {
        setPartnerSectionHidden(false)
        setPartnerSectionAdded(true)
    }

    const deletePersonalSection = async () => {
        if (!personalSectionPendingDelete) return

        setIsDeletingPersonalSection(true)
        const finishDeleting = () => setIsDeletingPersonalSection(false)
        try {
            if (personalSectionPendingDelete === "donor") {
                await updateProfile({
                    education: "",
                    marital_status: null,
                    ssn: null,
                    address_line1: null,
                    address_line2: null,
                    address_city: null,
                    address_state: null,
                    address_postal: null,
                })
                setRevealedSsn(null)
                setDonorPersonalSectionAdded(false)
                setDonorPersonalSectionHidden(true)
            } else {
                await updateProfile({
                    partner_name: null,
                    partner_date_of_birth: null,
                    partner_email: null,
                    partner_phone: null,
                    partner_ssn: null,
                    partner_address_line1: null,
                    partner_address_line2: null,
                    partner_city: null,
                    partner_state: null,
                    partner_postal: null,
                })
                setRevealedPartnerSsn(null)
                setPartnerSectionAdded(false)
                setPartnerSectionHidden(true)
            }
            setPersonalSectionPendingDelete(null)
            finishDeleting()
        } catch {
            toast.error("Unable to delete personal information")
            finishDeleting()
        }
    }

    return (
        <>
            <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                <div className="space-y-4">
                    <SurrogateOverviewCard title="Contact Information" icon={UserIcon}>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Name:</span>
                            <InlineEditField
                                value={donorData.full_name}
                                onSave={async (value) => {
                                    await onUpdate({ full_name: value })
                                }}
                                placeholder="Enter name"
                                className="text-base font-medium"
                                label="Full name"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Email:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={donorData.email}
                                    onSave={async (value) => {
                                        await onUpdate({ email: value })
                                    }}
                                    type="email"
                                    placeholder="Enter email"
                                    validate={(value) => (!value.includes("@") ? "Invalid email" : null)}
                                    label="Email"
                                />
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="size-6"
                                onClick={copyEmail}
                                aria-label="Copy email"
                            >
                                {copiedEmail ? (
                                    <CheckIcon className="size-3" />
                                ) : (
                                    <CopyIcon className="size-3" />
                                )}
                            </Button>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Phone:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={donorData.phone ?? undefined}
                                    onSave={async (value) => {
                                        await onUpdate({ phone: value || null })
                                    }}
                                    type="tel"
                                    placeholder="-"
                                    label="Phone"
                                />
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">State:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={donorData.state ?? undefined}
                                    onSave={async (value) => {
                                        await onUpdate({ state: value || null })
                                    }}
                                    placeholder="-"
                                    validate={(value) =>
                                        value && value.length !== 2
                                            ? "Use 2-letter code (e.g., CA, TX)"
                                            : null
                                    }
                                    label="State"
                                />
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Source:</span>
                            <Badge variant="secondary" className="capitalize">
                                {donorData.source}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Created:</span>
                            <span className="text-sm">{formatDate(donorData.created_at)}</span>
                        </div>
                    </SurrogateOverviewCard>

                    <SurrogateOverviewCard title="Demographics" icon={InfoIcon}>
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
                            <ProfileMetric
                                icon={CalendarDaysIcon}
                                label="Date of Birth"
                                primary={
                                    <InlineDateField
                                        value={donorData.date_of_birth}
                                        onSave={async (value) => {
                                            await onUpdate({ date_of_birth: value })
                                        }}
                                        placeholder="-"
                                        label="Date of Birth"
                                    />
                                }
                                secondary={getAgeLabel(donorData.date_of_birth)}
                            />
                            <ProfileMetric
                                icon={UsersIcon}
                                label="Race / Ethnicity"
                                primary={
                                    <InlineRaceField
                                        value={donorData.race ?? undefined}
                                        onSave={async (value) => {
                                            await onUpdate({ race: value || null })
                                        }}
                                    />
                                }
                            />
                            <ProfileMetric
                                icon={RulerIcon}
                                label="Height"
                                primary={
                                    <InlineHeightField
                                        value={donorData.height_ft}
                                        onSave={async (value) => {
                                            await onUpdate({ height_ft: value })
                                        }}
                                    />
                                }
                            />
                            <ProfileMetric
                                icon={WeightIcon}
                                label="Weight"
                                primary={
                                    <InlineWeightField
                                        value={donorData.weight_lb}
                                        onSave={async (value) => {
                                            await onUpdate({ weight_lb: value })
                                        }}
                                    />
                                }
                            />
                            <ProfileMetric
                                icon={ScaleIcon}
                                label="BMI"
                                primary={bmiValue ?? "-"}
                            />
                        </div>
                    </SurrogateOverviewCard>

                    <>
                            <SurrogateOverviewCard
                                title="Personal Information"
                                icon={UserIcon}
                                action={canEdit && (
                                    <DropdownMenu>
                                        <DropdownMenuTrigger
                                            render={
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    aria-label="Edit Personal Information"
                                                    className="group h-8 rounded-full border-border/70 bg-background/90 px-3.5 text-xs font-medium shadow-none transition-colors hover:bg-accent/70 data-[state=open]:bg-accent data-[state=open]:text-accent-foreground"
                                                />
                                            }
                                        >
                                            <PencilIcon className="size-3.5 text-muted-foreground transition-colors group-data-[state=open]:text-current" />
                                            Edit Info
                                            <ChevronDownIcon className="ml-0.5 size-3.5 text-muted-foreground transition-[color,transform] group-data-[state=open]:translate-y-px group-data-[state=open]:text-current" />
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent
                                            align="end"
                                            sideOffset={8}
                                            className="w-56 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                                        >
                                            {(!showDonorPersonalInfo || !showPartnerInfo) && (
                                                <DropdownMenuGroup>
                                                    <DropdownMenuSub>
                                                        <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium">
                                                            <SectionActionIcon icon={<PlusIcon className="size-4" />} />
                                                            Add Section
                                                        </DropdownMenuSubTrigger>
                                                        <DropdownMenuSubContent className="w-52 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90">
                                                            {!showDonorPersonalInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={addDonorPersonalSection}
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UserIcon className="size-4" />} />
                                                                    <span className="font-medium">Donor</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                            {!showPartnerInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={addPartnerSection}
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UsersIcon className="size-4" />} />
                                                                    <span className="font-medium">Partner</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                        </DropdownMenuSubContent>
                                                    </DropdownMenuSub>
                                                </DropdownMenuGroup>
                                            )}
                                            {hasAnyPersonalInfoSection && (
                                                <DropdownMenuGroup>
                                                    <DropdownMenuSub>
                                                        <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium text-destructive data-open:bg-destructive/10 data-open:text-destructive focus:bg-destructive/10 focus:text-destructive">
                                                            <SectionActionIcon icon={<Trash2Icon className="size-4" />} tone="destructive" />
                                                            Delete Section
                                                        </DropdownMenuSubTrigger>
                                                        <DropdownMenuSubContent className="w-52 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90">
                                                            {showDonorPersonalInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={() => setPersonalSectionPendingDelete("donor")}
                                                                    variant="destructive"
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UserIcon className="size-4" />} tone="destructive" />
                                                                    <span className="font-medium">Delete Donor</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                            {showPartnerInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={() => setPersonalSectionPendingDelete("partner")}
                                                                    variant="destructive"
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UsersIcon className="size-4" />} tone="destructive" />
                                                                    <span className="font-medium">Delete Partner</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                        </DropdownMenuSubContent>
                                                    </DropdownMenuSub>
                                                </DropdownMenuGroup>
                                            )}
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                )}
                            >
                                {!hasAnyPersonalInfoSection ? (
                                    <p className="py-4 text-center text-sm text-muted-foreground">
                                        No personal information added yet.
                                    </p>
                                ) : (
                                    <div className="grid items-stretch gap-4 lg:grid-cols-2">
                                    {showDonorPersonalInfo && (
                                        <PersonalInfoColumn title="Donor" icon={UserIcon}>
                                        <PersonalInfoRow label="Donor Type">
                                            <span>{record.donor_type === "egg" ? "Egg Donor" : "Sperm Donor"}</span>
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Education">
                                            {educationOptions.length > 0 ? <InlineSelectField
                                                value={record.education}
                                                label="Education"
                                                options={educationOptions}
                                                placeholder="Not answered"
                                                onSave={async value=>onUpdate({education:value})}
                                                triggerClassName="w-full max-w-[15rem]"
                                            /> : <InlineEditField label="Education" value={record.education} placeholder="Not answered" onSave={value => onUpdate({ education: value || null })} />}
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Marital Status">
                                            <InlineSelectField
                                                label="Marital Status"
                                                value={donorData.marital_status}
                                                options={maritalStatusOptions}
                                                onSave={async (value) => {
                                                    await updateProfile({ marital_status: value })
                                                }}
                                                triggerClassName="w-full max-w-[15rem]"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="SSN">
                                            <SsnField
                                                label="donor SSN"
                                                maskedValue={donorData.ssn_masked}
                                                revealedValue={revealedSsn}
                                                isRevealPending={revealSensitiveInfoMutation.isPending}
                                                onReveal={revealSensitiveInfo}
                                                onSave={async (value) => {
                                                    await updateProfile({ ssn: value })
                                                    setRevealedSsn(null)
                                                }}
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Address Line 1">
                                            <InlineEditField
                                                value={donorData.address_line1}
                                                onSave={async (value) => updateProfile({ address_line1: value || null })}
                                                placeholder="-"
                                                label="Donor address line 1"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Address Line 2">
                                            <InlineEditField
                                                value={donorData.address_line2}
                                                onSave={async (value) => updateProfile({ address_line2: value || null })}
                                                placeholder="-"
                                                label="Donor address line 2"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="City">
                                            <InlineEditField
                                                value={donorData.address_city}
                                                onSave={async (value) => updateProfile({ address_city: value || null })}
                                                placeholder="-"
                                                label="Donor city"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="State">
                                            <InlineEditField
                                                value={donorData.address_state}
                                                onSave={async (value) => updateProfile({ address_state: value || null })}
                                                placeholder="-"
                                                validate={(value) =>
                                                    value && value.length !== 2
                                                        ? "Use 2-letter code (e.g., CA, TX)"
                                                        : null
                                                }
                                                label="Donor state"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Postal Code">
                                            <InlineEditField
                                                value={donorData.address_postal}
                                                onSave={async (value) => updateProfile({ address_postal: value || null })}
                                                placeholder="-"
                                                label="Donor postal code"
                                            />
                                        </PersonalInfoRow>
                                        </PersonalInfoColumn>
                                    )}

                                    {showPartnerInfo && (
                                        <PersonalInfoColumn title="Partner" icon={UsersIcon}>
                                            <PersonalInfoRow label="Full Name">
                                                <InlineEditField
                                                    value={donorData.partner_name}
                                                    onSave={async (value) => updateProfile({ partner_name: value || null })}
                                                    placeholder="-"
                                                    label="Partner full name"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="DOB">
                                                <InlineDateField
                                                    value={donorData.partner_date_of_birth}
                                                    onSave={async (value) => updateProfile({ partner_date_of_birth: value })}
                                                    placeholder="-"
                                                    label="Partner date of birth"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Email">
                                                <InlineEditField
                                                    value={donorData.partner_email}
                                                    onSave={async (value) => updateProfile({ partner_email: value || null })}
                                                    type="email"
                                                    placeholder="-"
                                                    validate={(value) => (value && !value.includes("@") ? "Invalid email" : null)}
                                                    label="Partner email"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Phone">
                                                <InlineEditField
                                                    value={donorData.partner_phone}
                                                    onSave={async (value) => updateProfile({ partner_phone: value || null })}
                                                    type="tel"
                                                    placeholder="-"
                                                    label="Partner phone"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="SSN">
                                                <SsnField
                                                    label="partner SSN"
                                                    maskedValue={donorData.partner_ssn_masked}
                                                    revealedValue={revealedPartnerSsn}
                                                    isRevealPending={revealSensitiveInfoMutation.isPending}
                                                    onReveal={revealSensitiveInfo}
                                                    onSave={async (value) => {
                                                        await updateProfile({ partner_ssn: value })
                                                        setRevealedPartnerSsn(null)
                                                    }}
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Address Line 1">
                                                <InlineEditField
                                                    value={donorData.partner_address_line1}
                                                    onSave={async (value) => updateProfile({ partner_address_line1: value || null })}
                                                    placeholder="-"
                                                    label="Partner address line 1"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Address Line 2">
                                                <InlineEditField
                                                    value={donorData.partner_address_line2}
                                                    onSave={async (value) => updateProfile({ partner_address_line2: value || null })}
                                                    placeholder="-"
                                                    label="Partner address line 2"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="City">
                                                <InlineEditField
                                                    value={donorData.partner_city}
                                                    onSave={async (value) => updateProfile({ partner_city: value || null })}
                                                    placeholder="-"
                                                    label="Partner city"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="State">
                                                <InlineEditField
                                                    value={donorData.partner_state}
                                                    onSave={async (value) => updateProfile({ partner_state: value || null })}
                                                    placeholder="-"
                                                    validate={(value) =>
                                                        value && value.length !== 2
                                                            ? "Use 2-letter code (e.g., CA, TX)"
                                                            : null
                                                    }
                                                    label="Partner state"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Postal Code">
                                                <InlineEditField
                                                    value={donorData.partner_postal}
                                                    onSave={async (value) => updateProfile({ partner_postal: value || null })}
                                                    placeholder="-"
                                                    label="Partner postal code"
                                                />
                                            </PersonalInfoRow>
                                        </PersonalInfoColumn>
                                    )}
                                    </div>
                                )}
                            </SurrogateOverviewCard>

                            <AlertDialog
                                open={personalSectionPendingDelete !== null}
                                onOpenChange={(open) => {
                                    if (!open && !isDeletingPersonalSection) {
                                        setPersonalSectionPendingDelete(null)
                                    }
                                }}
                            >
                                <AlertDialogContent>
                                    <AlertDialogHeader>
                                        <AlertDialogTitle>
                                            Delete {personalSectionPendingDelete === "donor" ? "Donor" : "Partner"} section?
                                        </AlertDialogTitle>
                                        <AlertDialogDescription>
                                            This removes the section from Personal Information and clears any saved details. You can add it back later.
                                        </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                        <AlertDialogCancel disabled={isDeletingPersonalSection}>Cancel</AlertDialogCancel>
                                        <AlertDialogAction
                                            variant="destructive"
                                            onClick={deletePersonalSection}
                                            disabled={isDeletingPersonalSection}
                                        >
                                            Delete Section
                                        </AlertDialogAction>
                                    </AlertDialogFooter>
                                </AlertDialogContent>
                            </AlertDialog>
                        </>

                    <CombinedMedicalInsuranceCard
                        surrogateData={donorData}
                        onUpdate={async (data) => {
                            await onUpdate(data)
                        }}
                    />
                </div>

                <div className="space-y-4">
                    {activityPanel}

                    <DonorEligibilityChecklist items={profile.eligibility_checklist} onUpdate={onUpdate} />
                </div>
            </div>
        </>
    )
}
