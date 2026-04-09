"use client";

import React, { createContext, useContext, useMemo, useState } from 'react';

import { getStoredAuthRole, getStoredTenantId, getStoredUserId } from '@/services/auth';

type AuthUser = { id: string; tenantId: string; roles: string[] };
type AuthContextValue = { user: AuthUser | null; isAuthenticated: boolean; refresh: () => void };

const AuthContext = createContext<AuthContextValue>({ user: null, isAuthenticated: false, refresh: () => undefined });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((v) => v + 1);
  const value = useMemo<AuthContextValue>(() => {
    const role = getStoredAuthRole();
    const userId = getStoredUserId();
    const tenantId = getStoredTenantId();
    if (!role || !userId || !tenantId) return { user: null, isAuthenticated: false, refresh };
    return { user: { id: userId, tenantId, roles: [role] }, isAuthenticated: true, refresh };
  }, [version]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { return useContext(AuthContext); }
