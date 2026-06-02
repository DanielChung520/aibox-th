const CACHE_KEY = 'aibox_th_theme_templates';
const CACHE_TIMESTAMP_KEY = 'aibox_th_theme_templates_ts';
const CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 小時

export function getCachedTemplates(): { templates: unknown[]; timestamp: number } | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    const ts = localStorage.getItem(CACHE_TIMESTAMP_KEY);
    if (!raw || !ts) return null;
    return { templates: JSON.parse(raw), timestamp: Number(ts) };
  } catch {
    return null;
  }
}

export function setCachedTemplates(templates: unknown[]): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(templates));
    localStorage.setItem(CACHE_TIMESTAMP_KEY, String(Date.now()));
  } catch (e) { console.debug('[offlineCache] cache write failed', e); }
}

export function isCacheValid(): boolean {
  const cached = getCachedTemplates();
  if (!cached) return false;
  return Date.now() - cached.timestamp < CACHE_TTL_MS;
}
