/**
 * @file        favoriteStore.ts
 * @description Sidebar 功能收藏與使用次數狀態管理（localStorage 持久化）
 *              提供收藏 toggle、使用次數累加、查詢功能
 * @lastUpdate  2026-06-22 14:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

const STORAGE_KEY = 'sidebar_favorites';

interface SidebarFavorites {
  favoriteCodes: string[];
  usageCounts: Record<string, number>;
}

class FavoriteStore {
  private data: SidebarFavorites = { favoriteCodes: [], usageCounts: {} };

  constructor() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        this.data = JSON.parse(stored);
      }
    } catch {
      /* ignore parse errors */
    }
  }

  private save(): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
  }

  incrementUsage(code: string): void {
    this.data.usageCounts[code] = (this.data.usageCounts[code] || 0) + 1;
    this.save();
  }

  toggleFavorite(code: string): void {
    const idx = this.data.favoriteCodes.indexOf(code);
    if (idx >= 0) {
      this.data.favoriteCodes.splice(idx, 1);
    } else {
      this.data.favoriteCodes.push(code);
    }
    this.save();
  }

  isFavorite(code: string): boolean {
    return this.data.favoriteCodes.includes(code);
  }

  getUsageCount(code: string): number {
    return this.data.usageCounts[code] || 0;
  }

  getFavoriteCodes(): string[] {
    return [...this.data.favoriteCodes];
  }

  clear(): void {
    this.data = { favoriteCodes: [], usageCounts: {} };
    localStorage.removeItem(STORAGE_KEY);
  }
}

export const favoriteStore = new FavoriteStore();
