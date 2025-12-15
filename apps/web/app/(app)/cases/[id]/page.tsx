"use client"

import * as React from "react"
import { useRouter, useParams } from "next/navigation"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { RichTextEditor } from "@/components/rich-text-editor"
import {
    PlusIcon,
    MoreVerticalIcon,
    CopyIcon,
    CheckIcon,
    XIcon,
    TrashIcon,
    LoaderIcon,
    ArrowLeftIcon,
} from "lucide-react"
import { useCase, useCaseHistory, useChangeStatus, useArchiveCase, useRestoreCase, useUpdateCase } from "@/lib/hooks/use-cases"
import { useNotes, useCreateNote, useDeleteNote } from "@/lib/hooks/use-notes"
import { useTasks, useCompleteTask, useUncompleteTask } from "@/lib/hooks/use-tasks"
import { STATUS_CONFIG, type CaseStatus } from "@/lib/types/case"
import type { NoteRead } from "@/lib/types/note"
import type { TaskListItem } from "@/lib/types/task"
import type { CaseStatusHistory } from "@/lib/api/cases"

// Format date for display
function formatDateTime(dateString: string): string {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })
}

function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    })
}

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

// Status options for dropdown - matches backend CaseStatus enum
// Note: 'approved' auto-transitions to 'pending_handoff' on backend
// Note: Stage-B statuses (pending_match+) blocked for intake on backend
const STATUS_OPTIONS: CaseStatus[] = [
    'new_unread',
    'contacted',
    'followup_scheduled',
    'application_submitted',
    'under_review',
    'approved',        // Backend auto-converts to pending_handoff
    'pending_handoff', // Visible but only changeable via Accept
    'disqualified',
    'pending_match',
    'meds_started',
    'exam_passed',
    'embryo_transferred',
    'delivered',
]

export default function CaseDetailPage() {
    const params = useParams()
    const id = params.id as string
    const router = useRouter()
    const [copiedEmail, setCopiedEmail] = React.useState(false)
    const [editDialogOpen, setEditDialogOpen] = React.useState(false)

    // Fetch data
    const { data: caseData, isLoading, error } = useCase(id)
    const { data: history } = useCaseHistory(id)
    const { data: notes } = useNotes(id)
    const { data: tasksData } = useTasks({ case_id: id })

    // Mutations
    const changeStatusMutation = useChangeStatus()
    const archiveMutation = useArchiveCase()
    const restoreMutation = useRestoreCase()
    const createNoteMutation = useCreateNote()
    const deleteNoteMutation = useDeleteNote()
    const completeTaskMutation = useCompleteTask()
    const uncompleteTaskMutation = useUncompleteTask()
    const updateCaseMutation = useUpdateCase()

    const copyEmail = () => {
        if (!caseData) return
        navigator.clipboard.writeText(caseData.email)
        setCopiedEmail(true)
        setTimeout(() => setCopiedEmail(false), 2000)
    }

    const handleStatusChange = async (newStatus: CaseStatus) => {
        if (!caseData) return
        await changeStatusMutation.mutateAsync({ caseId: id, data: { status: newStatus } })
    }

    const handleArchive = async () => {
        await archiveMutation.mutateAsync(id)
        router.push('/cases')
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(id)
    }

    const handleAddNote = async (html: string) => {
        if (!html || html === '<p></p>') return
        await createNoteMutation.mutateAsync({ caseId: id, body: html })
    }

    const handleDeleteNote = async (noteId: string) => {
        await deleteNoteMutation.mutateAsync({ noteId, caseId: id })
    }

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        if (isCompleted) {
            await uncompleteTaskMutation.mutateAsync(taskId)
        } else {
            await completeTaskMutation.mutateAsync(taskId)
        }
    }

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading case...</span>
            </div>
        )
    }

    if (error || !caseData) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Card className="p-6">
                    <p className="text-destructive">Error loading case: {error?.message || 'Not found'}</p>
                    <Button variant="outline" className="mt-4" onClick={() => router.push('/cases')}>
                        Back to Cases
                    </Button>
                </Card>
            </div>
        )
    }

    const statusConfig = STATUS_CONFIG[caseData.status] || { label: caseData.status, color: 'bg-gray-500' }

    return (
        <div className="flex flex-1 flex-col">
            {/* Case Header */}
            <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => router.push('/cases')}>
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back
                    </Button>
                    <h1 className="text-lg font-semibold">Case #{caseData.case_number}</h1>
                    <Badge className={`${statusConfig.color} text-white`}>{statusConfig.label}</Badge>
                    {caseData.is_archived && <Badge variant="secondary">Archived</Badge>}
                </div>
                <div className="flex items-center gap-2">
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            render={
                                <Button variant="outline" size="sm" disabled={caseData.is_archived}>
                                    Change Status
                                </Button>
                            }
                        />
                        <DropdownMenuContent align="end">
                            {STATUS_OPTIONS.map((status: CaseStatus) => {
                                const config = STATUS_CONFIG[status]
                                return (
                                    <DropdownMenuItem
                                        key={status}
                                        onClick={() => handleStatusChange(status)}
                                        disabled={status === caseData.status}
                                    >
                                        <span className={`mr-2 size-2 rounded-full ${config.color}`} />
                                        {config.label}
                                    </DropdownMenuItem>
                                )
                            })}
                        </DropdownMenuContent>
                    </DropdownMenu>
                    <Button variant="outline" size="sm">
                        Assign
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            render={
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreVerticalIcon className="h-4 w-4" />
                                </Button>
                            }
                        />
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setEditDialogOpen(true)}>Edit</DropdownMenuItem>
                            {caseData.is_archived ? (
                                <DropdownMenuItem onClick={handleRestore}>Restore</DropdownMenuItem>
                            ) : (
                                <DropdownMenuItem onClick={handleArchive}>Archive</DropdownMenuItem>
                            )}
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
                        <TabsTrigger value="notes">Notes {notes && notes.length > 0 && `(${notes.length})`}</TabsTrigger>
                        <TabsTrigger value="tasks">Tasks {tasksData && tasksData.items.length > 0 && `(${tasksData.items.length})`}</TabsTrigger>
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
                                            <div className="text-2xl font-semibold">{caseData.full_name}</div>
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
                                            <span className="text-sm">{caseData.phone || '-'}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">State:</span>
                                            <span className="text-sm">{caseData.state || '-'}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Source:</span>
                                            <Badge variant="secondary" className="capitalize">{caseData.source}</Badge>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Created:</span>
                                            <span className="text-sm">{formatDate(caseData.created_at)}</span>
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
                                            <span className="text-sm">{caseData.date_of_birth ? formatDate(caseData.date_of_birth) : '-'}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Race:</span>
                                            <span className="text-sm">{caseData.race || '-'}</span>
                                        </div>
                                        {(caseData.height_ft || caseData.weight_lb) && (
                                            <>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Height:</span>
                                                    <span className="text-sm">{caseData.height_ft ? `${caseData.height_ft} ft` : '-'}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Weight:</span>
                                                    <span className="text-sm">{caseData.weight_lb ? `${caseData.weight_lb} lb` : '-'}</span>
                                                </div>
                                            </>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>

                            <div>
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Eligibility Checklist</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        {[
                                            { label: 'Age Eligible (18-42)', value: caseData.is_age_eligible },
                                            { label: 'US Citizen or PR', value: caseData.is_citizen_or_pr },
                                            { label: 'Has Child', value: caseData.has_child },
                                            { label: 'Non-Smoker', value: caseData.is_non_smoker },
                                            { label: 'Prior Surrogate Experience', value: caseData.has_surrogate_experience },
                                        ].map(({ label, value }) => (
                                            <div key={label} className="flex items-center gap-2">
                                                {value === true && <CheckIcon className="h-4 w-4 text-green-500" />}
                                                {value === false && <XIcon className="h-4 w-4 text-red-500" />}
                                                {value === null && <span className="h-4 w-4 text-center text-muted-foreground">-</span>}
                                                <span className="text-sm">{label}</span>
                                            </div>
                                        ))}
                                        {(caseData.num_deliveries !== null || caseData.num_csections !== null) && (
                                            <div className="border-t pt-3 space-y-2">
                                                {caseData.num_deliveries !== null && (
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">Deliveries:</span>
                                                        <span className="text-sm">{caseData.num_deliveries}</span>
                                                    </div>
                                                )}
                                                {caseData.num_csections !== null && (
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">C-Sections:</span>
                                                        <span className="text-sm">{caseData.num_csections}</span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
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
                                    <RichTextEditor
                                        placeholder="Add a note..."
                                        onSubmit={handleAddNote}
                                        submitLabel="Add Note"
                                        isSubmitting={createNoteMutation.isPending}
                                    />

                                    {notes && notes.length > 0 ? (
                                        <div className="space-y-4 border-t pt-4">
                                            {notes.map((note) => (
                                                <div key={note.id} className="flex gap-3 group">
                                                    <Avatar className="h-8 w-8">
                                                        <AvatarFallback>{getInitials(note.author_name)}</AvatarFallback>
                                                    </Avatar>
                                                    <div className="flex-1 space-y-1">
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-sm font-medium">{note.author_name || 'Unknown'}</span>
                                                                <span className="text-xs text-muted-foreground">{formatDateTime(note.created_at)}</span>
                                                            </div>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-6 w-6 opacity-0 group-hover:opacity-100"
                                                                onClick={() => handleDeleteNote(note.id)}
                                                            >
                                                                <TrashIcon className="h-3 w-3" />
                                                            </Button>
                                                        </div>
                                                        <div
                                                            className="text-sm text-muted-foreground prose prose-sm max-w-none"
                                                            dangerouslySetInnerHTML={{ __html: note.body }}
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-sm text-muted-foreground text-center py-4">No notes yet. Add the first note above.</p>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* TASKS TAB */}
                    <TabsContent value="tasks" className="space-y-4">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle>Tasks for Case #{caseData.case_number}</CardTitle>
                                <Button size="sm">
                                    <PlusIcon className="h-4 w-4 mr-2" />
                                    Add Task
                                </Button>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {tasksData && tasksData.items.length > 0 ? (
                                    tasksData.items.map((task) => (
                                        <div key={task.id} className="flex items-start gap-3">
                                            <Checkbox
                                                id={`task-${task.id}`}
                                                className="mt-1"
                                                checked={task.is_completed}
                                                onCheckedChange={() => handleTaskToggle(task.id, task.is_completed)}
                                            />
                                            <div className="flex-1 space-y-1">
                                                <label
                                                    htmlFor={`task-${task.id}`}
                                                    className={`text-sm font-medium leading-none ${task.is_completed ? 'line-through text-muted-foreground' : ''}`}
                                                >
                                                    {task.title}
                                                </label>
                                                {task.due_date && (
                                                    <div className="flex items-center gap-2">
                                                        <Badge variant="secondary" className="text-xs">
                                                            Due: {formatDate(task.due_date)}
                                                        </Badge>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-sm text-muted-foreground text-center py-4">No tasks for this case.</p>
                                )}
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
                                {history && history.length > 0 ? (
                                    history.map((entry, idx) => {
                                        const toConfig = STATUS_CONFIG[entry.to_status as CaseStatus] || { label: entry.to_status, color: 'bg-gray-500' }
                                        const fromConfig = STATUS_CONFIG[entry.from_status as CaseStatus] || { label: entry.from_status, color: 'bg-gray-500' }
                                        const isLast = idx === history.length - 1

                                        return (
                                            <div key={entry.id} className="flex gap-3">
                                                <div className="relative">
                                                    <div className={`h-2 w-2 rounded-full ${toConfig.color} mt-1.5`}></div>
                                                    {!isLast && <div className="absolute left-1 top-4 h-full w-px bg-border"></div>}
                                                </div>
                                                <div className="flex-1 space-y-1 pb-4">
                                                    <div className="flex items-center gap-2">
                                                        <Badge variant="secondary" className="text-xs">
                                                            {fromConfig.label}
                                                        </Badge>
                                                        <span className="text-xs text-muted-foreground">→</span>
                                                        <Badge className={`${toConfig.color} text-white text-xs`}>
                                                            {toConfig.label}
                                                        </Badge>
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Changed by {entry.changed_by_name || 'System'} • {formatDateTime(entry.changed_at)}
                                                    </div>
                                                    {entry.reason && (
                                                        <p className="text-sm pt-1">{entry.reason}</p>
                                                    )}
                                                </div>
                                            </div>
                                        )
                                    })
                                ) : (
                                    <p className="text-sm text-muted-foreground text-center py-4">No status changes recorded.</p>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>

            {/* Edit Case Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Edit Case: #{caseData?.case_number}</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={async (e) => {
                        e.preventDefault()
                        const form = e.target as HTMLFormElement
                        const formData = new FormData(form)
                        const data: Record<string, unknown> = {}

                        // Text fields
                        if (formData.get('full_name')) data.full_name = formData.get('full_name')
                        if (formData.get('email')) data.email = formData.get('email')
                        data.phone = formData.get('phone') || null
                        data.state = formData.get('state') || null
                        data.date_of_birth = formData.get('date_of_birth') || null
                        data.race = formData.get('race') || null

                        // Number fields
                        const heightFt = formData.get('height_ft')
                        data.height_ft = heightFt ? parseFloat(heightFt as string) : null
                        const weightLb = formData.get('weight_lb')
                        data.weight_lb = weightLb ? parseFloat(weightLb as string) : null
                        const numDeliveries = formData.get('num_deliveries')
                        data.num_deliveries = numDeliveries ? parseInt(numDeliveries as string) : null
                        const numCsections = formData.get('num_csections')
                        data.num_csections = numCsections ? parseInt(numCsections as string) : null

                        // Boolean fields (checkboxes)
                        data.is_age_eligible = formData.get('is_age_eligible') === 'on'
                        data.is_citizen_or_pr = formData.get('is_citizen_or_pr') === 'on'
                        data.has_child = formData.get('has_child') === 'on'
                        data.is_non_smoker = formData.get('is_non_smoker') === 'on'
                        data.has_surrogate_experience = formData.get('has_surrogate_experience') === 'on'
                        data.is_priority = formData.get('is_priority') === 'on'

                        await updateCaseMutation.mutateAsync({ caseId: id, data })
                        setEditDialogOpen(false)
                    }}>
                        <div className="grid gap-4 py-4">
                            {/* Contact Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="full_name">Full Name *</Label>
                                    <Input id="full_name" name="full_name" defaultValue={caseData?.full_name} required />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email *</Label>
                                    <Input id="email" name="email" type="email" defaultValue={caseData?.email} required />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="phone">Phone</Label>
                                    <Input id="phone" name="phone" defaultValue={caseData?.phone ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="state">State</Label>
                                    <Input id="state" name="state" defaultValue={caseData?.state ?? ''} />
                                </div>
                            </div>

                            {/* Personal Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="date_of_birth">Date of Birth</Label>
                                    <Input id="date_of_birth" name="date_of_birth" type="date" defaultValue={caseData?.date_of_birth ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="race">Race</Label>
                                    <Input id="race" name="race" defaultValue={caseData?.race ?? ''} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="height_ft">Height (ft)</Label>
                                    <Input id="height_ft" name="height_ft" type="number" step="0.1" defaultValue={caseData?.height_ft ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="weight_lb">Weight (lb)</Label>
                                    <Input id="weight_lb" name="weight_lb" type="number" defaultValue={caseData?.weight_lb ?? ''} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="num_deliveries">Number of Deliveries</Label>
                                    <Input id="num_deliveries" name="num_deliveries" type="number" min="0" max="20" defaultValue={caseData?.num_deliveries ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="num_csections">Number of C-Sections</Label>
                                    <Input id="num_csections" name="num_csections" type="number" min="0" max="10" defaultValue={caseData?.num_csections ?? ''} />
                                </div>
                            </div>

                            {/* Boolean Fields */}
                            <div className="grid grid-cols-2 gap-4 pt-2">
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_priority" name="is_priority" defaultChecked={caseData?.is_priority} />
                                    <Label htmlFor="is_priority">Priority Case</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_age_eligible" name="is_age_eligible" defaultChecked={caseData?.is_age_eligible ?? false} />
                                    <Label htmlFor="is_age_eligible">Age Eligible</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_citizen_or_pr" name="is_citizen_or_pr" defaultChecked={caseData?.is_citizen_or_pr ?? false} />
                                    <Label htmlFor="is_citizen_or_pr">US Citizen/PR</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="has_child" name="has_child" defaultChecked={caseData?.has_child ?? false} />
                                    <Label htmlFor="has_child">Has Child</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_non_smoker" name="is_non_smoker" defaultChecked={caseData?.is_non_smoker ?? false} />
                                    <Label htmlFor="is_non_smoker">Non-Smoker</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="has_surrogate_experience" name="has_surrogate_experience" defaultChecked={caseData?.has_surrogate_experience ?? false} />
                                    <Label htmlFor="has_surrogate_experience">Surrogate Experience</Label>
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateCaseMutation.isPending}>
                                {updateCaseMutation.isPending ? 'Saving...' : 'Save Changes'}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    )
}
