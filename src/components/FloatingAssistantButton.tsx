/**
 * @file        FloatingAssistantButton.tsx
 * @description 艾企 AI 助手按鈕 — 左鍵拖曳/點擊切換 Drawer，右鍵顯示 Agent 切換選單
 * @lastUpdate  2026-06-16 12:00:00
 * @author      Daniel Chung
 * @version     1.5.0
 */

import { Tooltip, Avatar } from 'antd';
import { RobotOutlined } from '@ant-design/icons';
import { invoke } from '@tauri-apps/api/core';
import { useState, useEffect, useRef, useCallback } from 'react';
import { authStore } from '../stores/auth';
import { useAvatar } from '../services/avatarCache';
import { useAIAssistantDrawer } from '../contexts/AIAssistantDrawerContext';
import { agentApi, type Agent } from '../services/api';
import AgentMenu from './AIAssistantDrawer/AgentMenu';

export default function FloatingAssistantButton() {
  const [visible, setVisible] = useState(false);
  const avatarSrc = useAvatar();
  const { isOpen, toggle } = useAIAssistantDrawer();
  const BUTTON_SIZE = 56;
  const EDGE_OFFSET = 24;
  const [position, setPosition] = useState(() => ({
    x: Math.max(EDGE_OFFSET, window.innerWidth - BUTTON_SIZE - EDGE_OFFSET),
    y: Math.max(EDGE_OFFSET, window.innerHeight - BUTTON_SIZE - EDGE_OFFSET),
  }));
  const [isDragging, setIsDragging] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeAgent, setActiveAgent] = useState<Agent | null>(null);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const dragRef = useRef({
    startX: 0,
    startY: 0,
    initX: 0,
    initY: 0,
    hasMoved: false,
  });

  useEffect(() => {
    const unsubscribe = authStore.subscribe(() => {
      setVisible(authStore.getState().isAuthenticated);
    });
    setVisible(authStore.getState().isAuthenticated);

    return () => {
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    const handleResize = () => {
      setPosition((prev) => ({
        x: Math.max(EDGE_OFFSET, Math.min(prev.x, window.innerWidth - BUTTON_SIZE - EDGE_OFFSET)),
        y: Math.max(EDGE_OFFSET, Math.min(prev.y, window.innerHeight - BUTTON_SIZE - EDGE_OFFSET)),
      }));
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    agentApi.list().then(res => {
      setAgents(res.data.data || []);
    }).catch(() => {});
  }, []);

  const handleClick = useCallback(async () => {
    try {
      // Try Drawer toggle first (primary mode)
      toggle();
    } catch {
      // Fallback to Tauri native window (safety period)
      try {
        await invoke('toggle_ai_assistant');
      } catch (err) {
        console.warn('[FloatingAssistantButton] Tauri toggle not available:', err);
      }
    }
  }, [toggle]);

  const handlePointerStart = (clientX: number, clientY: number) => {
    setIsDragging(true);
    dragRef.current = {
      startX: clientX,
      startY: clientY,
      initX: position.x,
      initY: position.y,
      hasMoved: false,
    };
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    handlePointerStart(e.clientX, e.clientY);
    e.preventDefault();
  };

  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    const touch = e.touches[0];
    if (!touch) return;
    handlePointerStart(touch.clientX, touch.clientY);
    e.preventDefault();
  };

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setShowAgentMenu(true);
  }, []);

  const handleAgentSelect = useCallback((agent: Agent) => {
    setActiveAgent(agent);
    setShowAgentMenu(false);
    if (!isOpen) toggle();
  }, [isOpen, toggle]);

  useEffect(() => {
    if (!isDragging) return;

    const updatePosition = (clientX: number, clientY: number) => {
      const dx = clientX - dragRef.current.startX;
      const dy = clientY - dragRef.current.startY;

      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        dragRef.current.hasMoved = true;
      }

      const nextX = dragRef.current.initX + dx;
      const nextY = dragRef.current.initY + dy;
      const maxX = window.innerWidth - BUTTON_SIZE - EDGE_OFFSET;
      const maxY = window.innerHeight - BUTTON_SIZE - EDGE_OFFSET;

      setPosition({
        x: Math.max(EDGE_OFFSET, Math.min(nextX, maxX)),
        y: Math.max(EDGE_OFFSET, Math.min(nextY, maxY)),
      });
    };

    const handleMouseMove = (e: MouseEvent) => {
      updatePosition(e.clientX, e.clientY);
    };

    const handleTouchMove = (e: TouchEvent) => {
      const touch = e.touches[0];
      if (!touch) return;
      updatePosition(touch.clientX, touch.clientY);
    };

    const finishDrag = () => {
      setIsDragging(false);
      if (!dragRef.current.hasMoved) {
        void handleClick();
      }
    };

    document.addEventListener('mousemove', handleMouseMove, { passive: false });
    document.addEventListener('mouseup', finishDrag);
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', finishDrag);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', finishDrag);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', finishDrag);
    };
  }, [isDragging, handleClick]);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        zIndex: 9999,
        width: BUTTON_SIZE,
        height: BUTTON_SIZE,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        touchAction: 'none',
        background: 'linear-gradient(135deg, rgba(29, 78, 216, 0.96) 0%, rgba(37, 99, 235, 0.98) 100%)',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
      }}
      onMouseDown={handleMouseDown}
      onTouchStart={handleTouchStart}
      onContextMenu={handleContextMenu}
    >
      <Tooltip title={activeAgent ? `${activeAgent.name} — 右鍵切換` : '打開艾企 AI 助手'} placement="left">
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          <Avatar
            size={32}
            src={avatarSrc}
            icon={!avatarSrc ? <RobotOutlined /> : undefined}
            style={{ backgroundColor: avatarSrc ? 'transparent' : 'rgba(30, 64, 175, 0.22)', pointerEvents: 'none' }}
          />
        </div>
      </Tooltip>

      {showAgentMenu && (
        <AgentMenu
          agents={agents}
          activeAgent={activeAgent}
          position={position}
          onSelect={handleAgentSelect}
          onClose={() => setShowAgentMenu(false)}
        />
      )}
    </div>
  );
}
