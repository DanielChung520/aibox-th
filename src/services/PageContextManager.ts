/**
 * @file        PageContextManager.ts
 * @description 全局頁面上下文管理器，任何組件可上報當前狀態
 */

export interface PageContextState {
  page: string;
  pageName: string;
  component?: string;
  componentName?: string;
  entity?: string;
  entityType?: string;
  action?: string;
  data?: Record<string, unknown>;
}

const listeners = new Set<(ctx: PageContextState) => void>();
let currentContext: PageContextState | null = null;

export const pageContextManager = {
  report(ctx: Partial<PageContextState>) {
    currentContext = { ...currentContext, ...ctx } as PageContextState;
    listeners.forEach(fn => fn(currentContext!));
  },

  getContext() {
    return currentContext;
  },

  subscribe(fn: (ctx: PageContextState) => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
