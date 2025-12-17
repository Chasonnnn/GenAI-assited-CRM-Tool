'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import api from '@/lib/api';

// TEMPORARY: Set to true to bypass auth for testing
const DEV_BYPASS_AUTH = true;

// Interface matches backend MeResponse schema
interface User {
    user_id: string;
    email: string;
    display_name: string;
    avatar_url?: string;
    org_id: string;
    org_name: string;
    org_slug: string;
    role: string;
    ai_enabled: boolean;
}

// Mock user for testing when auth is bypassed
const MOCK_USER: User = {
    user_id: '4176661a-0bab-4e28-b44f-1591960b88bf',
    email: 'manager@test.com',
    display_name: 'Test Manager',
    avatar_url: undefined,
    org_id: 'd1f370ab-1680-46b3-a37d-7cff639e4a47',
    org_name: 'Test Organization',
    org_slug: 'test-org',
    role: 'manager',
    ai_enabled: true, // Enable AI for testing
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
    }, [user, isLoading]);

    return { user, isLoading };
}

