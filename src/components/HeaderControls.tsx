/**
 * @file        Header 右側控制區元件
 * @description Header 右側的控制項：服務狀態列、主題切換、使用者頭像下拉
 * @lastUpdate  2026-04-14 21:39:58
 * @author      Daniel Chung
 * @version     1.2.0
 */

import { useState, useEffect } from 'react';
import { Button, Avatar, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import { UserOutlined, LogoutOutlined, SunOutlined, MoonOutlined } from '@ant-design/icons';
import ServiceStatusBar from './ServiceStatusBar';
import JobMonitor from './JobMonitor';
import type { LoginResponse } from '../services/api';
import { paramsApi } from '../services/api';

const avatarModules = import.meta.glob<{ default: string }>(
  '../assets/avatar/*.png',
  { eager: true }
);

function resolveAvatarSrc(name: string): string | undefined {
  if (!name) return undefined;
  const entry = Object.entries(avatarModules).find(([path]) => {
    const filename = path.split('/').pop() || '';
    return filename.replace(/\.png$/i, '') === name;
  });
  return entry ? entry[1].default : undefined;
}

interface HeaderControlsProps {
  user: LoginResponse['user'] | null;
  isDark: boolean;
  primaryColor: string;
  textColor: string;
  onLogout: () => void;
  onToggleTheme: () => void;
}

export default function HeaderControls({
  user,
  isDark,
  primaryColor,
  textColor,
  onLogout,
  onToggleTheme,
}: HeaderControlsProps) {
  const [avatarSrc, setAvatarSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    paramsApi.get('basic.avatar')
      .then(res => {
        const name = res.data?.data?.param_value;
        if (name) setAvatarSrc(resolveAvatarSrc(name));
      })
      .catch(() => {});

    const handleAvatarChanged = (e: Event) => {
      const name = (e as CustomEvent).detail?.name;
      if (name) setAvatarSrc(resolveAvatarSrc(name));
    };
    window.addEventListener('avatar-changed', handleAvatarChanged);
    return () => window.removeEventListener('avatar-changed', handleAvatarChanged);
  }, []);

  const menuItems: MenuProps['items'] = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: onLogout },
  ];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <ServiceStatusBar />
      <JobMonitor isDark={isDark} primaryColor={primaryColor} textColor={textColor} />
      <Button
        type="text"
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
        onClick={onToggleTheme}
        style={{ color: textColor }}
      />
      <span style={{ color: textColor }}>{user?.name || user?.username}</span>
      <Dropdown menu={{ items: menuItems }} placement="bottomRight">
        <Avatar
          style={{ cursor: 'pointer', background: avatarSrc ? 'transparent' : primaryColor }}
          src={avatarSrc}
          icon={!avatarSrc ? <UserOutlined /> : undefined}
        />
      </Dropdown>
    </div>
  );
}
