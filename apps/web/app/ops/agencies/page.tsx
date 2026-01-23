'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { listOrganizations, type OrganizationSummary } from '@/lib/api/platform';
import { buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Building2, Plus, Search, ChevronRight, Loader2, Users } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const STATUS_BADGE_VARIANTS: Record<string, string> = {
    active: 'bg-green-500/10 text-green-600 border-green-500/20',
    trial: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    past_due: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    canceled: 'bg-red-500/10 text-red-600 border-red-500/20',
};

const PLAN_BADGE_VARIANTS: Record<string, string> = {
    starter: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300',
    professional: 'bg-teal-500/10 text-teal-600 dark:text-teal-400',
    enterprise: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
};

export default function AgenciesPage() {
    const router = useRouter();
    const [agencies, setAgencies] = useState<OrganizationSummary[]>([]);
    const [total, setTotal] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('');

    useEffect(() => {
        async function fetchAgencies() {
            setIsLoading(true);
            try {
                const data = await listOrganizations({
                    ...(search ? { search } : {}),
                    ...(statusFilter ? { status: statusFilter } : {}),
                });
                setAgencies(data.items);
                setTotal(data.total);
            } catch (error) {
                console.error('Failed to fetch agencies:', error);
            } finally {
                setIsLoading(false);
            }
        }
        fetchAgencies();
    }, [search, statusFilter]);

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                        Agencies
                    </h1>
                    <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
                        {total} total agencies
                    </p>
                </div>
                <Link href="/ops/agencies/new" className={buttonVariants()}>
                    <Plus className="mr-2 size-4" />
                    Create Agency
                </Link>
            </div>

            {/* Filters */}
            <div className="flex gap-4">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-stone-400" />
                    <Input
                        placeholder="Search by name or slug..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9"
                    />
                </div>
                <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v || '')}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">All statuses</SelectItem>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="trial">Trial</SelectItem>
                        <SelectItem value="past_due">Past Due</SelectItem>
                        <SelectItem value="canceled">Canceled</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Table */}
            {isLoading ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="size-8 animate-spin text-muted-foreground" />
                </div>
            ) : agencies.length === 0 ? (
                <div className="text-center py-16 border rounded-lg bg-white dark:bg-stone-900">
                    <Building2 className="mx-auto size-12 text-muted-foreground/50 mb-4" />
                    <h3 className="text-lg font-medium text-foreground">No agencies yet</h3>
                    <p className="text-muted-foreground mt-1 mb-4">
                        Create your first agency to get started
                    </p>
                    <Link href="/ops/agencies/new" className={buttonVariants()}>
                        <Plus className="mr-2 size-4" />
                        Create Agency
                    </Link>
                </div>
            ) : (
                <div className="border rounded-lg bg-white dark:bg-stone-900">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Agency</TableHead>
                                <TableHead>Members</TableHead>
                                <TableHead>Surrogates</TableHead>
                                <TableHead>Plan</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead className="w-10"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {agencies.map((agency) => (
                                <TableRow
                                    key={agency.id}
                                    className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                                    onClick={() => router.push(`/ops/agencies/${agency.id}`)}
                                >
                                    <TableCell>
                                        <div>
                                            <div className="font-medium text-stone-900 dark:text-stone-100">
                                                {agency.name}
                                            </div>
                                            <div className="text-xs font-mono text-stone-500">
                                                {agency.slug}
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-1.5 text-stone-600 dark:text-stone-300">
                                            <Users className="size-3.5" />
                                            {agency.member_count}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-stone-600 dark:text-stone-300">
                                        {agency.surrogate_count}
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={PLAN_BADGE_VARIANTS[agency.subscription_plan]}
                                        >
                                            {agency.subscription_plan}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={STATUS_BADGE_VARIANTS[agency.subscription_status]}
                                        >
                                            {agency.subscription_status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-stone-500 dark:text-stone-400 text-sm">
                                        {formatDistanceToNow(new Date(agency.created_at), {
                                            addSuffix: true,
                                        })}
                                    </TableCell>
                                    <TableCell>
                                        <ChevronRight className="size-4 text-stone-400" />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    );
}
