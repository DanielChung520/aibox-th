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
} from '@ant-design/icons';
import { authStore } from '../stores/auth';
import { authApi, functionApi, paramsApi, Function } from '../services/api';
import { iconMap } from '../utils/icons';
import { useThemeMode, useShellTokens, useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';
import AppLogo from '../components/AppLogo';
import HeaderControls from '../components/HeaderControls';
import { signalCollector } from '../services/signalCollector';
import { userProfileStore } from '../stores/userProfileStore';

const { Header, Sider, Content } = Layout;

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const [user, setUser] = useState(authStore.getState().user);
  const [functions, setFunctions] = useState<Function[]>([]);
  const [appLogo, setAppLogo] = useState('');

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

    const topGroups = functions
      .filter(f => f.function_type === 'group' && f.status === 'enabled')
      .sort((a, b) => a.sort_order - b.sort_order);

    return topGroups.map(group => {
      const subs = functions
        .filter(f => f.function_type === 'sub_function' && f.parent_key === group.code && f.status === 'enabled')
        .sort((a, b) => a.sort_order - b.sort_order);

      const item: any = { key: group.path || group.code, icon: buildIcon(group.icon), label: group.name };

      if (subs.length > 0) {
        item.children = subs.map(sub => ({ key: sub.path || sub.code, label: sub.name }));
      } else if (group.path) {
        item.onClick = () => navigate(group.path!);
      }

      return item;
    });
  })();

  const handleMenuClick = ({ key }: { key: string }) => {
    const item = functions.find(f => (f.path || f.code) === key);
    if (item?.path) navigate(item.path);
  };

  const handleLogout = () => {
    userProfileStore.clear();
    authStore.logout();
    navigate('/login');
  };

  const toggleTheme = () => {
    setThemeMode(isDark ? 'light' : 'dark');
  };

  const getPageTitle = () => {
    const path = location.pathname;
    const func = functions.find(f => f.path === path);
    if (func) return func.name;
    if (path.includes('users')) return '账户管理';
    if (path.includes('roles')) return '角色管理';
    if (path.includes('params')) return '系統參數';
    return '首页';
  };

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
        <Sider trigger={null} collapsible collapsed={collapsed} width={200} style={{ background: siderBg }}>
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
              <span style={{ color: textColor, fontSize: 16, fontWeight: 500 }}>{getPageTitle()}</span>
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
            padding: '24px',
            background: contentBg,
            borderRadius: '10px',
            height: 'calc(100vh - 96px)',
            overflow: 'auto',
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
