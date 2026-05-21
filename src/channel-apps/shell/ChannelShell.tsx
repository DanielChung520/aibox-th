/**
 * @file        ChannelShell.tsx
 * @description LINE 頻道 Shell 容器元件 - 負責頻道應用的整體佈局框架
 *              提供統一的 Header + Content 佈局，支援 CSS class 與 inline style 混合
 * @lastUpdate  2026-05-21 16:45:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import type { ReactNode } from 'react';
import './ChannelShell.css';

interface ChannelShellProps {
  title: string;
  children: ReactNode;
  onBack?: () => void;
}

export default function ChannelShell({ title, children, onBack }: ChannelShellProps) {
  return (
    <div className="channel-shell">
      <header className="channel-shell__header">
        {onBack && (
          <button className="channel-shell__back-btn" onClick={onBack} aria-label="Go back">
            &#8592;
          </button>
        )}
        <h1 className="channel-shell__header-title">{title}</h1>
      </header>
      <main className="channel-shell__content">{children}</main>
    </div>
  );
}
