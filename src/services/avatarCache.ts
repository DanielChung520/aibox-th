/**
 * @file        avatarCache.ts
 * @description Avatar 請求快取 — 確保多個元件共用同一筆請求，避免 4 次重複的 GET /system-params/basic.avatar
 *              若 basic.avatar 尚未設定，直接 resolve undefined 不發 request
 * @lastUpdate  2026-05-30 14:00:00
 * @author      Sisyphus
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { paramsApi, type SystemParam } from './api';

const avatarModules = import.meta.glob<{ default: string }>(
  '../assets/avatar/*.png',
  { eager: true }
);

export function resolveAvatarSrc(name: string | undefined): string | undefined {
  if (!name) return undefined;
  const entry = Object.entries(avatarModules).find(([path]) => {
    const filename = path.split('/').pop() || '';
    return filename.replace(/\.png$/i, '') === name;
  });
  return entry ? entry[1].default : undefined;
}

// ── Module-level cache ─────────────────────────────────────────────
// 所有元件共用同一份 cache，只發一次 HTTP request
type CacheState =
  | { status: 'idle' }
  | { status: 'loading'; promise: Promise<string | undefined> }
  | { status: 'done'; value: string | undefined };

let cache: CacheState = { status: 'idle' };

/**
 * 取得 basic.avatar 的參數值（頭像名稱）。
 * - 模組層級快取，整份應用只發一次 request
 * - 若尚未設定，回傳 undefined（不報錯）
 * - 外部可傳入 paramsList 跳過個別 request（例如 SystemParams 頁面已有完整清單）
 */
export function getAvatarName(paramsList?: SystemParam[]): Promise<string | undefined> {
  // 若外部已提供完整 params list，直接從中查找
  if (paramsList) {
    const avatarParam = paramsList.find(p => p.param_key === 'basic.avatar');
    return Promise.resolve(avatarParam?.param_value);
  }

  // 已快取
  if (cache.status === 'done') {
    return Promise.resolve(cache.value);
  }

  // 已在 loading
  if (cache.status === 'loading') {
    return cache.promise;
  }

  // 首次呼叫 — 發 request
  const promise = paramsApi.get('basic.avatar')
    .then(res => {
      const value = res.data?.data?.param_value;
      cache = { status: 'done', value };
      return value;
    })
    .catch(() => {
      cache = { status: 'done', value: undefined };
      return undefined;
    });

  cache = { status: 'loading', promise };
  return promise;
}

/**
 * 清除快取（當 avatar 被更新時呼叫，讓下次 mount 重新取得）
 */
export function clearAvatarCache(): void {
  cache = { status: 'idle' };
}

/**
 * React Hook — 在元件內使用 avatar
 * 第一次 mount 時發 request，後續沿用快取
 */
export function useAvatar(paramsList?: SystemParam[]): string | undefined {
  const [avatarName, setAvatarName] = useState<string | undefined>(() => {
    // 若 paramsList 已有資料，同步初始化
    if (paramsList) {
      return paramsList.find(p => p.param_key === 'basic.avatar')?.param_value;
    }
    // 若已快取過，同步初始化
    if (cache.status === 'done') {
      return cache.value;
    }
    return undefined;
  });
  const [avatarSrc, setAvatarSrc] = useState<string | undefined>(() =>
    avatarName ? resolveAvatarSrc(avatarName) : undefined
  );

  useEffect(() => {
    let cancelled = false;

    if (paramsList) {
      // paramsList 來自外部，不需要發 request
      const name = paramsList.find(p => p.param_key === 'basic.avatar')?.param_value;
      if (!cancelled) {
        setAvatarName(name);
        setAvatarSrc(resolveAvatarSrc(name));
      }
      return;
    }

    getAvatarName().then(name => {
      if (!cancelled) {
        setAvatarName(name);
        setAvatarSrc(resolveAvatarSrc(name));
      }
    });

    // 監聽 avatar-changed 事件
    const handleAvatarChanged = (e: Event) => {
      const name = (e as CustomEvent).detail?.name;
      if (!cancelled) {
        setAvatarName(name);
        setAvatarSrc(resolveAvatarSrc(name));
      }
      // 清除快取讓下次有機會重新取得
      clearAvatarCache();
    };
    window.addEventListener('avatar-changed', handleAvatarChanged);

    return () => {
      cancelled = true;
      window.removeEventListener('avatar-changed', handleAvatarChanged);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return avatarSrc;
}
