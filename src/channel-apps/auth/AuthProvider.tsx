/**
 * @file        AuthProvider.tsx
 * @description LINE 頻道認證提供者 - 包裝 LIFF 認證邏輯，提供頻道層級的使用者認證 Context
 * @note        LINE LIFF integration will be added in future phase. Currently returns unauthenticated default state.
 * @lastUpdate  2026-05-21 16:35:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { createContext, useContext, type ReactNode } from 'react';

export interface ChannelAuthState {
  user: { id: string; name: string; platform: 'line' | 'whatsapp' | 'dingtalk' | 'internal' } | null;
  isAuthenticated: boolean;
  isLiff: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getToken: () => string | null;
}

const defaultState: ChannelAuthState = {
  user: null,
  isAuthenticated: false,
  isLiff: false,
  login: async () => {
    // No-op: LINE LIFF integration will be implemented in a future phase
  },
  logout: async () => {
    // No-op: LINE LIFF integration will be implemented in a future phase
  },
  getToken: () => null,
};

export const ChannelAuthContext = createContext<ChannelAuthState>(defaultState);

interface ChannelAuthProviderProps {
  children: ReactNode;
}

export function ChannelAuthProvider({ children }: ChannelAuthProviderProps) {
  return (
    <ChannelAuthContext.Provider value={defaultState}>
      {children}
    </ChannelAuthContext.Provider>
  );
}

export function useChannelAuth(): ChannelAuthState {
  const ctx = useContext(ChannelAuthContext);
  if (!ctx) {
    throw new Error('useChannelAuth must be used within a ChannelAuthProvider');
  }
  return ctx;
}

export default ChannelAuthProvider;
