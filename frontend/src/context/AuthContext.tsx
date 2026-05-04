import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { User, UserRole } from '../types';

interface AuthContextValue {
  user: User | null;
  userId: string | null;
  sessionToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (user: User, userId: string, sessionToken: string) => void;
  logout: () => void;
  hasRole: (roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Rehydrate from localStorage on mount
  useEffect(() => {
    try {
      const storedUser = localStorage.getItem('hf-user');
      const storedUserId = localStorage.getItem('x-user-id');
      const storedToken = localStorage.getItem('x-session-token');

      if (storedUser && storedUserId && storedToken) {
        setUser(JSON.parse(storedUser));
        setUserId(storedUserId);
        setSessionToken(storedToken);
      }
    } catch {
      // Invalid stored data — clear it
      localStorage.removeItem('hf-user');
      localStorage.removeItem('x-user-id');
      localStorage.removeItem('x-session-token');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback((userData: User, uid: string, token: string) => {
    setUser(userData);
    setUserId(uid);
    setSessionToken(token);
    localStorage.setItem('hf-user', JSON.stringify(userData));
    localStorage.setItem('x-user-id', uid);
    localStorage.setItem('x-session-token', token);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setUserId(null);
    setSessionToken(null);
    localStorage.removeItem('hf-user');
    localStorage.removeItem('x-user-id');
    localStorage.removeItem('x-session-token');
  }, []);

  const hasRole = useCallback(
    (roles: UserRole[]) => {
      if (!user) return false;
      return roles.includes(user.role);
    },
    [user]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        userId,
        sessionToken,
        isAuthenticated: !!user && !!sessionToken,
        isLoading,
        login,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}
