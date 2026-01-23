'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Building2, Users, AlertTriangle, Plus, Bell, Loader2 } from 'lucide-react';
import { getPlatformStats, listAlerts, type PlatformAlert, type PlatformStats } from '@/lib/api/platform';
import { toast } from 'sonner';


function StatCard({
    title,
    value,
    icon: Icon,
    trend,
    trendLabel,
    subtitle,
    variant = 'default',
    action,
}: {
    title: string;
    value: number;
    icon: React.ElementType;
    trend?: number;
    trendLabel?: string;
    subtitle?: string;
    variant?: 'default' | 'warning';
    action?: { label: string; href: string };
}) {
    return (
        <Card className={variant === 'warning' && value > 0 ? 'border-amber-200 dark:border-amber-900/50' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-stone-500 dark:text-stone-400">
                    {title}
                </CardTitle>
                <Icon
                    className={`size-5 ${
                        variant === 'warning' && value > 0
                            ? 'text-amber-500'
                            : 'text-stone-400 dark:text-stone-500'
                    }`}
                />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-stone-900 dark:text-stone-100">
                    {value.toLocaleString()}
                </div>
                {(trend !== undefined || subtitle) && (
                    <p className="text-xs text-stone-500 dark:text-stone-400 mt-1">
                        {trend !== undefined && (
                            <span className={trend >= 0 ? 'text-green-600' : 'text-red-600'}>
                                {trend >= 0 ? '+' : ''}
                                {trend}
                            </span>
                        )}
                        {trend !== undefined && trendLabel && ` ${trendLabel}`}
                        {subtitle && !trend && subtitle}
                    </p>
                )}
                {action && (
                    <Link
                        href={action.href}
                        className={buttonVariants({
                            variant: 'link',
                            size: 'sm',
                            className: 'p-0 h-auto mt-2 text-teal-600 dark:text-teal-400',
                        })}
                    >
                        {action.label}
                    </Link>
                )}
            </CardContent>
        </Card>
    );
}

export default function OpsDashboard() {
    const [stats, setStats] = useState<PlatformStats | null>(null);
    const [recentAlerts, setRecentAlerts] = useState<PlatformAlert[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [hasError, setHasError] = useState(false);

    useEffect(() => {
        async function fetchDashboard() {
            setIsLoading(true);
            setHasError(false);
            try {
                const [statsData, alertsData] = await Promise.all([
                    getPlatformStats(),
                    listAlerts({ limit: 5, status: 'open' }),
                ]);
                setStats(statsData);
                setRecentAlerts(alertsData.items);
            } catch {
                setHasError(true);
                toast.error('Failed to load ops dashboard');
            } finally {
                setIsLoading(false);
            }
        }
        fetchDashboard();
    }, []);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (hasError || !stats) {
        return (
            <div className="flex items-center justify-center py-16">
                <div className="text-center space-y-3">
                    <AlertTriangle className="size-10 mx-auto text-muted-foreground/60" />
                    <p className="text-muted-foreground">Failed to load dashboard data.</p>
                    <Button variant="outline" onClick={() => window.location.reload()}>
                        Retry
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-6 p-6">
            {/* Welcome Banner */}
            <div className="rounded-xl bg-gradient-to-r from-teal-600 to-teal-500 p-6 text-white">
                <h1 className="text-2xl font-semibold">Platform Operations</h1>
                <p className="text-teal-100 mt-1">
                    Manage agencies, users, and system health
                </p>
                <Link
                    href="/ops/agencies/new"
                    className={buttonVariants({
                        className: 'mt-4 bg-white text-teal-600 hover:bg-teal-50',
                    })}
                >
                    <Plus className="mr-2 size-4" />
                    Create Agency
                </Link>
            </div>

            {/* Stats Grid */}
            <div className="grid gap-4 md:grid-cols-3">
                <StatCard
                    title="Agencies"
                    value={stats.agency_count ?? 0}
                    icon={Building2}
                />
                <StatCard
                    title="Active Users"
                    value={stats.active_user_count ?? 0}
                    icon={Users}
                    subtitle="Last 30 days"
                />
                <StatCard
                    title="Open Alerts"
                    value={stats.open_alerts ?? 0}
                    icon={AlertTriangle}
                    variant={stats.open_alerts > 0 ? 'warning' : 'default'}
                    action={{ label: 'View', href: '/ops/alerts' }}
                />
            </div>

            {/* Quick Actions */}
            <div className="flex gap-3">
                <Link href="/ops/agencies" className={buttonVariants({ variant: 'outline' })}>
                    <Building2 className="mr-2 size-4" />
                    View All Agencies
                </Link>
                <Link href="/ops/alerts" className={buttonVariants({ variant: 'outline' })}>
                    <Bell className="mr-2 size-4" />
                    Alert Inbox
                </Link>
            </div>

            {/* Empty State for Recent Alerts */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-lg">Recent Alerts</CardTitle>
                    <Link href="/ops/alerts" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
                        View all
                    </Link>
                </CardHeader>
                <CardContent>
                    {recentAlerts.length === 0 ? (
                        <div className="text-center py-8">
                            <AlertTriangle className="size-12 mx-auto mb-4 text-muted-foreground/50" />
                            <p className="text-muted-foreground">No recent alerts</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {recentAlerts.map((alert) => (
                                <Link
                                    key={alert.id}
                                    href={`/ops/agencies/${alert.organization_id}`}
                                    className="block rounded-md border border-stone-200 dark:border-stone-800 p-3 hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                                                {alert.title}
                                            </p>
                                            <p className="text-xs text-stone-500 dark:text-stone-400">
                                                {alert.org_name} · {alert.severity.toUpperCase()}
                                            </p>
                                        </div>
                                        <Badge variant="outline">{alert.status}</Badge>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
