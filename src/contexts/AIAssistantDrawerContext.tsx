/**
 * @file        AI Assistant Drawer 狀態管理
 * @description 控制 AI Assistant Drawer 的開啟/關閉與當前視圖狀態
 * @lastUpdate  2026-06-15 10:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { createContext, useState, useContext, useCallback, ReactNode } from 'react';

export type DrawerView = 'chat' | 'intentHistory' | 'actionTrail';

interface DrawerContextValue {
  isOpen: boolean;
  activeView: DrawerView;
  open: () => void;
  close: () => void;
  toggle: () => void;
  setActiveView: (view: DrawerView) => void;
}

const defaultCtx: DrawerContextValue = {
  isOpen: false,
  activeView: 'chat',
  open: () => {},
  close: () => {},
  toggle: () => {},
  setActiveView: () => {},
};

export const AIAssistantDrawerContext = createContext<DrawerContextValue>(defaultCtx);

export function AIAssistantDrawerProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeView, setActiveViewState] = useState<DrawerView>('chat');

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen(prev => !prev), []);
  const setActiveView = useCallback((view: DrawerView) => setActiveViewState(view), []);

  return (
    <AIAssistantDrawerContext.Provider
      value={{ isOpen, activeView, open, close, toggle, setActiveView }}
    >
      {children}
    </AIAssistantDrawerContext.Provider>
  );
}

export function useAIAssistantDrawer(): DrawerContextValue {
  return useContext(AIAssistantDrawerContext);
}
