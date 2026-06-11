/**
 * @file        統一主題供應器
 * @description DB 驅動的主題系統，分離 Shell（固定深色）與 Content（可切換）兩層
 * @lastUpdate  2026-03-25 14:42:53
 * @author      Daniel Chung
 * @version     2.1.0
 */

import { createContext, useState, useEffect, useContext, useCallback, ReactNode } from 'react';
import { themeTemplateApi, ShellTokens, ContentTokens, ThemeTemplate } from '../services/api';
import {
  DEFAULT_SHELL_TOKENS,
  DEFAULT_CONTENT_LIGHT_TOKENS,
  DEFAULT_CONTENT_DARK_TOKENS,
} from '../styles/theme/tokens';
import { getCachedTemplates, setCachedTemplates } from '../services/offlineCache';

export type ThemeMode = 'light' | 'dark' | 'system';
export type EffectiveTheme = 'light' | 'dark';

interface ThemeContextValue {
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  effectiveTheme: EffectiveTheme;
  shellTokens: ShellTokens;
  contentTokens: ContentTokens;
  reloadTemplates: () => Promise<void>;
}

const defaultCtx: ThemeContextValue = {
  themeMode: 'system',
  setThemeMode: () => {},
  effectiveTheme: 'dark',
  shellTokens: DEFAULT_SHELL_TOKENS,
  contentTokens: DEFAULT_CONTENT_DARK_TOKENS,
  reloadTemplates: async () => {},
};

export const ThemeContext = createContext<ThemeContextValue>(defaultCtx);

function resolveEffective(mode: ThemeMode): EffectiveTheme {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return mode;
}

function pickContentTokens(
  templates: ThemeTemplate[],
  effective: EffectiveTheme,
): ContentTokens {
  const key = effective === 'dark' ? 'content.dark' : 'content.light';
  const found = templates.find(t => t._key === key && t.template_type === 'content');
  const defaults = effective === 'dark' ? DEFAULT_CONTENT_DARK_TOKENS : DEFAULT_CONTENT_LIGHT_TOKENS;
  if (found) return { ...defaults, ...found.tokens } as ContentTokens;
  return defaults;
}

function pickShellTokens(templates: ThemeTemplate[]): ShellTokens {
  const found = templates.find(t => t._key === 'shell.default' && t.template_type === 'shell');
  if (found) return found.tokens as ShellTokens;
  return DEFAULT_SHELL_TOKENS;
}

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [themeMode, setThemeModeRaw] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('theme-mode');
    return (stored as ThemeMode) || 'system';
  });
  const [effectiveTheme, setEffectiveTheme] = useState<EffectiveTheme>(() =>
    resolveEffective(themeMode),
  );
  const [templates, setTemplates] = useState<ThemeTemplate[]>(() => {
    const cached = getCachedTemplates();
    return cached ? (cached.templates as ThemeTemplate[]) : [];
  });

  const loadTemplates = useCallback(async () => {
    try {
      const res = await themeTemplateApi.list();
      const data = res.data.data || [];
      setTemplates(data);
      setCachedTemplates(data);
    } catch (e) { void e; }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const setThemeMode = useCallback((mode: ThemeMode) => {
    setThemeModeRaw(mode);
    localStorage.setItem('theme-mode', mode);
  }, []);

  useEffect(() => {
    setEffectiveTheme(resolveEffective(themeMode));
  }, [themeMode]);

  useEffect(() => {
    if (themeMode !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) =>
      setEffectiveTheme(e.matches ? 'dark' : 'light');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [themeMode]);

  const shellTokens = pickShellTokens(templates);
  const contentTokens = pickContentTokens(templates, effectiveTheme);

  return (
    <ThemeContext.Provider
      value={{
        themeMode,
        setThemeMode,
        effectiveTheme,
        shellTokens,
        contentTokens,
        reloadTemplates: loadTemplates,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useEffectiveTheme(): EffectiveTheme {
  return useContext(ThemeContext).effectiveTheme;
}

export function useThemeMode(): [ThemeMode, (mode: ThemeMode) => void] {
  const ctx = useContext(ThemeContext);
  return [ctx.themeMode, ctx.setThemeMode];
}

export function useShellTokens(): ShellTokens {
  return useContext(ThemeContext).shellTokens;
}

export function useContentTokens(): ContentTokens {
  return useContext(ThemeContext).contentTokens;
}

export function useReloadTemplates(): () => Promise<void> {
  return useContext(ThemeContext).reloadTemplates;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
