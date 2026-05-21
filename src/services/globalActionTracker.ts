/**
 * @file        globalActionTracker.ts
 * @description 全局 DOM 操作監聽器 — 自動捕捉全站使用者交互行為，
 *              記錄到 ActionTrail 作為艾企助手的操作上下文。
 * @lastUpdate  2026-05-15
 * @author      AI Agent
 * @version     1.0.0
 */

import { actionTrail } from './actionTrail';
import type { ActionEventType } from './actionTrail';

interface ClickMeta {
  tagName: string;
  id: string;
  className: string;
  textContent: string;
  ariaLabel: string;
  dataAttrs: Record<string, string>;
}

interface FocusMeta {
  placeholder: string;
  name: string;
  id: string;
  type: string;
}

let clickHandler: ((e: MouseEvent) => void) | null = null;
let focusHandler: ((e: FocusEvent) => void) | null = null;
let visibilityHandler: (() => void) | null = null;
let mutationObserver: MutationObserver | null = null;

const lastClickMap = new WeakMap<Element, number>();
const CLICK_DEBOUNCE_MS = 200;

let rowSelectPending = false;
let mutationDebounceTimer: ReturnType<typeof setTimeout> | null = null;
const MUTATION_DEBOUNCE_MS = 300;

function truncateText(text: string, max = 50): string {
  return text.replace(/\s+/g, ' ').trim().slice(0, max);
}

function collectDataAttrs(el: Element): Record<string, string> {
  const attrs: Record<string, string> = {};
  for (const attr of el.attributes) {
    if (attr.name.startsWith('data-')) {
      attrs[attr.name] = attr.value;
    }
  }
  return attrs;
}

function createClickHandler(): (e: MouseEvent) => void {
  return (e: MouseEvent) => {
    const target = e.target as Element | null;
    if (!target) return;

    if (target.hasAttribute('data-at-tracked')) return;

    const now = Date.now();
    const lastClick = lastClickMap.get(target);
    if (lastClick && now - lastClick < CLICK_DEBOUNCE_MS) return;
    lastClickMap.set(target, now);

    const meta: ClickMeta = {
      tagName: target.tagName,
      id: target.id || '',
      className: target.className?.toString() || '',
      textContent: truncateText(target.textContent ?? ''),
      ariaLabel: (target as HTMLElement).ariaLabel || target.getAttribute('aria-label') || '',
      dataAttrs: collectDataAttrs(target),
    };

    actionTrail.record(
      'click' as ActionEventType,
      meta as unknown as Record<string, unknown>,
    );
  };
}

function createFocusHandler(): (e: FocusEvent) => void {
  return (e: FocusEvent) => {
    const target = e.target as HTMLElement | null;
    if (!target) return;

    const tagName = target.tagName.toLowerCase();
    if (tagName !== 'input' && tagName !== 'textarea' && tagName !== 'select') {
      return;
    }

    if (tagName === 'input') {
      const input = target as HTMLInputElement;
      if (input.type === 'password') return;
    }

    const meta: FocusMeta = {
      placeholder:
        (target as HTMLInputElement | HTMLTextAreaElement).placeholder ?? '',
      name: (target as HTMLInputElement | HTMLTextAreaElement).name ?? '',
      id: target.id ?? '',
      type: (target as HTMLInputElement).type || tagName,
    };

    actionTrail.record(
      'input_focus' as ActionEventType,
      meta as unknown as Record<string, unknown>,
    );
  };
}

function createVisibilityHandler(): () => void {
  return () => {
    if (document.visibilityState === 'visible') {
      actionTrail.record('page_navigate', { source: 'visibilitychange' });
    }
  };
}

function createMutationObserver(): MutationObserver {
  return new MutationObserver((mutations) => {
    const hasSelectedRow = mutations.some((mutation) =>
      Array.from(mutation.addedNodes).some((node) => {
        if (!(node instanceof Element)) return false;
        return (
          node.matches?.('.ant-table-row.ant-table-row-selected') ??
          node.querySelector?.('.ant-table-row.ant-table-row-selected') != null
        );
      }),
    );

    if (!hasSelectedRow || rowSelectPending) return;

    rowSelectPending = true;
    mutationDebounceTimer = setTimeout(() => {
      const selectedRow = document.querySelector(
        '.ant-table-row.ant-table-row-selected',
      );
      if (selectedRow) {
        const table =
          selectedRow.closest?.('.ant-table') ??
          selectedRow.closest?.('table');
        actionTrail.record(
          'row_select' as ActionEventType,
          { tableClassName: table?.className?.toString() ?? '' },
        );
      }
      rowSelectPending = false;
      mutationDebounceTimer = null;
    }, MUTATION_DEBOUNCE_MS);
  });
}

/**
 * Start global DOM event tracking.
 *
 * Attaches passive listeners for click / focusin / visibilitychange and
 * a MutationObserver for table row selection.  Safe to call multiple times —
 * subsequent calls are no-ops.
 */
export function startGlobalTracking(): void {
  if (clickHandler) return;

  clickHandler = createClickHandler();
  document.addEventListener('click', clickHandler, { passive: true });

  focusHandler = createFocusHandler();
  document.addEventListener('focusin', focusHandler, { passive: true });

  visibilityHandler = createVisibilityHandler();
  document.addEventListener('visibilitychange', visibilityHandler);

  mutationObserver = createMutationObserver();
  mutationObserver.observe(document.body, {
    childList: true,
    subtree: true,
  });
}

/**
 * Stop global DOM event tracking and release all resources.
 *
 * Removes all event listeners, disconnects the MutationObserver, and clears
 * any pending debounce timers.  Safe to call even if tracking was never started.
 */
export function stopGlobalTracking(): void {
  if (clickHandler) {
    document.removeEventListener('click', clickHandler);
    clickHandler = null;
  }

  if (focusHandler) {
    document.removeEventListener('focusin', focusHandler);
    focusHandler = null;
  }

  if (visibilityHandler) {
    document.removeEventListener('visibilitychange', visibilityHandler);
    visibilityHandler = null;
  }

  if (mutationObserver) {
    mutationObserver.disconnect();
    mutationObserver = null;
  }

  if (mutationDebounceTimer) {
    clearTimeout(mutationDebounceTimer);
    mutationDebounceTimer = null;
  }
  rowSelectPending = false;
}
