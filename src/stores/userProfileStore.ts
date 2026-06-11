/**
 * @file        使用者 Profile 狀態管理
 * @description 管理 AIQ UserProfileSummary 的拉取、快取與訂閱機制。
 *              Login 時從後端拉取 → localStorage 快取 → 提供 user_prior 給 Perception。
 * @lastUpdate  2026-04-18 20:12:58
 * @author      Daniel Chung
 * @version     1.0.0
 */

import api from '../services/api';

const STORAGE_KEY = 'aiq_user_profile';

export interface Pattern {
  context_signature: string;
  execution_path: string;
  success_rate: number;
  sample_count: number;
}

export interface QueryPatterns {
  frequent_intents: string[];
  avg_clarification_rounds: number;
  preferred_response_depth: 'brief' | 'detailed';
}

export interface UserProfileSummary {
  user_key: string;
  last_updated: number;
  total_turns: number;
  domain_counts: Record<string, number>;
  domain_distribution: Record<string, number>;
  query_patterns: QueryPatterns;
  success_patterns: Pattern[];
  failure_patterns: Pattern[];
}

export interface UserPrior {
  active_domains: Record<string, number>;
  frequent_queries: string[];
  skill_level: 'beginner' | 'intermediate' | 'advanced';
}

function profileToUserPrior(profile: UserProfileSummary): UserPrior {
  const totalSamples = profile.success_patterns.reduce((sum, p) => sum + p.sample_count, 0)
    + profile.failure_patterns.reduce((sum, p) => sum + p.sample_count, 0);

  let skillLevel: UserPrior['skill_level'] = 'beginner';
  if (totalSamples > 100) {
    skillLevel = 'advanced';
  } else if (totalSamples > 20) {
    skillLevel = 'intermediate';
  }

  return {
    active_domains: { ...profile.domain_distribution },
    frequent_queries: [...profile.query_patterns.frequent_intents],
    skill_level: skillLevel,
  };
}

function createEmptyProfile(userKey: string): UserProfileSummary {
  return {
    user_key: userKey,
    last_updated: 0,
    total_turns: 0,
    domain_counts: {},
    domain_distribution: {},
    query_patterns: {
      frequent_intents: [],
      avg_clarification_rounds: 0,
      preferred_response_depth: 'brief',
    },
    success_patterns: [],
    failure_patterns: [],
  };
}

class UserProfileStore {
  private profile: UserProfileSummary | null = null;
  private listeners: Set<() => void> = new Set();

  constructor() {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) {
      try {
        this.profile = JSON.parse(cached) as UserProfileSummary;
      } catch (err: unknown) {
        console.warn('[UserProfileStore] Failed to parse cached profile, clearing', err);
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  getProfile(): UserProfileSummary | null {
    return this.profile;
  }

  getUserPrior(): UserPrior | null {
    if (!this.profile) return null;
    return profileToUserPrior(this.profile);
  }

  async load(userKey: string): Promise<void> {
    try {
      const response = await api.get<UserProfileSummary>(
        '/api/v1/aiq/user-profile',
      );
      const data = response.data;
      if (data && data.user_key) {
        this.profile = data;
      } else {
        this.profile = createEmptyProfile(userKey);
      }
    } catch (err: unknown) {
      console.warn('[UserProfileStore] Failed to load profile, using empty', err);
      this.profile = createEmptyProfile(userKey);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.profile));
    this.notify();
  }

  async reload(): Promise<void> {
    if (!this.profile) return;
    await this.load(this.profile.user_key);
  }

  clear(): void {
    this.profile = null;
    localStorage.removeItem(STORAGE_KEY);
    this.notify();
  }

  private notify(): void {
    this.listeners.forEach(listener => listener());
  }
}

export const userProfileStore = new UserProfileStore();
