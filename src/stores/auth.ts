/**
 * @file        認證狀態管理
 * @description 自定義 AuthStore，用於管理用戶登入狀態、訂閱機制
 * @lastUpdate  2026-03-17 23:27:55
 * @author      Daniel Chung
 * @version     1.0.0
 * @history
 * - 2026-03-17 23:27:55 | Daniel Chung | 1.0.0 | 初始版本
 */

import { LoginResponse, paramsApi } from '../services/api';

interface AuthState {
  user: LoginResponse['user'] | null;
  token: string | null;
  isAuthenticated: boolean;
}

class AuthStore {
  private state: AuthState = {
    user: null,
    token: localStorage.getItem('token'),
    isAuthenticated: !!localStorage.getItem('token'),
  };

  private listeners: Set<() => void> = new Set();

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  getState() {
    return this.state;
  }

  getSavedUsername(): string | null {
    return localStorage.getItem('saved_username');
  }

  getSavedPassword(): string | null {
    const encrypted = localStorage.getItem('saved_password');
    if (!encrypted) return null;
    try {
      return atob(encrypted);
    } catch {
      return null;
    }
  }

  getLastLogoutTime(): number | null {
    const time = localStorage.getItem('last_logout_time');
    return time ? parseInt(time, 10) : null;
  }

  login(user: LoginResponse['user'], token: string, remember?: boolean, password?: string) {
    this.state = { user, token, isAuthenticated: true };
    localStorage.setItem('token', token);
    
    if (remember) {
      localStorage.setItem('saved_username', user.username);
      if (password) {
        localStorage.setItem('saved_password', btoa(password));
      }
    }
    
    localStorage.removeItem('last_logout_time');
    this.notify();
  }

  logout() {
    this.state = { user: null, token: null, isAuthenticated: false };
    localStorage.removeItem('token');
    localStorage.setItem('last_logout_time', Date.now().toString());
    
    const remember = localStorage.getItem('saved_username');
    if (remember) {
      localStorage.removeItem('saved_username');
      localStorage.removeItem('saved_password');
    }
    
    this.notify();
  }

  async canAutoLogin(): Promise<boolean> {
    const lastLogout = this.getLastLogoutTime();
    if (!lastLogout) return false;
    
    const savedPassword = this.getSavedPassword();
    if (!savedPassword) return false;
    
    const savedUsername = this.getSavedUsername();
    if (!savedUsername) return false;
    
    try {
      const enabledResponse = await paramsApi.get('autoLogin.enabled');
      const enabled = enabledResponse.data?.data?.param_value === 'true';
      if (!enabled) return false;
      
      const daysResponse = await paramsApi.get('autoLogin.days');
      const autoLoginDays = parseInt(daysResponse.data?.data?.param_value || '2', 10);
      const autoLoginMs = autoLoginDays * 24 * 60 * 60 * 1000;
      const now = Date.now();
      
      return (now - lastLogout) < autoLoginMs;
    } catch {
      const autoLoginDays = 2;
      const autoLoginMs = autoLoginDays * 24 * 60 * 60 * 1000;
      const now = Date.now();
      
      return (now - lastLogout) < autoLoginMs;
    }
  }

  async getAutoLoginCredentials(): Promise<{ username: string; password: string } | null> {
    const canLogin = await this.canAutoLogin();
    if (!canLogin) return null;
    
    const username = this.getSavedUsername();
    const password = this.getSavedPassword();
    
    if (username && password) {
      return { username, password };
    }
    return null;
  }

  private notify() {
    this.listeners.forEach(listener => listener());
  }
}

export const authStore = new AuthStore();
