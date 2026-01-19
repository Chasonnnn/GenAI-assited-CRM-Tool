/**
 * API client for system metadata (health, version).
 */

import { api } from '../api';

export interface SystemHealth {
    status: string;
    env?: string;
    version?: string;
}

export function getSystemHealth(): Promise<SystemHealth> {
    return api.get<SystemHealth>('/health');
}
