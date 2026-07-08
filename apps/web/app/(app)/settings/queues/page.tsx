"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { PlusIcon, MoreVerticalIcon, Loader2Icon, UsersIcon, XIcon, UserPlusIcon } from "lucide-react"
import {
    useQueues,
    useCreateQueue,
    useUpdateQueue,
    useQueueMembers,
    useAddQueueMember,
    useRemoveQueueMember,
    type Queue,
    type QueueCreatePayload,
    type QueueMember,
} from "@/lib/hooks/use-queues"
import { useMembers } from "@/lib/hooks/use-permissions"
import type { Member } from "@/lib/api/permissions"
import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

function resolveErrorMessage(error: unknown, fallback: string) {
    if (error instanceof Error && error.message) return error.message
    return fallback
}

export default function QueuesSettingsPage() {
    const { push } = useRouter()
    const { user } = useAuth()
    const { data: queues, isLoading, error } = useQueues(true) // Include inactive
    const createQueueMutation = useCreateQueue()
    const updateQueueMutation = useUpdateQueue()

    const [createDialogOpen, setCreateDialogOpen] = React.useState(false)
    const [editDialogOpen, setEditDialogOpen] = React.useState(false)
    const [membersDialogOpen, setMembersDialogOpen] = React.useState(false)
    const editingQueueRef = React.useRef<Queue | null>(null)
    const [managingQueue, setManagingQueue] = React.useState<Queue | null>(null)
    const [formData, setFormData] = React.useState<QueueCreatePayload>({ name: "", description: "" })
    const [selectedUserId, setSelectedUserId] = React.useState<string>("")

    // Fetch org members for selector
    const { data: orgMembers } = useMembers()

    // Fetch queue members when managing
    const { data: queueMembers, isLoading: loadingMembers } = useQueueMembers(managingQueue?.id || null)
    const addMemberMutation = useAddQueueMember()
    const removeMemberMutation = useRemoveQueueMember()

    // Check if user is an admin
    const isManager = user?.role && ['admin', 'developer'].includes(user.role)

    // Redirect if not admin
    React.useEffect(() => {
        if (user && !isManager) {
            push('/settings')
        }
    }, [user, isManager, push])

    const handleCreateQueue = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!formData.name.trim()) return

        await createQueueMutation.mutateAsync(formData)
        setFormData({ name: "", description: "" })
        setCreateDialogOpen(false)
    }

    const handleUpdateQueue = async (e: React.FormEvent) => {
        e.preventDefault()
        const editingQueue = editingQueueRef.current
        if (!editingQueue || !formData.name.trim()) return

        const trimmedDescription = (formData.description ?? "").trim()
        await updateQueueMutation.mutateAsync({
            queueId: editingQueue.id,
            data: {
                name: formData.name,
                ...(trimmedDescription ? { description: trimmedDescription } : {}),
            },
        })
        setEditDialogOpen(false)
        editingQueueRef.current = null
        setFormData({ name: "", description: "" })
    }

    const handleToggleActive = async (queue: Queue) => {
        await updateQueueMutation.mutateAsync({
            queueId: queue.id,
            data: { is_active: !queue.is_active }
        })
    }

    const openEditDialog = (queue: Queue) => {
        editingQueueRef.current = queue
        setFormData({ name: queue.name, description: queue.description || "" })
        setEditDialogOpen(true)
    }

    const handleEditDialogOpenChange = (open: boolean) => {
        setEditDialogOpen(open)
        if (!open) {
            editingQueueRef.current = null
        }
    }

    const openMembersDialog = (queue: Queue) => {
        setManagingQueue(queue)
        setSelectedUserId("")
        setMembersDialogOpen(true)
    }

    const handleAddMember = async () => {
        if (!managingQueue || !selectedUserId) return
        try {
            await addMemberMutation.mutateAsync({ queueId: managingQueue.id, userId: selectedUserId })
            setSelectedUserId("")
            toast.success("Member added to queue")
        } catch (error: unknown) {
            toast.error(resolveErrorMessage(error, "Failed to add member"))
        }
    }

    const handleRemoveMember = async (userId: string) => {
        if (!managingQueue) return
        try {
            await removeMemberMutation.mutateAsync({ queueId: managingQueue.id, userId })
            toast.success("Member removed from queue")
        } catch (error: unknown) {
            toast.error(resolveErrorMessage(error, "Failed to remove member"))
        }
    }

    // Filter out users already in queue
    const availableMembers = orgMembers?.filter(
        m => !queueMembers?.some(qm => qm.user_id === m.user_id)
    ) || []

    if (!isManager) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <QueuesPageHeader onCreate={() => setCreateDialogOpen(true)} />
            <QueuesStatusContent
                error={error}
                isLoading={isLoading}
                queues={queues}
                onCreate={() => setCreateDialogOpen(true)}
                onEdit={openEditDialog}
                onManageMembers={openMembersDialog}
                onToggleActive={handleToggleActive}
            />
            <QueueFormDialog
                open={createDialogOpen}
                onOpenChange={setCreateDialogOpen}
                title="Create Queue"
                nameId="queue-name"
                descriptionId="queue-description"
                nameInputName="queueName"
                descriptionInputName="queueDescription"
                formData={formData}
                onFormDataChange={setFormData}
                onSubmit={handleCreateQueue}
                submitDisabled={createQueueMutation.isPending || !formData.name.trim()}
                submitLabel="Create Queue"
                pendingLabel="Creating…"
                isPending={createQueueMutation.isPending}
                namePlaceholder="e.g., New Leads Queue"
                descriptionPlaceholder="Brief description of the queue purpose"
            />
            <QueueFormDialog
                open={editDialogOpen}
                onOpenChange={handleEditDialogOpenChange}
                title="Edit Queue"
                nameId="edit-queue-name"
                descriptionId="edit-queue-description"
                nameInputName="editQueueName"
                descriptionInputName="editQueueDescription"
                formData={formData}
                onFormDataChange={setFormData}
                onSubmit={handleUpdateQueue}
                submitDisabled={updateQueueMutation.isPending || !formData.name.trim()}
                submitLabel="Save Changes"
                pendingLabel="Saving…"
                isPending={updateQueueMutation.isPending}
            />
            <QueueMembersDialog
                open={membersDialogOpen}
                onOpenChange={setMembersDialogOpen}
                managingQueue={managingQueue}
                selectedUserId={selectedUserId}
                onSelectedUserIdChange={setSelectedUserId}
                availableMembers={availableMembers}
                queueMembers={queueMembers}
                loadingMembers={loadingMembers}
                addMemberPending={addMemberMutation.isPending}
                removeMemberPending={removeMemberMutation.isPending}
                onAddMember={handleAddMember}
                onRemoveMember={handleRemoveMember}
            />
        </div>
    )
}

function QueuesPageHeader({ onCreate }: { onCreate: () => void }) {
    return (
        <div className="flex items-center justify-between mb-6">
            <div>
                <h1 className="text-2xl font-semibold flex items-center gap-2">
                    <UsersIcon className="size-6" aria-hidden="true" />
                    Queue Management
                </h1>
                <p className="text-muted-foreground">
                    Manage case queues for your organization
                </p>
            </div>
            <Button onClick={onCreate}>
                <PlusIcon className="size-4 mr-2" aria-hidden="true" />
                Create Queue
            </Button>
        </div>
    )
}

function QueuesStatusContent({
    error,
    isLoading,
    queues,
    onCreate,
    onEdit,
    onManageMembers,
    onToggleActive,
}: {
    error: Error | null | undefined
    isLoading: boolean
    queues: Queue[] | undefined
    onCreate: () => void
    onEdit: (queue: Queue) => void
    onManageMembers: (queue: Queue) => void
    onToggleActive: (queue: Queue) => void | Promise<void>
}) {
    if (error) {
        return (
            <Card className="p-6 text-center text-destructive mb-6">
                Error loading queues: {error.message}
            </Card>
        )
    }

    if (isLoading) {
        return (
            <Card className="p-12 flex items-center justify-center">
                <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </Card>
        )
    }

    if (queues?.length === 0) {
        return (
            <Card className="p-12 text-center">
                <UsersIcon className="size-12 mx-auto text-muted-foreground mb-4" aria-hidden="true" />
                <h3 className="text-lg font-medium mb-2">No queues yet</h3>
                <p className="text-muted-foreground mb-4">
                    Create your first queue to organize cases
                </p>
                <Button onClick={onCreate}>
                    <PlusIcon className="size-4 mr-2" aria-hidden="true" />
                    Create Queue
                </Button>
            </Card>
        )
    }

    if (!queues?.length) return null

    return (
        <QueuesTable
            queues={queues}
            onEdit={onEdit}
            onManageMembers={onManageMembers}
            onToggleActive={onToggleActive}
        />
    )
}

function QueuesTable({
    queues,
    onEdit,
    onManageMembers,
    onToggleActive,
}: {
    queues: Queue[]
    onEdit: (queue: Queue) => void
    onManageMembers: (queue: Queue) => void
    onToggleActive: (queue: Queue) => void | Promise<void>
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Queues</CardTitle>
                <CardDescription>
                    {queues.filter((queue) => queue.is_active).length} active, {queues.filter((queue) => !queue.is_active).length} inactive
                </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Name</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead>Members</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="w-[50px]"></TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {queues.map((queue) => (
                            <TableRow key={queue.id} className={!queue.is_active ? "opacity-50" : ""}>
                                <TableCell className="font-medium">{queue.name}</TableCell>
                                <TableCell className="text-muted-foreground max-w-[300px] truncate">
                                    {queue.description || "—"}
                                </TableCell>
                                <TableCell>
                                    <button
                                        type="button"
                                        onClick={() => onManageMembers(queue)}
                                        className="inline-flex"
                                        aria-label={`Manage members for ${queue.name}`}
                                    >
                                        <Badge variant="outline" className="cursor-pointer">
                                            <UsersIcon className="size-3 mr-1" aria-hidden="true" />
                                            {queue.member_ids?.length || 0}
                                        </Badge>
                                    </button>
                                </TableCell>
                                <TableCell>
                                    <Badge variant={queue.is_active ? "default" : "secondary"}>
                                        {queue.is_active ? "Active" : "Inactive"}
                                    </Badge>
                                </TableCell>
                                <TableCell>
                                    <DropdownMenu>
                                        <DropdownMenuTrigger
                                            className="inline-flex items-center justify-center size-8 p-0 rounded-md hover:bg-accent"
                                            aria-label={`Queue actions for ${queue.name}`}
                                        >
                                            <span className="inline-flex items-center justify-center">
                                                <MoreVerticalIcon className="size-4" aria-hidden="true" />
                                            </span>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem onClick={() => onEdit(queue)}>
                                                Edit
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => onManageMembers(queue)}>
                                                Manage Members
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => onToggleActive(queue)}>
                                                {queue.is_active ? "Deactivate" : "Activate"}
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    )
}

function QueueFormDialog({
    open,
    onOpenChange,
    title,
    nameId,
    descriptionId,
    nameInputName,
    descriptionInputName,
    formData,
    onFormDataChange,
    onSubmit,
    submitDisabled,
    submitLabel,
    pendingLabel,
    isPending,
    namePlaceholder,
    descriptionPlaceholder,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    title: string
    nameId: string
    descriptionId: string
    nameInputName: string
    descriptionInputName: string
    formData: QueueCreatePayload
    onFormDataChange: React.Dispatch<React.SetStateAction<QueueCreatePayload>>
    onSubmit: (event: React.FormEvent) => void | Promise<void>
    submitDisabled: boolean
    submitLabel: string
    pendingLabel: string
    isPending: boolean
    namePlaceholder?: string
    descriptionPlaceholder?: string
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                </DialogHeader>
                <form onSubmit={onSubmit}>
                    <div className="space-y-4 py-4">
                        <div>
                            <Label htmlFor={nameId}>Name</Label>
                            <Input
                                id={nameId}
                                name={nameInputName}
                                autoComplete="off"
                                value={formData.name}
                                onChange={(event) =>
                                    onFormDataChange((currentFormData) => ({
                                        ...currentFormData,
                                        name: event.target.value,
                                    }))
                                }
                                placeholder={namePlaceholder}
                                className="mt-2"
                            />
                        </div>
                        <div>
                            <Label htmlFor={descriptionId}>Description (optional)</Label>
                            <Textarea
                                id={descriptionId}
                                name={descriptionInputName}
                                autoComplete="off"
                                value={formData.description || ""}
                                onChange={(event) =>
                                    onFormDataChange((currentFormData) => ({
                                        ...currentFormData,
                                        description: event.target.value,
                                    }))
                                }
                                placeholder={descriptionPlaceholder}
                                className="mt-2"
                                rows={3}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={submitDisabled}>
                            {isPending ? pendingLabel : submitLabel}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}

function QueueMembersDialog({
    open,
    onOpenChange,
    managingQueue,
    selectedUserId,
    onSelectedUserIdChange,
    availableMembers,
    queueMembers,
    loadingMembers,
    addMemberPending,
    removeMemberPending,
    onAddMember,
    onRemoveMember,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    managingQueue: Queue | null
    selectedUserId: string
    onSelectedUserIdChange: (userId: string) => void
    availableMembers: Member[]
    queueMembers: QueueMember[] | undefined
    loadingMembers: boolean
    addMemberPending: boolean
    removeMemberPending: boolean
    onAddMember: () => void | Promise<void>
    onRemoveMember: (userId: string) => void | Promise<void>
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" aria-hidden="true" />
                        {managingQueue?.name} - Members
                    </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="flex gap-2">
                        <Select value={selectedUserId} onValueChange={(value) => onSelectedUserIdChange(value || "")}>
                            <SelectTrigger className="flex-1">
                                <SelectValue placeholder="Select a user to add…" />
                            </SelectTrigger>
                            <SelectContent>
                                {availableMembers.length === 0 ? (
                                    <div className="py-2 px-3 text-sm text-muted-foreground">
                                        All users are already members
                                    </div>
                                ) : (
                                    availableMembers.map((member) => (
                                        <SelectItem key={member.user_id} value={member.user_id}>
                                            {member.display_name || member.email}
                                        </SelectItem>
                                    ))
                                )}
                            </SelectContent>
                        </Select>
                        <Button
                            onClick={onAddMember}
                            disabled={!selectedUserId || addMemberPending}
                            size="icon"
                            aria-label="Add member to queue"
                        >
                            <UserPlusIcon className="size-4" aria-hidden="true" />
                        </Button>
                    </div>

                    <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs uppercase tracking-wider">
                            Current Members ({queueMembers?.length || 0})
                        </Label>
                        {loadingMembers ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            </div>
                        ) : queueMembers?.length === 0 ? (
                            <div className="text-center py-4 text-sm text-muted-foreground">
                                No members assigned. Queue is open to all case managers.
                            </div>
                        ) : (
                            <div className="space-y-1 max-h-[200px] overflow-y-auto">
                                {queueMembers?.map((member) => (
                                    <div
                                        key={member.id}
                                        className="flex items-center justify-between p-2 rounded-md bg-muted/50"
                                    >
                                        <div>
                                            <div className="font-medium text-sm">{member.user_name || "Unknown"}</div>
                                            <div className="text-xs text-muted-foreground">{member.user_email}</div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="size-7 text-muted-foreground hover:text-destructive"
                                            onClick={() => onRemoveMember(member.user_id)}
                                            disabled={removeMemberPending}
                                            aria-label={`Remove ${member.user_name || member.user_email || "member"} from queue`}
                                        >
                                            <XIcon className="size-4" aria-hidden="true" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <p className="text-xs text-muted-foreground">
                        When a queue has members, only those members can claim surrogates from it.
                        If no members are assigned, any case manager can claim from the queue.
                    </p>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Close member management
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
