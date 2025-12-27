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
import { PlusIcon, MoreVerticalIcon, LoaderIcon, UsersIcon, XIcon, UserPlusIcon } from "lucide-react"
import {
    useQueues,
    useCreateQueue,
    useUpdateQueue,
    useDeleteQueue,
    useQueueMembers,
    useAddQueueMember,
    useRemoveQueueMember,
    type Queue,
    type QueueCreatePayload
} from "@/lib/hooks/use-queues"
import { useMembers } from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

export default function QueuesSettingsPage() {
    const router = useRouter()
    const { user } = useAuth()
    const { data: queues, isLoading, error } = useQueues(true) // Include inactive
    const createQueueMutation = useCreateQueue()
    const updateQueueMutation = useUpdateQueue()
    const deleteQueueMutation = useDeleteQueue()

    const [createDialogOpen, setCreateDialogOpen] = React.useState(false)
    const [editDialogOpen, setEditDialogOpen] = React.useState(false)
    const [membersDialogOpen, setMembersDialogOpen] = React.useState(false)
    const [editingQueue, setEditingQueue] = React.useState<Queue | null>(null)
    const [managingQueue, setManagingQueue] = React.useState<Queue | null>(null)
    const [formData, setFormData] = React.useState<QueueCreatePayload>({ name: "", description: "" })
    const [selectedUserId, setSelectedUserId] = React.useState<string>("")

    // Fetch org members for selector
    const { data: orgMembers } = useMembers()

    // Fetch queue members when managing
    const { data: queueMembers, isLoading: loadingMembers } = useQueueMembers(managingQueue?.id || null)
    const addMemberMutation = useAddQueueMember()
    const removeMemberMutation = useRemoveQueueMember()

    // Check if user is a manager
    const isManager = user?.role && ['admin', 'developer'].includes(user.role)

    // Redirect if not manager
    React.useEffect(() => {
        if (user && !isManager) {
            router.push('/settings')
        }
    }, [user, isManager, router])

    const handleCreateQueue = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!formData.name.trim()) return

        await createQueueMutation.mutateAsync(formData)
        setFormData({ name: "", description: "" })
        setCreateDialogOpen(false)
    }

    const handleUpdateQueue = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editingQueue || !formData.name.trim()) return

        await updateQueueMutation.mutateAsync({
            queueId: editingQueue.id,
            data: { name: formData.name, description: formData.description }
        })
        setEditDialogOpen(false)
        setEditingQueue(null)
        setFormData({ name: "", description: "" })
    }

    const handleToggleActive = async (queue: Queue) => {
        await updateQueueMutation.mutateAsync({
            queueId: queue.id,
            data: { is_active: !queue.is_active }
        })
    }

    const handleDeleteQueue = async (queueId: string) => {
        if (!confirm("Are you sure you want to deactivate this queue?")) return
        await deleteQueueMutation.mutateAsync(queueId)
    }

    const openEditDialog = (queue: Queue) => {
        setEditingQueue(queue)
        setFormData({ name: queue.name, description: queue.description || "" })
        setEditDialogOpen(true)
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
        } catch (error: any) {
            toast.error(error?.message || "Failed to add member")
        }
    }

    const handleRemoveMember = async (userId: string) => {
        if (!managingQueue) return
        try {
            await removeMemberMutation.mutateAsync({ queueId: managingQueue.id, userId })
            toast.success("Member removed from queue")
        } catch (error: any) {
            toast.error(error?.message || "Failed to remove member")
        }
    }

    // Filter out users already in queue
    const availableMembers = orgMembers?.filter(
        m => !queueMembers?.some(qm => qm.user_id === m.user_id)
    ) || []

    if (!isManager) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <UsersIcon className="h-6 w-6" />
                        Queue Management
                    </h1>
                    <p className="text-muted-foreground">
                        Manage case queues for your organization
                    </p>
                </div>
                <Button onClick={() => setCreateDialogOpen(true)}>
                    <PlusIcon className="h-4 w-4 mr-2" />
                    Create Queue
                </Button>
            </div>

            {/* Error State */}
            {error && (
                <Card className="p-6 text-center text-destructive mb-6">
                    Error loading queues: {error.message}
                </Card>
            )}

            {/* Loading State */}
            {isLoading && (
                <Card className="p-12 flex items-center justify-center">
                    <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                </Card>
            )}

            {/* Empty State */}
            {!isLoading && !error && queues?.length === 0 && (
                <Card className="p-12 text-center">
                    <UsersIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">No queues yet</h3>
                    <p className="text-muted-foreground mb-4">
                        Create your first queue to organize cases
                    </p>
                    <Button onClick={() => setCreateDialogOpen(true)}>
                        <PlusIcon className="h-4 w-4 mr-2" />
                        Create Queue
                    </Button>
                </Card>
            )}

            {/* Queues Table */}
            {!isLoading && !error && queues && queues.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Queues</CardTitle>
                        <CardDescription>
                            {queues.filter(q => q.is_active).length} active, {queues.filter(q => !q.is_active).length} inactive
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
                                            <Badge variant="outline" className="cursor-pointer" onClick={() => openMembersDialog(queue)}>
                                                <UsersIcon className="size-3 mr-1" />
                                                {queue.member_ids?.length || 0}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={queue.is_active ? "default" : "secondary"}>
                                                {queue.is_active ? "Active" : "Inactive"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger className="inline-flex items-center justify-center size-8 p-0 rounded-md hover:bg-accent">
                                                    <span className="inline-flex items-center justify-center">
                                                        <MoreVerticalIcon className="size-4" />
                                                    </span>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => openEditDialog(queue)}>
                                                        Edit
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => openMembersDialog(queue)}>
                                                        Manage Members
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => handleToggleActive(queue)}>
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
            )}

            {/* Create Queue Dialog */}
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Queue</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleCreateQueue}>
                        <div className="space-y-4 py-4">
                            <div>
                                <Label htmlFor="queue-name">Name</Label>
                                <Input
                                    id="queue-name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="e.g., New Leads Queue"
                                    className="mt-2"
                                />
                            </div>
                            <div>
                                <Label htmlFor="queue-description">Description (optional)</Label>
                                <Textarea
                                    id="queue-description"
                                    value={formData.description || ""}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    placeholder="Brief description of the queue purpose"
                                    className="mt-2"
                                    rows={3}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" type="button" onClick={() => setCreateDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={createQueueMutation.isPending || !formData.name.trim()}>
                                {createQueueMutation.isPending ? "Creating..." : "Create Queue"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Edit Queue Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Queue</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleUpdateQueue}>
                        <div className="space-y-4 py-4">
                            <div>
                                <Label htmlFor="edit-queue-name">Name</Label>
                                <Input
                                    id="edit-queue-name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="mt-2"
                                />
                            </div>
                            <div>
                                <Label htmlFor="edit-queue-description">Description (optional)</Label>
                                <Textarea
                                    id="edit-queue-description"
                                    value={formData.description || ""}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    className="mt-2"
                                    rows={3}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" type="button" onClick={() => setEditDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateQueueMutation.isPending || !formData.name.trim()}>
                                {updateQueueMutation.isPending ? "Saving..." : "Save Changes"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Members Dialog */}
            <Dialog open={membersDialogOpen} onOpenChange={setMembersDialogOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <UsersIcon className="size-5" />
                            {managingQueue?.name} - Members
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        {/* Add Member */}
                        <div className="flex gap-2">
                            <Select value={selectedUserId} onValueChange={(v) => setSelectedUserId(v || "")}>
                                <SelectTrigger className="flex-1">
                                    <SelectValue placeholder="Select a user to add..." />
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
                                onClick={handleAddMember}
                                disabled={!selectedUserId || addMemberMutation.isPending}
                                size="icon"
                            >
                                <UserPlusIcon className="size-4" />
                            </Button>
                        </div>

                        {/* Member List */}
                        <div className="space-y-2">
                            <Label className="text-muted-foreground text-xs uppercase tracking-wider">
                                Current Members ({queueMembers?.length || 0})
                            </Label>
                            {loadingMembers ? (
                                <div className="flex items-center justify-center py-4">
                                    <LoaderIcon className="size-4 animate-spin" />
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
                                                onClick={() => handleRemoveMember(member.user_id)}
                                                disabled={removeMemberMutation.isPending}
                                            >
                                                <XIcon className="size-4" />
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Help text */}
                        <p className="text-xs text-muted-foreground">
                            When a queue has members, only those members can claim cases from it.
                            If no members are assigned, any case manager can claim from the queue.
                        </p>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setMembersDialogOpen(false)}>
                            Done
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
