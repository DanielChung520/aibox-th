/**
 * @file        主佈局元件
 * @description 應用主佈局，包含側邊欄導航、Header、使用者資訊下拉選單
 * @lastUpdate  2026-03-25 17:30:00
 * @author      Daniel Chung
 * @version     1.0.1
 */

import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, ConfigProvider, theme } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  LoadingOutlined,
  StarOutlined,
} from '@ant-design/icons';
import { authStore } from '../stores/auth';
import { authApi, functionApi, paramsApi, Function } from '../services/api';
import { favoriteStore } from '../stores/favoriteStore';
import { iconMap } from '../utils/icons';
import { useThemeMode, useShellTokens, useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';
import AppLogo from '../components/AppLogo';
import HeaderControls from '../components/HeaderControls';
import { signalCollector } from '../services/signalCollector';
import { userProfileStore } from '../stores/userProfileStore';
import { useAIAssistantDrawer } from '../contexts/AIAssistantDrawerContext';

const { Header, Sider, Content } = Layout;

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const { isOpen: isDrawerOpen } = useAIAssistantDrawer();

  const [user, setUser] = useState(authStore.getState().user);
  const [functions, setFunctions] = useState<Function[]>([]);
  const [appLogo, setAppLogo] = useState('');

  // ── Context menu for favorite toggle ──
  const [ctxTarget, setCtxTarget] = useState<{ code: string; x: number; y: number } | null>(null);

  const PREFIX_FAV = '__fav_';
  const PREFIX_FREQ = '__freq_';

  const shellTokens = useShellTokens();
  const contentTokens = useContentTokens();
  const [, setThemeMode] = useThemeMode();
  const effectiveTheme = useEffectiveTheme();

  const isDark = effectiveTheme === 'dark';
  const siderBg = shellTokens.siderBg;
  const headerBg = shellTokens.headerBg;
  const textColor = shellTokens.logoColor;
  const primaryColor = contentTokens.colorPrimary;
  const contentBg = contentTokens.contentBg || contentTokens.colorBgBase;
  const tooltipBgRaw = contentTokens.tooltipBg || contentTokens.containerBg || contentTokens.colorBgBase || '#1e293b';
  const tooltipBgOpacity = (contentTokens.tooltipBgOpacity ?? 88) / 100;
  const tooltipBg = tooltipBgRaw.startsWith('#') && tooltipBgRaw.length === 7
    ? `${tooltipBgRaw}${Math.round(tooltipBgOpacity * 255).toString(16).padStart(2, '0')}`
    : tooltipBgRaw;

  useEffect(() => {
    void signalCollector.start();
    return () => { signalCollector.stop(); };
  }, []);

  // ── Auto-collapse sidebar when AI Assistant Drawer opens ──
  useEffect(() => {
    if (isDrawerOpen && !collapsed) {
      setCollapsed(true);
    }
  }, [isDrawerOpen]);

  useEffect(() => {
    const unsubscribe = authStore.subscribe(() => {
      setUser(authStore.getState().user);
    });
    if (!authStore.getState().user && authStore.getState().token) {
      authApi.me().then((res: any) => {
        if (res.data.code === 200) {
          const userData = res.data.data;
          authStore.login(userData, authStore.getState().token!);
          setUser(userData);
          void userProfileStore.load(userData._key);
        }
      }).catch(() => {});
    } else if (authStore.getState().user) {
      void userProfileStore.load(authStore.getState().user!._key);
    }
    return unsubscribe;
  }, []);

  useEffect(() => {
    functionApi.getAuthorized()
      .then(res => setFunctions(res.data.data || []))
      .catch(() => setFunctions([]));
  }, []);

  useEffect(() => {
    paramsApi.list().then((res: any) => {
      const params = res.data.data || [];
      const logo = params.find((p: any) => p.param_key === 'app.logo');
      if (logo?.param_value) setAppLogo(logo.param_value);
    }).catch(() => {});
  }, []);

  const buildIcon = (iconName: string | null) => {
    if (!iconName || !iconMap[iconName]) return <SettingOutlined />;
    return React.createElement(iconMap[iconName]);
  };

  const menuItems = (() => {
    if (functions.length === 0) {
      return [{ key: 'loading', icon: <LoadingOutlined />, label: '載入中...', disabled: true }];
    }

    const setCtx = (e: React.MouseEvent, code: string) => {
      e.preventDefault();
      e.stopPropagation();
      setCtxTarget({ code, x: e.clientX, y: e.clientY });
    };

    const topGroups = functions
      .filter(f => f.function_type === 'group' && f.status === 'enabled')
      .sort((a, b) => a.sort_order - b.sort_order);

    // ── Build quick-access sections ──
    const enabledSubs = functions.filter(
      f => f.function_type === 'sub_function' && f.status === 'enabled',
    );

    const favItems = enabledSubs
      .filter(f => favoriteStore.isFavorite(f.code))
      .map(f => ({
        key: `${PREFIX_FAV}${f.path || f.code}`,
        icon: buildIcon(f.icon),
        label: (
          <span onContextMenu={(e) => setCtx(e, f.code)}>
            {f.name}
          </span>
        ),
      }));

    const freqItems = enabledSubs
      .filter(
        f =>
          !favoriteStore.isFavorite(f.code) &&
          favoriteStore.getUsageCount(f.code) > 10,
      )
      .sort(
        (a, b) =>
          favoriteStore.getUsageCount(b.code) -
          favoriteStore.getUsageCount(a.code),
      )
      .slice(0, 5)
      .map(f => ({
        key: `${PREFIX_FREQ}${f.path || f.code}`,
        icon: buildIcon(f.icon),
        label: (
          <span onContextMenu={(e) => setCtx(e, f.code)}>
            {f.name}
          </span>
        ),
      }));

    const result: any[] = [];

    if (favItems.length > 0) {
      result.push({
        type: 'group',
        label: '⭐ 我的收藏',
        key: `${PREFIX_FAV}section`,
        children: favItems,
      });
    }

    if (freqItems.length > 0) {
      result.push({
        type: 'group',
        label: '🔥 我的常用',
        key: `${PREFIX_FREQ}section`,
        children: freqItems,
      });
    }

    if (result.length > 0) {
      result.push({ type: 'divider', key: '__quick_divider' });
    }

    // ── Regular function groups ──
    topGroups.forEach(group => {
      const subs = functions
        .filter(
          f =>
            f.function_type === 'sub_function' &&
            f.parent_key === group.code &&
            f.status === 'enabled',
        )
        .sort((a, b) => a.sort_order - b.sort_order);

      const item: any = {
        key: group.path || group.code,
        icon: buildIcon(group.icon),
        label: (
          <span onContextMenu={(e) => setCtx(e, group.code)}>
            {group.name}
          </span>
        ),
      };

      if (subs.length > 0) {
        item.children = subs.map(sub => ({
          key: sub.path || sub.code,
          label: (
            <span onContextMenu={(e) => setCtx(e, sub.code)}>
              {sub.name}
            </span>
          ),
        }));
      } else if (group.path) {
        item.onClick = () => navigate(group.path!);
      }

      result.push(item);
    });

    return result;
  })();

  const handleMenuClick = ({ key }: { key: string }) => {
    const cleanKey = key.startsWith(PREFIX_FAV)
      ? key.slice(PREFIX_FAV.length)
      : key.startsWith(PREFIX_FREQ)
        ? key.slice(PREFIX_FREQ.length)
        : key;
    const item = functions.find(f => (f.path || f.code) === cleanKey);
    if (item?.path) {
      navigate(item.path);
      favoriteStore.incrementUsage(item.code);
    } else if (cleanKey.startsWith('/')) {
      navigate(cleanKey);
    }
  };

  const handleLogout = () => {
    userProfileStore.clear();
    favoriteStore.clear();
    authStore.logout();
    navigate('/login');
  };

  const toggleTheme = () => {
    setThemeMode(isDark ? 'light' : 'dark');
  };

  const getPageInfo = () => {
    const path = location.pathname;
    const func = functions.find(f => f.path === path);
    if (func) return { title: func.name, desc: func.description || '' };
    if (path.includes('users')) return { title: '账户管理', desc: '使用者帳號管理' };
    if (path.includes('roles')) return { title: '角色管理', desc: '角色與權限設定' };
    if (path.includes('params')) return { title: '系統參數', desc: '系統配置與設定' };
    return { title: '首页', desc: '' };
  };

  const pageInfo = getPageInfo();

  return (
    <Layout style={{ minHeight: '100vh', background: contentTokens.pageBg || shellTokens.headerBg, display: 'flex', flexDirection: 'row' }}>
      <ConfigProvider
        theme={{
          algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: { colorPrimary: contentTokens.colorPrimary },
          components: {
            Menu: {
              darkItemBg: shellTokens.siderBg,
              darkItemColor: shellTokens.menuItemColor,
              darkItemHoverBg: shellTokens.menuItemHoverBg,
              darkItemSelectedBg: shellTokens.menuItemSelectedBg,
              darkItemSelectedColor: shellTokens.menuItemSelectedColor,
            },
            Tooltip: {
              colorBgSpotlight: tooltipBg,
            },
          },
        }}
      >
        <Sider trigger={null} collapsible collapsed={collapsed} collapsedWidth={64} width={200} style={{ background: siderBg }}>
          <div style={{
            height: 65,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: `1px solid ${shellTokens.siderBorder}`,
            color: textColor,
          }}>
            <AppLogo logo={appLogo} collapsed={collapsed} textColor={textColor} borderColor={shellTokens.siderBorder} />
          </div>

          <Menu
            mode="inline"
            theme="dark"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => handleMenuClick({ key })}
            style={{ borderRight: 0, background: 'transparent' }}
          />

          {ctxTarget && (
            <>
              <div
                style={{ position: 'fixed', inset: 0, zIndex: 1050 }}
                onClick={() => setCtxTarget(null)}
                onContextMenu={(e) => { e.preventDefault(); setCtxTarget(null); }}
              />
              <div
                style={{
                  position: 'fixed',
                  top: ctxTarget.y,
                  left: ctxTarget.x,
                  zIndex: 1060,
                  background: isDark ? '#1e293b' : '#fff',
                  borderRadius: 6,
                  boxShadow: '0 6px 16px 0 rgba(0,0,0,0.08), 0 3px 6px -4px rgba(0,0,0,0.12)',
                  padding: '4px 0',
                  minWidth: 140,
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div
                  onClick={() => {
                    favoriteStore.toggleFavorite(ctxTarget.code);
                    setCtxTarget(null);
                  }}
                  style={{
                    padding: '5px 12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 13,
                    color: isDark ? '#e2e8f0' : '#333',
                    borderRadius: 4,
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = isDark ? '#334155' : '#f0f0f0'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <StarOutlined style={{ fontSize: 14 }} />
                  {favoriteStore.isFavorite(ctxTarget.code) ? '取消收藏' : '加入收藏'}
                </div>
              </div>
            </>
          )}

          <div style={{
            position: 'absolute', bottom: 16, left: 0, right: 0,
            textAlign: 'center', color: contentTokens.textSecondary, fontSize: '12px',
          }}>
            v1.0.0
          </div>
        </Sider>

        <Layout>
          <Header style={{
            padding: '0 16px',
            background: headerBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${shellTokens.siderBorder}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Button
                type="text"
                icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={() => setCollapsed(!collapsed)}
                style={{ fontSize: '16px', color: textColor }}
              />
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ color: textColor, fontSize: 16, fontWeight: 600 }}>{pageInfo.title}</span>
                {pageInfo.desc && <span style={{ color: '#a0aec0', fontSize: 12 }}>{pageInfo.desc}</span>}
              </div>
            </div>
            <HeaderControls
              user={user}
              isDark={isDark}
              primaryColor={primaryColor}
              textColor={textColor}
              onLogout={handleLogout}
              onToggleTheme={toggleTheme}
            />
          </Header>

          <Content style={{
            padding: 0,
            background: contentBg,
            height: 'calc(100vh - 64px)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}>
            <Outlet />
          </Content>
        </Layout>
      </ConfigProvider>
    </Layout>
  );
}
