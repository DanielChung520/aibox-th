/**
 * @file        AgentMenu.tsx
 * @description 艾企 AI 助手 Agent 切換浮動選單 — 固定定位，按鈕側上方展開
 *              支援：公用/私有分組、顏色指示條、圖示解析、活躍標記、動畫入場
 * @lastUpdate  2026-06-16 12:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useEffect, useRef, useState, useMemo } from 'react';
import { Tag } from 'antd';
import {
  CheckOutlined,
  SettingOutlined,
  RobotOutlined,
  MessageOutlined,
  ToolOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  TeamOutlined,
  SmileOutlined,
} from '@ant-design/icons';
import type { Agent } from '../../services/api';
import { getAgentColor } from '../../services/agentColor';

// ── Icon resolver ──
// Map common icon string values to Ant Design icon components
const ICON_MAP: Record<string, React.ReactNode> = {
  robot: <RobotOutlined />,
  RobotOutlined: <RobotOutlined />,
  message: <MessageOutlined />,
  MessageOutlined: <MessageOutlined />,
  tool: <ToolOutlined />,
  ToolOutlined: <ToolOutlined />,
  database: <DatabaseOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
  file: <FileTextOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  thunderbolt: <ThunderboltOutlined />,
  ThunderboltOutlined: <ThunderboltOutlined />,
  team: <TeamOutlined />,
  TeamOutlined: <TeamOutlined />,
  smile: <SmileOutlined />,
  SmileOutlined: <SmileOutlined />,
};

function resolveIcon(iconName: string | undefined): React.ReactNode {
  if (!iconName) return <RobotOutlined />;
  return ICON_MAP[iconName] ?? <RobotOutlined />;
}

// ── Component API ──

interface AgentMenuProps {
  agents: Agent[];
  activeAgent: Agent | null;
  /** FAB button position (top-left corner) */
  position: { x: number; y: number };
  onSelect: (agent: Agent) => void;
  onClose: () => void;
}

// ── Constants ──

const MENU_WIDTH = 260;
const MENU_RADIUS = 12;
const FAB_SIZE = 56;
const GAP = 8;
const ITEM_HEIGHT = 44;
const MAX_VISIBLE_ITEMS = 6;

// ── Component ──

export default function AgentMenu({ agents, activeAgent, position, onSelect, onClose }: AgentMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  // ── Trigger mount animation on next frame ──
  useEffect(() => {
    const timer = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(timer);
  }, []);

  // ── Split agents into public & private ──
  const { publicAgents, privateAgents } = useMemo(() => {
    const pub: Agent[] = [];
    const priv: Agent[] = [];
    for (const agent of agents) {
      if (agent.visibility === 'private') {
        priv.push(agent);
      } else {
        pub.push(agent);
      }
    }
    return { publicAgents: pub, privateAgents: priv };
  }, [agents]);

  // ── Compute fixed position (menu appears above/beside the FAB) ──
  const menuPosition = useMemo((): React.CSSProperties => {
    const rightOffset = window.innerWidth - (position.x + FAB_SIZE);
    const topOfFab = position.y;
    const bottomOffset = window.innerHeight - topOfFab + GAP;

    return {
      position: 'fixed' as const,
      right: Math.max(8, rightOffset),
      bottom: Math.max(8, bottomOffset),
      width: MENU_WIDTH,
    };
  }, [position, agents.length]);

  // ── Close on outside click ──
  useEffect(() => {
    // Delay registration to prevent the click that opened the menu from closing it
    const timer = setTimeout(() => {
      const handleClick = (e: MouseEvent) => {
        if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
          onClose();
        }
      };
      document.addEventListener('click', handleClick, true);
      // Cleanup removes this specific listener
      return () => document.removeEventListener('click', handleClick, true);
    }, 0);
    return () => clearTimeout(timer);
  }, [onClose]);

  // ── Close on Escape ──
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // ── Render a single agent row ──

  const renderAgentRow = (agent: Agent) => {
    const isActive = activeAgent?._key === agent._key;
    const color = getAgentColor(agent);
    const icon = resolveIcon(agent.icon);
    const visibilityLabel = agent.visibility === 'private' ? '私有' : '公用';

    return (
      <div
        key={agent._key ?? agent.name}
        onClick={() => onSelect(agent)}
        role="menuitem"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(agent); }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '9px 14px',
          cursor: 'pointer',
          borderLeft: `3px solid ${color}`,
          background: isActive ? 'rgba(59, 130, 246, 0.12)' : 'transparent',
          transition: 'background 0.15s ease',
          userSelect: 'none',
          minHeight: ITEM_HEIGHT,
        }}
        onMouseEnter={(e) => {
          if (!isActive) {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive) {
            e.currentTarget.style.background = 'transparent';
          }
        }}
      >
        {/* Color bar + icon */}
        <div
          style={{
            fontSize: 16,
            color,
            display: 'flex',
            flexShrink: 0,
            width: 20,
            justifyContent: 'center',
          }}
        >
          {icon}
        </div>

        {/* Agent name */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 13,
            fontWeight: isActive ? 600 : 400,
            color: '#e2e8f0',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {agent.name}
        </div>

        {/* Visibility tag */}
        <Tag
          color={agent.visibility === 'private' ? 'default' : 'blue'}
          style={{
            fontSize: 10,
            lineHeight: '16px',
            padding: '0 6px',
            borderRadius: 4,
            margin: 0,
            flexShrink: 0,
            border: agent.visibility === 'private' ? '1px solid rgba(255,255,255,0.15)' : 'none',
          }}
        >
          {visibilityLabel}
        </Tag>

        {/* Active checkmark */}
        {isActive && (
          <CheckOutlined style={{ color: '#60a5fa', fontSize: 14, flexShrink: 0 }} />
        )}
      </div>
    );
  };

  // ── Render ──

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="切換 AI 助手"
      style={{
        ...menuPosition,
        zIndex: 10001,
        background: 'rgba(22, 27, 34, 0.95)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.10)',
        borderRadius: MENU_RADIUS,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.3)',
        overflow: 'hidden',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.2s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        pointerEvents: 'auto',
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: '12px 14px 8px',
          fontSize: 12,
          fontWeight: 600,
          color: 'rgba(255, 255, 255, 0.5)',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          userSelect: 'none',
        }}
      >
        切換 AI 助手
      </div>

      {/* ── Agent list ── */}
      <div
        style={{
          maxHeight: MAX_VISIBLE_ITEMS * ITEM_HEIGHT,
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        {publicAgents.map(renderAgentRow)}

        {/* Divider between public and private */}
        {privateAgents.length > 0 && publicAgents.length > 0 && (
          <div
            style={{
              height: 1,
              background: 'rgba(255, 255, 255, 0.08)',
              margin: '4px 14px',
            }}
          />
        )}

        {privateAgents.map(renderAgentRow)}

        {/* Empty state */}
        {agents.length === 0 && (
          <div
            style={{
              padding: '20px 14px',
              textAlign: 'center',
              fontSize: 12,
              color: 'rgba(255, 255, 255, 0.35)',
            }}
          >
            暫無可用助手
          </div>
        )}
      </div>

      {/* ── Footer: manage agent ── */}
      <div
        onClick={() => {
          window.location.href = '/app/agents';
          onClose();
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { window.location.href = '/app/agents'; onClose(); } }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '10px 14px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          cursor: 'pointer',
          fontSize: 12,
          color: 'rgba(255, 255, 255, 0.55)',
          transition: 'color 0.15s ease, background 0.15s ease',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = '#e2e8f0';
          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'rgba(255, 255, 255, 0.55)';
          e.currentTarget.style.background = 'transparent';
        }}
      >
        <SettingOutlined style={{ fontSize: 14 }} />
        <span>管理 Agent</span>
      </div>
    </div>
  );
}
