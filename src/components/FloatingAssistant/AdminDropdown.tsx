/**
 * @file        AdminDropdown.tsx
 * @description 管理員下拉選單元件（操作記錄、意圖歷史）
 * @lastUpdate  2026-04-18 22:12:08
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { SettingOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import type { MenuProps } from 'antd';

interface AdminDropdownProps {
  menuItems: MenuProps['items'];
  onMenuClick: (key: string) => void;
}

export function AdminDropdown({ menuItems, onMenuClick }: AdminDropdownProps) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const timer = setTimeout(() => document.addEventListener('click', close), 0);
    return () => { clearTimeout(timer); document.removeEventListener('click', close); };
  }, [open]);

  return (
    <>
      <Button
        ref={btnRef}
        type="text"
        icon={<SettingOutlined />}
        size="small"
        style={{ color: 'rgba(255,255,255,0.65)', fontSize: 14 }}
        onClick={() => setOpen(!open)}
        onMouseDown={(e) => e.stopPropagation()}
        onTouchStart={(e) => e.stopPropagation()}
      />
      {open && createPortal(
        <div
          style={{
            position: 'fixed',
            top: (() => {
              const rect = btnRef.current?.getBoundingClientRect();
              return rect ? rect.bottom + 4 : 0;
            })(),
            left: (() => {
              const rect = btnRef.current?.getBoundingClientRect();
              return rect ? rect.right - 160 : 0;
            })(),
            zIndex: 100000,
            minWidth: 160,
            background: 'rgba(30, 41, 59, 0.95)',
            backdropFilter: 'blur(12px)',
            borderRadius: 8,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            padding: '4px 0',
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {(menuItems || []).map((item) => {
            const menuItem = item as { key: string; label: string };
            return (
              <div
                key={menuItem.key}
                style={{
                  padding: '8px 16px',
                  color: 'rgba(255,255,255,0.85)',
                  cursor: 'pointer',
                  fontSize: 13,
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.1)'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                onClick={() => {
                  setOpen(false);
                  onMenuClick(menuItem.key);
                }}
              >
                {menuItem.label}
              </div>
            );
          })}
        </div>,
        document.body
      )}
    </>
  );
}
