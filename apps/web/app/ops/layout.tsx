'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';
import Link from "@/components/app-link";
import { getPlatformMe, getPlatformStats } from '@/lib/api/platform';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ShieldCheck, Building2, Bell, LogOut, Loader2, LayoutTemplate, Terminal } from 'lucide-react';
import api, { ApiError } from '@/lib/api';
import './ops-theme.css';

function NavLink({
    href,
    exact = false,
    children,
}: {
    href: string;
    exact?: boolean;
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const isActive = exact ? pathname === href : pathname.startsWith(href);

    return (
        <Link
            href={href}
            aria-current={isActive ? 'page' : undefined}
            className={`shrink-0 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
        >
            {children}
        </Link>
    );
}

function getOpsAccessRedirect(error: unknown) {
    if (error instanceof ApiError && error.status === 403) {
        return error.message.toLowerCase().includes('mfa')
            ? '/mfa'
            : '/ops/login?error=not_platform_admin';
    }
    return '/ops/login';
}

function redirectToOpsLogin() {
    window.location.href = '/ops/login';
}

async function logoutFromOps() {
    try {
        await api.post('/auth/logout');
    } catch {
        // Ignore errors
    }
    redirectToOpsLogin();
}

export default function OpsLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { replace } = useRouter();
    const isLoginPage = pathname === '/ops/login';
    const platformMeQuery = useQuery({
        queryKey: ['platform', 'me'],
        queryFn: getPlatformMe,
        enabled: !isLoginPage,
        retry: false,
        staleTime: 60_000,
    });
    const platformStatsQuery = useQuery({
        queryKey: ['platform', 'stats'],
        queryFn: getPlatformStats,
        enabled: !isLoginPage,
        retry: false,
        staleTime: 60_000,
    });

    useEffect(() => {
        if (isLoginPage) return;
        if (platformMeQuery.isError) {
            if (pathname === '/ops/cli') {
                sessionStorage.setItem('ops_cli_login_pending', '1');
            }
            replace(getOpsAccessRedirect(platformMeQuery.error));
        } else if (pathname === '/ops' && platformMeQuery.isSuccess && sessionStorage.getItem('ops_cli_login_pending') === '1') {
            sessionStorage.removeItem('ops_cli_login_pending');
            replace('/ops/cli');
        }
    }, [isLoginPage, pathname, platformMeQuery.isError, platformMeQuery.isSuccess, platformMeQuery.error, replace]);

    // Don't show layout for login page
    if (isLoginPage) {
        return <>{children}</>;
    }

    if (platformMeQuery.isError) {
        return null;
    }

    // Stats only feed the Alerts badge, so the shell waits for the access check alone.
    if (platformMeQuery.isPending) {
        return (
            <div data-ops-console="" className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="size-8 animate-spin text-primary" aria-label="Loading" />
            </div>
        );
    }

    const user = platformMeQuery.data;
    const openAlertCount = platformStatsQuery.data?.open_alerts ?? 0;

    return (
        <div data-ops-console="" className="min-h-screen bg-background">
            {/* Top Header */}
            <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-14 items-center justify-between gap-4 px-4 sm:px-6">
                    <div className="flex min-w-0 items-center gap-6">
                        {/* Logo/Brand */}
                        <Link href="/ops" className="flex shrink-0 items-center gap-2" aria-label="Ops Console">
                            <div className="size-8 rounded-lg bg-primary flex items-center justify-center">
                                <ShieldCheck className="size-5 text-primary-foreground" aria-hidden="true" />
                            </div>
                            <span className="hidden font-semibold text-lg text-foreground lg:inline">
                                Ops Console
                            </span>
                        </Link>

                        {/* Nav Links */}
                        <nav className="flex min-w-0 items-center gap-1 overflow-x-auto">
                            <NavLink href="/ops" exact>
                                Dashboard
                            </NavLink>
                            <NavLink href="/ops/agencies">
                                <span className="flex items-center gap-1.5">
                                    <Building2 className="size-4" />
                                    Agencies
                                </span>
                            </NavLink>
                            <NavLink href="/ops/alerts">
                                <span className="flex items-center gap-1.5">
                                    <Bell className="size-4" />
                                    Alerts
                                    {openAlertCount > 0 && (
                                        <Badge
                                            variant="destructive"
                                            className="px-1.5 py-0 text-xs h-5"
                                        >
                                            {openAlertCount}
                                        </Badge>
                                    )}
                                </span>
                            </NavLink>
                            <NavLink href="/ops/templates">
                                <span className="flex items-center gap-1.5">
                                    <LayoutTemplate className="size-4" />
                                    Templates
                                </span>
                            </NavLink>
                            <NavLink href="/ops/cli">
                                <span className="flex items-center gap-1.5">
                                    <Terminal className="size-4" />
                                    CLI
                                </span>
                            </NavLink>
                        </nav>
                    </div>

                    {/* User Menu */}
                    <div className="flex shrink-0 items-center gap-4">
                        <span className="hidden text-sm text-muted-foreground md:inline">
                            {user.email}
                        </span>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={logoutFromOps}
                            aria-label="Log out"
                        >
                            <LogOut className="size-4" aria-hidden="true" />
                        </Button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="min-h-[calc(100vh-3.5rem)]">{children}</main>
        </div>
    );
}
