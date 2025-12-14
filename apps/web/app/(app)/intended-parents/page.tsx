"use client"

import { useState } from "react"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { PlusIcon, MoreVerticalIcon, SearchIcon } from "lucide-react"

// Sample data - TODO: Replace with API data
const intendedParents = [
    {
        id: "IP-001",
        name: "John & Jane Smith",
        email: "john.smith@email.com",
        phone: "(555) 123-4567",
        status: "Active",
        cases: 2,
        created: "1 week ago",
    },
    {
        id: "IP-002",
        name: "Michael & Sarah Davis",
        email: "michael.davis@email.com",
        phone: "(555) 234-5678",
        status: "Matched",
        cases: 1,
        created: "2 weeks ago",
    },
    {
        id: "IP-003",
        name: "Maria Garcia",
        email: "maria.garcia@email.com",
        phone: "(555) 345-6789",
        status: "Active",
        cases: 0,
        created: "3 weeks ago",
    },
    {
        id: "IP-004",
        name: "Robert & Lisa Chen",
        email: "robert.chen@email.com",
        phone: "(555) 456-7890",
        status: "On Hold",
        cases: 1,
        created: "1 month ago",
    },
    {
        id: "IP-005",
        name: "David Thompson",
        email: "david.t@email.com",
        phone: "(555) 567-8901",
        status: "Active",
        cases: 3,
        created: "1 month ago",
    },
    {
        id: "IP-006",
        name: "James & Emily Wilson",
        email: "j.wilson@email.com",
        phone: "(555) 678-9012",
        status: "Inactive",
        cases: 0,
        created: "2 months ago",
    },
    {
        id: "IP-007",
        name: "Jennifer Anderson",
        email: "j.anderson@email.com",
        phone: "(555) 789-0123",
        status: "Active",
        cases: 1,
        created: "2 months ago",
    },
    {
        id: "IP-008",
        name: "William & Amy Brown",
        email: "w.brown@email.com",
        phone: "(555) 890-1234",
        status: "Matched",
        cases: 2,
        created: "3 months ago",
    },
    {
        id: "IP-009",
        name: "Christopher Lee",
        email: "c.lee@email.com",
        phone: "(555) 901-2345",
        status: "Active",
        cases: 0,
        created: "3 months ago",
    },
    {
        id: "IP-010",
        name: "Daniel & Rachel Martinez",
        email: "d.martinez@email.com",
        phone: "(555) 012-3456",
        status: "On Hold",
        cases: 1,
        created: "4 months ago",
    },
]

const statusColors: Record<string, string> = {
    Active: "bg-green-500/10 text-green-500 border-green-500/20",
    Matched: "bg-purple-500/10 text-purple-500 border-purple-500/20",
    "On Hold": "bg-gray-500/10 text-gray-400 border-gray-500/20",
    Inactive: "bg-slate-500/10 text-slate-400 border-slate-500/20",
}

export default function IntendedParentsPage() {
    const [statusFilter, setStatusFilter] = useState("all")
    const [searchQuery, setSearchQuery] = useState("")

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Intended Parents</h1>
                    <Button>
                        <PlusIcon className="mr-2 size-4" />
                        Add Intended Parent
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-4 p-6">
                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                    <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value || "all")}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Statuses" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="active">Active</SelectItem>
                            <SelectItem value="matched">Matched</SelectItem>
                            <SelectItem value="on-hold">On Hold</SelectItem>
                            <SelectItem value="inactive">Inactive</SelectItem>
                        </SelectContent>
                    </Select>

                    <div className="relative ml-auto w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search intended parents..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9"
                        />
                    </div>
                </div>

                {/* Table Card */}
                <Card className="overflow-hidden">
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>ID</TableHead>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Phone</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Cases</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="w-[50px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {intendedParents.map((parent) => (
                                    <TableRow key={parent.id}>
                                        <TableCell>
                                            <Link href={`/intended-parents/${parent.id}`} className="font-medium text-primary hover:underline">
                                                {parent.id}
                                            </Link>
                                        </TableCell>
                                        <TableCell className="font-medium">{parent.name}</TableCell>
                                        <TableCell className="text-muted-foreground">{parent.email}</TableCell>
                                        <TableCell className="text-muted-foreground">{parent.phone}</TableCell>
                                        <TableCell>
                                            <Badge variant="secondary" className={statusColors[parent.status]}>
                                                {parent.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary" className="bg-primary/10 text-primary">
                                                {parent.cases} {parent.cases === 1 ? "case" : "cases"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">{parent.created}</TableCell>
                                        <TableCell>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="sm" className="size-8 p-0">
                                                        <MoreVerticalIcon className="size-4" />
                                                        <span className="sr-only">Open menu</span>
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem asChild>
                                                        <Link href={`/intended-parents/${parent.id}`}>View</Link>
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem>Edit</DropdownMenuItem>
                                                    <DropdownMenuItem>Archive</DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>

                    {/* Pagination */}
                    <div className="flex items-center justify-between border-t border-border px-6 py-4">
                        <div className="text-sm text-muted-foreground">Showing 1-10 of 48 intended parents</div>
                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm" disabled>
                                Previous
                            </Button>
                            <Button variant="outline" size="sm" className="bg-primary/10 text-primary">
                                1
                            </Button>
                            <Button variant="outline" size="sm">
                                2
                            </Button>
                            <Button variant="outline" size="sm">
                                3
                            </Button>
                            <Button variant="outline" size="sm">
                                4
                            </Button>
                            <Button variant="outline" size="sm">
                                5
                            </Button>
                            <Button variant="outline" size="sm">
                                Next
                            </Button>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    )
}
