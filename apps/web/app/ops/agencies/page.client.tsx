'use client';

import { useReducer } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from "@/components/app-link";
import { useRouter } from 'next/navigation';
import { getPlatformStats, listOrganizations } from '@/lib/api/platform';
import { buttonVariants } from '@/components/ui/button-variants';
import { PageHeader } from '@/components/page-header';
import { EmptyState } from '@/components/empty-state';
import { QueryErrorState } from '@/components/error-state';
import { toSelectOptions } from '@/lib/select-labels';
import {
    PLAN_BADGE_VARIANTS,
    STATUS_BADGE_VARIANTS,
    SUBSCRIPTION_STATUS_LABELS,
    getSubscriptionPlanLabel,
    getSubscriptionStatusLabel,
} from '@/components/ops/agencies/agency-constants';
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
import { RelativeTime } from '@/components/ui/time-display';
import { Building2, Plus, Search, ChevronRight, Loader2, Users } from 'lucide-react';

type AgenciesState = {
    search: string
    statusFilter: string
}

type AgenciesAction =
    | { type: "set-search"; search: string }
    | { type: "set-status-filter"; statusFilter: string }
    | { type: "clear-filters" }

const INITIAL_AGENCIES_STATE: AgenciesState = {
    search: "",
    statusFilter: "",
}

function agenciesReducer(state: AgenciesState, action: AgenciesAction): AgenciesState {
    switch (action.type) {
        case "set-search":
            return { ...state, search: action.search }
        case "set-status-filter":
            return { ...state, statusFilter: action.statusFilter }
        case "clear-filters":
            return INITIAL_AGENCIES_STATE
    }
}

export default function AgenciesPage() {
    const { push } = useRouter();
    const [state, dispatch] = useReducer(agenciesReducer, INITIAL_AGENCIES_STATE);
    const { search, statusFilter } = state;
    const agenciesQuery = useQuery({
        queryKey: [
            'platform',
            'agencies',
            { search: search || null, status: statusFilter || null },
        ],
        queryFn: async () => {
            const data = await listOrganizations({
                ...(search ? { search } : {}),
                ...(statusFilter ? { status: statusFilter } : {}),
            });
            return {
                ...data,
                items: data.items.filter((item) => !item.deleted_at),
            };
        },
        retry: false,
        staleTime: 30_000,
    });
    // Same query the ops layout uses for the nav badge, so this reads from cache.
    const statsQuery = useQuery({
        queryKey: ['platform', 'stats'],
        queryFn: getPlatformStats,
        retry: false,
        staleTime: 60_000,
    });
    const agencies = agenciesQuery.data?.items ?? [];
    const isLoading = agenciesQuery.isFetching;
    const hasActiveFilters = search.trim() !== '' || statusFilter !== '';
    const clearFilters = () => dispatch({ type: "clear-filters" });

    const createAgencyLink = (
        <Link href="/ops/agencies/new" className={buttonVariants()}>
            <Plus className="size-4" aria-hidden="true" />
            Create Agency
        </Link>
    );

    return (
        <div>
            <PageHeader
                title="Agencies"
                count={agenciesQuery.isSuccess ? agencies.length : null}
                countTotal={statsQuery.data?.agency_count}
                countLabel="agencies"
                actions={createAgencyLink}
            />

            <div className="p-6 space-y-6">
                {/* Filters */}
                <div className="flex flex-wrap gap-4">
                    <div className="relative w-full sm:max-w-sm sm:flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" aria-hidden="true" />
                        <Input
                            placeholder="Search by name or slug..."
                            aria-label="Search agencies"
                            value={search}
                            onChange={(e) => dispatch({ type: "set-search", search: e.target.value })}
                            className="pl-9"
                        />
                    </div>
                    <Select
                        value={statusFilter}
                        onValueChange={(v) => dispatch({ type: "set-status-filter", statusFilter: v || "" })}
                    >
                        <SelectTrigger className="w-full sm:w-[180px]" aria-label="Filter by status">
                            <SelectValue placeholder="All statuses">{getSubscriptionStatusLabel}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="">All statuses</SelectItem>
                            {toSelectOptions(SUBSCRIPTION_STATUS_LABELS).map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Table */}
                {agenciesQuery.isError ? (
                <div className="border rounded-lg bg-card">
                    <QueryErrorState
                        error={agenciesQuery.error}
                        onRetry={() => void agenciesQuery.refetch()}
                        isRetrying={agenciesQuery.isFetching}
                        title="Couldn't load agencies"
                        headingLevel={2}
                        className="min-h-0 py-12"
                    />
                </div>
            ) : isLoading ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="size-8 animate-spin text-muted-foreground" />
                </div>
            ) : agencies.length === 0 ? (
                <div className="border rounded-lg bg-card">
                    {hasActiveFilters ? (
                        <EmptyState
                            icon={Building2}
                            title="No matching agencies"
                            headingLevel={2}
                            onClearFilters={clearFilters}
                        />
                    ) : (
                        <EmptyState
                            icon={Building2}
                            title="No agencies yet"
                            headingLevel={2}
                            action={createAgencyLink}
                        />
                    )}
                </div>
            ) : (
                <div className="border rounded-lg bg-card">
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
                                    className="cursor-pointer hover:bg-muted/50"
                                    onClick={() => push(`/ops/agencies/${agency.id}`)}
                                >
                                    <TableCell>
                                        <div>
                                            <div className="font-medium text-foreground">
                                                {agency.name}
                                            </div>
                                            <div className="text-xs font-mono text-muted-foreground">
                                                {agency.slug}
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-1.5 text-muted-foreground">
                                            <Users className="size-3.5" aria-hidden="true" />
                                            {agency.member_count}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {agency.surrogate_count}
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={PLAN_BADGE_VARIANTS[agency.subscription_plan]}
                                        >
                                            {getSubscriptionPlanLabel(agency.subscription_plan)}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={STATUS_BADGE_VARIANTS[agency.subscription_status]}
                                        >
                                            {getSubscriptionStatusLabel(agency.subscription_status)}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground text-sm">
                                        <RelativeTime value={agency.created_at} />
                                    </TableCell>
                                    <TableCell>
                                        <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
            </div>
        </div>
    );
}
