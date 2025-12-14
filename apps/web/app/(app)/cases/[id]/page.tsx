"use client"

import * as React from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    PlusIcon,
    MoreVerticalIcon,
    CopyIcon,
    CheckIcon,
    XIcon,
    TrashIcon,
} from "lucide-react"

// TODO: This will be fetched from API based on case ID
const mockCaseData = {
    id: "00042",
    status: "contacted",
    fullName: "Sarah Johnson",
    email: "sarah.johnson@email.com",
    phone: "(555) 123-4567",
    state: "CA",
    source: "Meta",
    createdAt: "Dec 10, 2024",
    dateOfBirth: "1992-03-15",
    age: 32,
    race: "Caucasian",
    eligibility: {
        ageEligible: true,
        usCitizen: true,
        hasChild: true,
        nonSmoker: true,
        priorExperience: false,
        height: "5'6\"",
        weight: "145 lb",
        deliveries: 2,
        cSections: 0,
    },
}

export default function CaseDetailPage({ params }: { params: { id: string } }) {
    const [copiedEmail, setCopiedEmail] = React.useState(false)
    const caseData = mockCaseData // TODO: Replace with useCase(params.id) hook

    const copyEmail = () => {
        navigator.clipboard.writeText(caseData.email)
        setCopiedEmail(true)
        setTimeout(() => setCopiedEmail(false), 2000)
    }

    return (
        <div className="flex flex-1 flex-col">
            {/* Case Header */}
            <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
                <div className="flex items-center gap-2">
                    <h1 className="text-lg font-semibold">Case #{caseData.id}</h1>
                    <Badge className="bg-teal-500 hover:bg-teal-500/80">Contacted</Badge>
                </div>
                <div className="flex items-center gap-2">
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm">
                                Change Status
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem>New</DropdownMenuItem>
                            <DropdownMenuItem>Contacted</DropdownMenuItem>
                            <DropdownMenuItem>Qualified</DropdownMenuItem>
                            <DropdownMenuItem>In Process</DropdownMenuItem>
                            <DropdownMenuItem>Matched</DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                    <Button variant="outline" size="sm">
                        Assign
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                                <MoreVerticalIcon className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem>Edit</DropdownMenuItem>
                            <DropdownMenuItem>Archive</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </header>

            {/* Tabs Content */}
            <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
                <Tabs defaultValue="overview" className="w-full">
                    <TabsList className="mb-4 overflow-x-auto">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="notes">Notes</TabsTrigger>
                        <TabsTrigger value="tasks">Tasks</TabsTrigger>
                        <TabsTrigger value="history">History</TabsTrigger>
                    </TabsList>

                    {/* OVERVIEW TAB */}
                    <TabsContent value="overview" className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-[1.5fr_1fr]">
                            <div className="space-y-4">
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Contact Information</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <div>
                                            <div className="text-2xl font-semibold">{caseData.fullName}</div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Email:</span>
                                            <span className="text-sm">{caseData.email}</span>
                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={copyEmail}>
                                                {copiedEmail ? <CheckIcon className="h-3 w-3" /> : <CopyIcon className="h-3 w-3" />}
                                            </Button>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Phone:</span>
                                            <span className="text-sm">{caseData.phone}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">State:</span>
                                            <span className="text-sm">{caseData.state}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Source:</span>
                                            <Badge variant="secondary">{caseData.source}</Badge>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Created:</span>
                                            <span className="text-sm">{caseData.createdAt}</span>
                                        </div>
                                    </CardContent>
                                </Card>

                                <Card>
                                    <CardHeader>
                                        <CardTitle>Demographics</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Date of Birth:</span>
                                            <span className="text-sm">{caseData.dateOfBirth}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Age:</span>
                                            <span className="text-sm">{caseData.age}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Race:</span>
                                            <span className="text-sm">{caseData.race}</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>

                            <div>
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Eligibility Checklist</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            {caseData.eligibility.ageEligible ? (
                                                <CheckIcon className="h-4 w-4 text-green-500" />
                                            ) : (
                                                <XIcon className="h-4 w-4 text-red-500" />
                                            )}
                                            <span className="text-sm">Age Eligible (18-42)</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {caseData.eligibility.usCitizen ? (
                                                <CheckIcon className="h-4 w-4 text-green-500" />
                                            ) : (
                                                <XIcon className="h-4 w-4 text-red-500" />
                                            )}
                                            <span className="text-sm">US Citizen or PR</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {caseData.eligibility.hasChild ? (
                                                <CheckIcon className="h-4 w-4 text-green-500" />
                                            ) : (
                                                <XIcon className="h-4 w-4 text-red-500" />
                                            )}
                                            <span className="text-sm">Has Child</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {caseData.eligibility.nonSmoker ? (
                                                <CheckIcon className="h-4 w-4 text-green-500" />
                                            ) : (
                                                <XIcon className="h-4 w-4 text-red-500" />
                                            )}
                                            <span className="text-sm">Non-Smoker</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {caseData.eligibility.priorExperience ? (
                                                <CheckIcon className="h-4 w-4 text-green-500" />
                                            ) : (
                                                <XIcon className="h-4 w-4 text-red-500" />
                                            )}
                                            <span className="text-sm">Prior Surrogate Experience</span>
                                        </div>
                                        <div className="border-t pt-3 space-y-2">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">Height:</span>
                                                <span className="text-sm">{caseData.eligibility.height}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">Weight:</span>
                                                <span className="text-sm">{caseData.eligibility.weight}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">Deliveries:</span>
                                                <span className="text-sm">{caseData.eligibility.deliveries}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">C-Sections:</span>
                                                <span className="text-sm">{caseData.eligibility.cSections}</span>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>

                    {/* NOTES TAB */}
                    <TabsContent value="notes" className="space-y-4">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    <div className="flex gap-2">
                                        <Textarea placeholder="Add a note..." className="min-h-24" />
                                        <Button>Submit</Button>
                                    </div>

                                    <div className="space-y-4 border-t pt-4">
                                        <div className="flex gap-3 group">
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback>JM</AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium">John Manager</span>
                                                        <span className="text-xs text-muted-foreground">2 hours ago</span>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                                                        <TrashIcon className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                                <p className="text-sm text-muted-foreground">
                                                    Initial phone screening completed. Candidate is enthusiastic and meets all basic
                                                    requirements. Scheduled follow-up for next week.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex gap-3 group">
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback>SK</AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium">Sarah Kim</span>
                                                        <span className="text-xs text-muted-foreground">1 day ago</span>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                                                        <TrashIcon className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                                <p className="text-sm text-muted-foreground">
                                                    Sent initial questionnaire via email. Awaiting response.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex gap-3 group">
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback>JM</AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium">John Manager</span>
                                                        <span className="text-xs text-muted-foreground">2 days ago</span>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                                                        <TrashIcon className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                                <p className="text-sm text-muted-foreground">
                                                    First contact made. Left voicemail with callback information.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex gap-3 group">
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback>MR</AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium">Maria Rodriguez</span>
                                                        <span className="text-xs text-muted-foreground">3 days ago</span>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                                                        <TrashIcon className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                                <p className="text-sm text-muted-foreground">
                                                    New lead from Meta campaign. Profile looks promising.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* TASKS TAB */}
                    <TabsContent value="tasks" className="space-y-4">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle>Tasks for Case #{caseData.id}</CardTitle>
                                <Button size="sm">
                                    <PlusIcon className="h-4 w-4 mr-2" />
                                    Add Task
                                </Button>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-start gap-3">
                                    <Checkbox id="case-task-1" className="mt-1" />
                                    <div className="flex-1 space-y-1">
                                        <label
                                            htmlFor="case-task-1"
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                        >
                                            Follow up with Case #{caseData.id}
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="destructive" className="text-xs">
                                                Overdue
                                            </Badge>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-start gap-3">
                                    <Checkbox id="case-task-2" className="mt-1" />
                                    <div className="flex-1 space-y-1">
                                        <label
                                            htmlFor="case-task-2"
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                        >
                                            Schedule medical consultation
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-amber-500 text-xs hover:bg-amber-500/80">
                                                Today
                                            </Badge>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-start gap-3">
                                    <Checkbox id="case-task-3" className="mt-1" />
                                    <div className="flex-1 space-y-1">
                                        <label
                                            htmlFor="case-task-3"
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                        >
                                            Review medical history documents
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="secondary" className="text-xs">
                                                Tomorrow
                                            </Badge>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-start gap-3">
                                    <Checkbox id="case-task-4" className="mt-1" />
                                    <div className="flex-1 space-y-1">
                                        <label
                                            htmlFor="case-task-4"
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                        >
                                            Prepare initial contract
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="secondary" className="text-xs">
                                                Next Week
                                            </Badge>
                                        </div>
                                    </div>
                                </div>

                                <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground">
                                    Show completed (2)
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* HISTORY TAB */}
                    <TabsContent value="history" className="space-y-4">
                        <Card>
                            <CardHeader>
                                <CardTitle>Status History</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex gap-3">
                                    <div className="relative">
                                        <div className="h-2 w-2 rounded-full bg-teal-500 mt-1.5"></div>
                                        <div className="absolute left-1 top-4 h-full w-px bg-border"></div>
                                    </div>
                                    <div className="flex-1 space-y-1 pb-4">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="secondary" className="text-xs">
                                                New
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">→</span>
                                            <Badge className="bg-teal-500 hover:bg-teal-500/80 text-xs">Contacted</Badge>
                                        </div>
                                        <div className="text-xs text-muted-foreground">Changed by John Manager • 2 hours ago</div>
                                        <p className="text-sm pt-1">Reason: Initial contact made via phone</p>
                                    </div>
                                </div>

                                <div className="flex gap-3">
                                    <div className="relative">
                                        <div className="h-2 w-2 rounded-full bg-blue-500 mt-1.5"></div>
                                        <div className="absolute left-1 top-4 h-full w-px bg-border"></div>
                                    </div>
                                    <div className="flex-1 space-y-1 pb-4">
                                        <div className="text-sm font-medium">Task completed</div>
                                        <div className="text-xs text-muted-foreground">By Sarah Kim • 1 day ago</div>
                                        <p className="text-sm pt-1">Sent initial questionnaire</p>
                                    </div>
                                </div>

                                <div className="flex gap-3">
                                    <div className="relative">
                                        <div className="h-2 w-2 rounded-full bg-purple-500 mt-1.5"></div>
                                        <div className="absolute left-1 top-4 h-full w-px bg-border"></div>
                                    </div>
                                    <div className="flex-1 space-y-1 pb-4">
                                        <div className="text-sm font-medium">Note added</div>
                                        <div className="text-xs text-muted-foreground">By John Manager • 2 days ago</div>
                                        <p className="text-sm pt-1">First contact made. Left voicemail.</p>
                                    </div>
                                </div>

                                <div className="flex gap-3">
                                    <div className="relative">
                                        <div className="h-2 w-2 rounded-full bg-green-500 mt-1.5"></div>
                                        <div className="absolute left-1 top-4 h-full w-px bg-border"></div>
                                    </div>
                                    <div className="flex-1 space-y-1 pb-4">
                                        <div className="text-sm font-medium">Case assigned</div>
                                        <div className="text-xs text-muted-foreground">By System • 3 days ago</div>
                                        <p className="text-sm pt-1">Assigned to John Manager</p>
                                    </div>
                                </div>

                                <div className="flex gap-3">
                                    <div className="relative">
                                        <div className="h-2 w-2 rounded-full bg-muted-foreground mt-1.5"></div>
                                    </div>
                                    <div className="flex-1 space-y-1">
                                        <div className="text-sm font-medium">Case created</div>
                                        <div className="text-xs text-muted-foreground">By Maria Rodriguez • 3 days ago</div>
                                        <p className="text-sm pt-1">New lead from Meta campaign</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}
