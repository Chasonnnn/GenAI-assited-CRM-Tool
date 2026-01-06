'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import api from '@/lib/api';

const DEV_BYPASS_AUTH = process.env.NEXT_PUBLIC_DEV_BYPASS_AUTH === 'true';

// Interface matches backend MeResponse schema
export interface User {
    user_id: string;
    email: string;
    display_name: string;
    avatar_url?: string;
    phone?: string;
    title?: string;
    org_id: string;
    org_name: string;
    org_slug: string;
    org_timezone: string;
    role: string;
    ai_enabled: boolean;
    mfa_enabled: boolean;
    mfa_required: boolean;
    mfa_verified: boolean;
}

// Mock user for testing when auth is bypassed
const MOCK_USER: User = {
    user_id: '4176661a-0bab-4e28-b44f-1591960b88bf',
    email: 'admin@test.com',
    display_name: 'Test Admin',
    avatar_url: undefined,
    org_id: 'd1f370ab-1680-46b3-a37d-7cff639e4a47',
    org_name: 'Test Organization',
    org_slug: 'test-org',
    org_timezone: 'America/Los_Angeles',
    role: 'admin',
    ai_enabled: true, // Enable AI for testing
    mfa_enabled: true,
    mfa_required: false,
    mfa_verified: true,
};

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    error: Error | null;
    refetch: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(DEV_BYPASS_AUTH ? MOCK_USER : null);
    const [isLoading, setIsLoading] = useState(!DEV_BYPASS_AUTH);
    const [error, setError] = useState<Error | null>(null);

    const fetchUser = async () => {
        if (DEV_BYPASS_AUTH) {
            setUser(MOCK_USER);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const data = await api.get<User>('/auth/me');
            setUser(data);
        } catch (err) {
            setUser(null);
            if (err instanceof Error) {
                // Don't treat 401 as error - just means not logged in
                if ('status' in err && (err as { status: number }).status === 401) {
                    setError(null);
                } else {
                    setError(err);
                }
            }
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchUser();
    }, []);

    return (
        <AuthContext.Provider value={{ user, isLoading, error, refetch: fetchUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

// Hook for protected pages
export function useRequireAuth() {
    const { user, isLoading } = useAuth();

    useEffect(() => {
        if (!DEV_BYPASS_AUTH && !isLoading && !user) {
            window.location.href = '/login';
        }
        if (
            !DEV_BYPASS_AUTH &&
            !isLoading &&
            user &&
            user.mfa_required &&
            !user.mfa_verified
        ) {
            window.location.href = '/mfa';
        }
    }, [user, isLoading]);

    return { user, isLoading };
}
