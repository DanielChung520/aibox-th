/**
 * @file        AIAssistantDrawer.tsx
 * @description 艾企 AI 助手側邊抽屜面板 — 完整聊天功能
 *              支援串流回應、資料來源標記、歷程面板切換
 *              從 AIAssistantWindow.tsx 移植聊天邏輯，無 BroadcastChannel/assistantBridge 依賴
 * @lastUpdate  2026-06-15 16:00:00
 * @author      AI Agent
 * @version     2.0.0
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Drawer, Input, Button, Avatar, Spin, Tooltip, Tag } from 'antd';
import {
  BarChartOutlined,
  BulbOutlined,
  CloudOutlined,
  CodeOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  PaperClipOutlined,
  PlusOutlined,
  RobotOutlined,
  SafetyOutlined,
  SendOutlined,
  SettingOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { InputRef, MenuProps } from 'antd';
import { authStore } from '../stores/auth';
import { aiqChatStore } from '../stores/chatStore';
import { agentApi, type Agent } from '../services/api';
import { getAgentColor } from '../services/agentColor';
import { pageContextManager, type PageContextState } from '../services/PageContextManager';
import { ENTITY_INTERACT_EVENT } from '../hooks/useEntityPerception';
import { actionTrail, type ActionEvent } from '../services/actionTrail';
import { fetchActionHistory } from '../services/actionTrailApi';
import { intentEngine, type IntentGuess } from '../services/intentEngine';
import { AdminDropdown } from './FloatingAssistant/AdminDropdown';
import { ChatHistoryPanel } from './FloatingAssistant/ChatHistoryPanel';
import { MarkdownContent } from './FloatingAssistant/ChatMarkdown';
import RichMessageBubble from './FloatingAssistant/RichMessageBubble';
import DataSourceBadge from './FloatingAssistant/DataSourceBadge';
import { resolvePageContext } from './FloatingAssistant/types';
import { buildAssistantContext } from '../services/assistantContext';
import { useAIAssistantDrawer } from '../contexts/AIAssistantDrawerContext';
import { useContentTokens } from '../contexts/AppThemeProvider';
import SessionListPanel from './AIAssistantDrawer/SessionListPanel';
import './AIAssistantDrawer.css';

// ── Types ──

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

type HistoryView = 'chat' | 'intentHistory' | 'actionTrail';

// ── Props ──

interface AIAssistantDrawerProps {
  /** 控制 Drawer 開關 */
  open: boolean;
  /** Drawer 關閉回呼 */
  onClose: () => void;
}

// ── Component ──

/** Convert a hex color (#rrggbb) to rgba string with given alpha */
function hexAlpha(hex: string, alpha: number): string {
  if (!hex || hex.length < 7 || !hex.startsWith('#')) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function AIAssistantDrawer({ open, onClose }: AIAssistantDrawerProps) {
  const contentTokens = useContentTokens();
  const { activeView, setActiveView, activeAgent, setActiveAgent } = useAIAssistantDrawer();

  // ── State ──
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [intentGuesses, setIntentGuesses] = useState<IntentGuess[]>([]);
  const [intentPanelOpen, setIntentPanelOpen] = useState(false);
  const [fullPageContext, setFullPageContext] = useState<PageContextState | null>(pageContextManager.getContext());
  const [entityContext, setEntityContext] = useState<Record<string, unknown> | null>(null);
  const [modalContext, setModalContext] = useState<Record<string, unknown> | null>(null);
  const [currentView, setCurrentView] = useState<HistoryView>('chat');
  const [intentHistory, setIntentHistory] = useState<ActionEvent[]>([]);
  const [actionHistory, setActionHistory] = useState<ActionEvent[]>([]);
  const [storeState, setStoreState] = useState(aiqChatStore.getState());
  const [showSessionList, setShowSessionList] = useState(false);

  // ── Refs ──
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<InputRef>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // ── Auto-scroll to bottom ──
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, storeState.messages, storeState.streamingContent]);

  // ── Store subscription + load providers ──
  useEffect(() => {
    const unsubscribe = aiqChatStore.subscribe(() => setStoreState(aiqChatStore.getState()));
    void aiqChatStore.loadProviders();
    return unsubscribe;
  }, []);

  // ── Load agents list & set default active agent ──
  useEffect(() => {
    agentApi.list().then(res => {
      const list = res.data.data || [];
      if (list.length > 0 && !activeAgent) {
        setActiveAgent(list[0]);
      }
    }).catch(() => {});
  }, []);

  // ── Load sessions when drawer opens ──
  useEffect(() => {
    if (open) {
      void aiqChatStore.loadSessions();
    }
  }, [open]);

  // ── Session resume / welcome message ──
  useEffect(() => {
    const resumeSession = async () => {
      const lastKey = aiqChatStore.getLastSessionKey();
      if (lastKey) {
        try {
          await aiqChatStore.loadSessionMessages(lastKey);
          return;
        } catch {
          aiqChatStore.setActiveSessionKey(null);
        }
      }
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        content: '您好！我是艾企 AI 助手。請問有什麼可以幫您的？',
        timestamp: new Date(),
      }]);
    };

    const unsubscribe = authStore.subscribe(() => {
      const state = authStore.getState();
      if (state.isAuthenticated) {
        void resumeSession();
      }
    });

    if (authStore.getState().isAuthenticated) {
      void resumeSession();
    }

    return unsubscribe;
  }, []);

  // ── Intent engine subscription — auto-open panel when guesses arrive ──
  useEffect(() => {
    const unsubscribe = intentEngine.subscribe((guesses) => {
      setIntentGuesses(guesses);
      if (guesses.length > 0) {
        setIntentPanelOpen(true);
      }
    });
    intentEngine.startListening();
    return () => {
      unsubscribe();
      intentEngine.stopListening();
    };
  }, []);

  // ── Page context subscription ──
  useEffect(() => {
    const unsubscribe = pageContextManager.subscribe((ctx) => {
      setFullPageContext(ctx);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  // ── Entity interact event listener ──
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<Record<string, unknown>>).detail;
      setEntityContext({
        entity_id: detail.entity_id as string,
        entity_type: detail.entity_type as string,
        action: detail.action as string,
      });
    };
    window.addEventListener(ENTITY_INTERACT_EVENT, handler);
    return () => window.removeEventListener(ENTITY_INTERACT_EVENT, handler);
  }, []);

  // ── Modal context change event listener ──
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<Record<string, unknown>>).detail;
      setModalContext(detail.action === 'open' ? detail : null);
    };
    window.addEventListener('modal-context-change', handler);
    return () => window.removeEventListener('modal-context-change', handler);
  }, []);

  // ── Push mode: shift page content when Drawer opens ──
  useEffect(() => {
    if (open) {
      document.body.style.transition = 'margin-right 0.3s ease';
      document.body.style.marginRight = '480px';
    } else {
      document.body.style.marginRight = '';
      const timer = setTimeout(() => {
        document.body.style.transition = '';
      }, 300);
      return () => clearTimeout(timer);
    }
    return () => {
      document.body.style.marginRight = '';
      document.body.style.transition = '';
    };
  }, [open]);

  // ── Sync currentView with activeView from context ──
  useEffect(() => {
    setCurrentView(activeView as HistoryView);
  }, [activeView]);

  // ── Handlers ──

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || storeState.isStreaming) return;

    const userMessage = inputValue.trim();
    setInputValue('');

    try {
      const pageCtx = resolvePageContext(window.location.pathname);
      await aiqChatStore.sendMessage(userMessage, buildAssistantContext({
        pathname: window.location.pathname,
        pageContext: pageCtx,
        fullPageContext,
        modalContext,
        entityContext,
        intentGuesses,
        recentActions: actionTrail.getTrail(8),
      }));
    } catch {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，網路連線發生問題，請稍後再試。',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  }, [inputValue, storeState.isStreaming, intentGuesses, fullPageContext, modalContext, entityContext]);

  const handleStopStreaming = useCallback(() => {
    aiqChatStore.stopStreaming();
  }, []);

  const handleBulbToggle = useCallback(() => {
    setIntentPanelOpen((prev) => !prev);
  }, []);

  const handleChipClick = useCallback((guess: IntentGuess) => {
    setInputValue(guess.text);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const handleNewChat = useCallback(() => {
    setMessages([{
      id: `welcome-${Date.now()}`,
      role: 'assistant',
      content: '您好！我是艾企 AI 助手。請問有什麼可以幫您的？',
      timestamp: new Date(),
    }]);
    setInputValue('');
    setCurrentView('chat');
    setActiveView('chat');
    aiqChatStore.setActiveSessionKey(null);
    aiqChatStore.resetCurrentSession();
    aiqChatStore.clearDataSources();
  }, [setActiveView]);

  // ── Icon resolution helper ──
  function resolveIcon(iconName?: string): React.ReactNode {
    if (!iconName) return <RobotOutlined />;
    const iconMap: Record<string, React.ReactNode> = {
      'RobotOutlined': <RobotOutlined />,
      'UserOutlined': <UserOutlined />,
      'BarChartOutlined': <BarChartOutlined />,
      'ToolOutlined': <ToolOutlined />,
      'DatabaseOutlined': <DatabaseOutlined />,
      'SettingOutlined': <SettingOutlined />,
      'CodeOutlined': <CodeOutlined />,
      'ExperimentOutlined': <ExperimentOutlined />,
      'SafetyOutlined': <SafetyOutlined />,
      'CloudOutlined': <CloudOutlined />,
    };
    return iconMap[iconName] || <RobotOutlined />;
  }

  // ── Session action handlers ──
  const handleSessionSelect = useCallback(async (sessionKey: string) => {
    await aiqChatStore.loadSessionMessages(sessionKey);
    setShowSessionList(false);
  }, []);

  const handleNewSessionFromList = useCallback(async () => {
    await aiqChatStore.createSession();
    setShowSessionList(false);
  }, []);

  const handleDeleteSession = useCallback(async (sessionKey: string) => {
    await aiqChatStore.deleteSession(sessionKey);
  }, []);

  const adminMenuItems: MenuProps['items'] = [
    { key: 'actionTrail', label: '📋 顯示操作記錄' },
    { key: 'intentHistory', label: '🔍 顯示意圖記錄' },
  ];

  const handleAdminMenuClick = useCallback((key: string) => {
    if (key === 'intentHistory') {
      const events = [
        ...actionTrail.getTrailByType('intent_accepted', 50),
        ...actionTrail.getTrailByType('intent_rejected', 50),
        ...actionTrail.getTrailByType('intent_confirmed', 50),
      ].sort((a, b) => b.timestamp - a.timestamp);
      setIntentHistory(events);
      setCurrentView('intentHistory');
      setActiveView('intentHistory');
      return;
    }

    if (key === 'actionTrail') {
      const events = actionTrail.getTrail(100)
        .filter((event) => !event.type.startsWith('intent_'))
        .sort((a, b) => b.timestamp - a.timestamp);
      setActionHistory(events);
      setCurrentView('actionTrail');
      setActiveView('actionTrail');
      fetchActionHistory({ page: 1, pageSize: 50, sort: 'desc' }).catch(() => {});
    }
  }, [setActiveView]);

  const handleFileSelect = (_event: React.ChangeEvent<HTMLInputElement>) => {
    // no-op for now
  };

  const handleImageSelect = (_event: React.ChangeEvent<HTMLInputElement>) => {
    // no-op for now
  };

  // ── Computed values ──

  const renderedMessages = useMemo<ChatMessage[]>(() => {
    if (storeState.messages.length === 0) {
      return messages;
    }

    return storeState.messages.map((msg) => ({
      id: msg._key,
      role: (msg.role === 'user' || msg.role === 'assistant' || msg.role === 'system') ? msg.role : 'assistant',
      content: msg.content,
      timestamp: new Date(msg.created_at),
    }));
  }, [messages, storeState.messages]);

  // ── Theme-derived CSS variables ──
  const textBase = contentTokens.colorTextBase;
  const primary = contentTokens.colorPrimary;
  const drawerVars = {
    '--container-bg': contentTokens.containerBg,
    '--color-text-base': textBase,
    '--color-text-secondary': contentTokens.textSecondary,
    '--color-primary': primary,
    '--color-primary-hover': contentTokens.btnSendHover || primary,
    '--input-bg': contentTokens.chatInputBg,
    '--border-color': hexAlpha(textBase, 0.10),
    '--placeholder-color': hexAlpha(textBase, 0.45),
    '--font-family': contentTokens.fontFamily,
    '--border-radius': `${contentTokens.borderRadius}px`,
    /* Interactive / semantic backgrounds */
    '--hover-bg': hexAlpha(textBase, 0.08),
    '--intent-panel-bg': hexAlpha(textBase, 0.03),
    '--chip-bg': hexAlpha(textBase, 0.06),
    '--chip-border': hexAlpha(textBase, 0.10),
    '--chip-hover-bg': hexAlpha(primary, 0.15),
    '--bulb-active-bg': hexAlpha(primary, 0.12),
    '--avatar-bg': hexAlpha(primary, 0.20),
    '--avatar-border': hexAlpha(primary, 0.30),
    '--history-gradient-1': hexAlpha(primary, 0.04),
    '--history-gradient-2': hexAlpha(primary, 0.03),
    '--history-bg': hexAlpha(contentTokens.colorBgBase, 0.42),
  } as React.CSSProperties;

  // ── Render: Header ──

  const headerTitle = useMemo(() => (
    <div className="ai-drawer__header-title">
      <Avatar
        size={28}
        src={undefined}
        icon={activeAgent ? resolveIcon(activeAgent.icon) : <RobotOutlined />}
        style={activeAgent ? {
          border: `2px solid ${getAgentColor(activeAgent)}`,
          color: getAgentColor(activeAgent),
          backgroundColor: `${getAgentColor(activeAgent)}22`,
        } : undefined}
      />
      <span className="ai-drawer__header-text">
        {activeAgent ? activeAgent.name : '助手'}
      </span>
      {activeAgent && (
        <Tag color={activeAgent.visibility === 'private' ? 'default' : 'blue'} style={{ fontSize: 10 }}>
          {activeAgent.visibility === 'private' ? '私有' : '公用'}
        </Tag>
      )}
    </div>
  ), [activeAgent]);

  const headerExtra = (
    <div className="ai-drawer__header-actions">
      <Tooltip title="對話歷史">
        <Button
          type="text"
          icon={<HistoryOutlined />}
          className="ai-drawer__header-btn"
          onClick={() => setShowSessionList(prev => !prev)}
        />
      </Tooltip>
      <Tooltip title="開始新對話">
        <Button
          type="text"
          icon={<PlusOutlined />}
          className="ai-drawer__header-btn"
          onClick={handleNewChat}
        />
      </Tooltip>
      <AdminDropdown menuItems={adminMenuItems} onMenuClick={handleAdminMenuClick} />
    </div>
  );

  return (
    <Drawer
      placement="right"
      open={open}
      onClose={onClose}
      destroyOnClose={false}
      mask={false}
      rootClassName="ai-drawer"
      style={drawerVars}
      styles={{
        wrapper: { width: 480 },
        body: { padding: 0, overflow: 'hidden' },
      }}
      title={headerTitle}
      extra={headerExtra}
    >
      {showSessionList && (
        <SessionListPanel
          sessions={storeState.sessions}
          activeSessionKey={storeState.activeSessionKey}
          agentColor={activeAgent ? getAgentColor(activeAgent) : undefined}
          onSelect={handleSessionSelect}
          onNewChat={handleNewSessionFromList}
          onDelete={handleDeleteSession}
          onRename={async (key, title) => {
            await aiqChatStore.updateSessionTitle(key, title);
          }}
          onClose={() => setShowSessionList(false)}
        />
      )}
      <div className="ai-drawer__container">
        {currentView !== 'chat' ? (
          <div className="ai-drawer__history">
            <ChatHistoryPanel
              currentView={currentView}
              intentHistory={intentHistory}
              actionHistory={actionHistory}
              onBackToChat={() => {
                setCurrentView('chat');
                setActiveView('chat');
              }}
            />
          </div>
        ) : (
          <>
            <div className="ai-drawer__messages">
              {renderedMessages.map((msg) => (
                <div key={msg.id} className={`message message-${msg.role}`}>
                  <div className="message-content">
                    <div className="message-bubble">
                      <RichMessageBubble content={msg.content} role={msg.role as 'user' | 'assistant'} />
                    </div>
                    {msg.role === 'assistant' && storeState.dataSources.length > 0 && (
                      <DataSourceBadge sources={storeState.dataSources} />
                    )}
                    <div className="message-time">
                      {msg.timestamp.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              ))}

              {storeState.isStreaming && storeState.streamingContent && (
                <div className="message message-assistant">
                  <div className="message-content">
                    <div className="message-bubble">
                      <MarkdownContent content={storeState.streamingContent} />
                    </div>
                  </div>
                </div>
              )}

              {storeState.isStreaming && !storeState.streamingContent && (
                <div className="message message-assistant">
                  <div className="message-content">
                    <div className="message-bubble loading">
                      <Spin size="small" /> 思考中...
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Intent guess panel — inline, collapsible chips above footer */}
            <div
              className={`ai-drawer__intent-panel ${intentPanelOpen && intentGuesses.length > 0 ? 'ai-drawer__intent-panel--open' : ''}`}
            >
              <div className="ai-drawer__intent-chips">
                {intentGuesses.map((guess, i) => (
                  <div
                    key={i}
                    className="ai-drawer__intent-chip"
                    onClick={() => handleChipClick(guess)}
                  >
                    <span className="ai-drawer__intent-chip-text">{guess.text}</span>
                    <Tag
                      color={guess.confidence >= 0.8 ? 'green' : guess.confidence >= 0.5 ? 'orange' : 'default'}
                      className="ai-drawer__intent-chip-tag"
                    >
                      {guess.source === 'template' ? '模板' : guess.source === 'rule' ? '規則' : 'AI'}
                    </Tag>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="ai-drawer__footer">
          {intentGuesses.length > 0 ? (
            <Tooltip title="顯示意圖預測">
              <Button
                type="text"
                icon={<BulbOutlined />}
                className={`ai-drawer__footer-btn ai-drawer__footer-bulb ${intentPanelOpen ? 'active' : ''}`}
                onClick={handleBulbToggle}
              />
            </Tooltip>
          ) : (
            <Tooltip title="操作更多後可使用意圖猜測">
              <Button
                type="text"
                icon={<BulbOutlined />}
                className="ai-drawer__footer-btn ai-drawer__footer-bulb"
                disabled
              />
            </Tooltip>
          )}
          <Tooltip title="附加檔案">
            <Button
              type="text"
              icon={<PaperClipOutlined />}
              className="ai-drawer__footer-btn"
              onClick={() => fileInputRef.current?.click()}
            />
          </Tooltip>
          <Input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={handleSend}
            placeholder="輸入消息...（支援 Markdown）"
            disabled={storeState.isStreaming}
            className="ai-drawer__footer-input"
          />
          <Button
            type="text"
            className={`ai-drawer__footer-send ${storeState.isStreaming ? 'is-stop' : ''}`}
            icon={storeState.isStreaming ? <span className="ai-stop-square" aria-hidden="true" /> : <SendOutlined />}
            onClick={storeState.isStreaming ? handleStopStreaming : handleSend}
            disabled={!storeState.isStreaming && !inputValue.trim()}
            aria-label={storeState.isStreaming ? '中止回應' : '送出訊息'}
          />
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.txt,.xlsx,.csv"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
          <input
            ref={imageInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleImageSelect}
          />
        </div>
      </div>
    </Drawer>
  );
}
