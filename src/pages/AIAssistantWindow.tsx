/**
 * @file        AIAssistantWindow.tsx
 * @description 艾企 AI 助手獨立窗口頁面 - 由 Tauri 原生窗口渲染
 *              採用左側獨立意圖面板 + 右側聊天窗口的原始佈局模式
 * @lastUpdate  2026-04-23 20:20:00
 * @author      Daniel Chung
 * @version     1.7.0
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ConfigProvider, App as AntApp, theme, Input, Button, Avatar, Spin, Tooltip, Tag } from 'antd';
import { SendOutlined, BulbOutlined, RobotOutlined, PaperClipOutlined, CloseOutlined, ExpandOutlined, ShrinkOutlined, PlusOutlined } from '@ant-design/icons';
import type { InputRef, MenuProps } from 'antd';
import { invoke } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { authStore } from '../stores/auth';
import { aiqChatStore } from '../stores/chatStore';
import { pageContextManager } from '../services/PageContextManager';
import { actionTrail, type ActionEvent } from '../services/actionTrail';
import { fetchActionHistory } from '../services/actionTrailApi';
import { intentEngine } from '../services/intentEngine';
import { getAvatarName } from '../services/avatarCache';
import { AdminDropdown } from '../components/FloatingAssistant/AdminDropdown';
import { ChatHistoryPanel } from '../components/FloatingAssistant/ChatHistoryPanel';
import { MarkdownContent } from '../components/FloatingAssistant/ChatMarkdown';
import RichMessageBubble from '../components/FloatingAssistant/RichMessageBubble';
import DataSourceBadge from '../components/FloatingAssistant/DataSourceBadge';
import { subscribeAssistantBridge, type AssistantBridgeState } from '../services/assistantBridge';
import { resolvePageContext } from '../components/FloatingAssistant/types';
import type { IntentGuess } from '../components/FloatingAssistant/types';
import { buildAssistantContext } from '../services/assistantContext';
import './AIAssistantWindow.css';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

type HistoryView = 'chat' | 'intentHistory' | 'actionTrail';

function AIAssistantWindow() {
  const SIDECAR_WIDTH = 274;
  const SIDECAR_LEFT = 18;
  const WINDOW_LEFT = 314;
  const WINDOW_RIGHT = 18;
  const SIDECAR_VISIBILITY_GAP = 24;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [intentGuesses, setIntentGuesses] = useState<IntentGuess[]>([]);
  const [intentPanelOpen, setIntentPanelOpen] = useState(true);
  const [avatarSrc, setAvatarSrc] = useState<string | undefined>(undefined);
  const [bridgeState, setBridgeState] = useState<AssistantBridgeState | null>(null);
  const [windowWidth, setWindowWidth] = useState(() => window.innerWidth);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<InputRef>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [currentView, setCurrentView] = useState<HistoryView>('chat');
  const [intentHistory, setIntentHistory] = useState<ActionEvent[]>([]);
  const [actionHistory, setActionHistory] = useState<ActionEvent[]>([]);
  const [storeState, setStoreState] = useState(aiqChatStore.getState());

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, storeState.messages, storeState.streamingContent]);

  useEffect(() => {
    document.documentElement.classList.add('ai-assistant-window');
    return () => {
      document.documentElement.classList.remove('ai-assistant-window');
    };
  }, []);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    let active = true;

    const syncExpandedState = async () => {
      try {
        const expanded = await invoke<boolean>('get_ai_assistant_expanded');
        if (active) {
          setIsExpanded(expanded);
        }
      } catch {
        // ignore state sync errors outside Tauri runtime
      }
    };

    void syncExpandedState();
    window.addEventListener('focus', syncExpandedState);

    return () => {
      active = false;
      window.removeEventListener('focus', syncExpandedState);
    };
  }, []);

  useEffect(() => {
    getAvatarName().then(name => {
      if (name) {
        setAvatarSrc(`/avatars/${name}.png`);
      }
    });
  }, []);

  useEffect(() => {
    const unsubscribe = aiqChatStore.subscribe(() => setStoreState(aiqChatStore.getState()));
    void aiqChatStore.loadProviders();
    return unsubscribe;
  }, []);

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
        timestamp: new Date()
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

  useEffect(() => {
    const unsubscribe = intentEngine.subscribe((guesses) => {
      if (bridgeState?.intentGuesses?.length) {
        return;
      }
      setIntentGuesses(guesses);
      if (guesses.length > 0) {
        setIntentPanelOpen(true);
      }
    });
    intentEngine.startListening();
    return unsubscribe;
  }, [bridgeState?.intentGuesses]);

  useEffect(() => subscribeAssistantBridge((state) => setBridgeState(state)), []);

  useEffect(() => {
    if (!bridgeState) {
      return;
    }

    setIntentGuesses(bridgeState.intentGuesses);
    if (bridgeState.intentGuesses.length > 0) {
      setIntentPanelOpen(true);
    }
  }, [bridgeState]);

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || storeState.isStreaming) return;

    const userMessage = inputValue.trim();
    setInputValue('');

    try {
      const fallbackFullPageContext = bridgeState?.fullPageContext ?? pageContextManager.getContext();
      await aiqChatStore.sendMessage(userMessage, buildAssistantContext({
        pathname: bridgeState?.pathname ?? window.location.pathname,
        pageContext: bridgeState?.pageContext ?? effectivePageContext,
        fullPageContext: fallbackFullPageContext,
        modalContext: bridgeState?.modalContext ?? null,
        entityContext: bridgeState?.entityContext ?? null,
        intentGuesses,
        recentActions: actionTrail.getTrail(8),
      }));
    } catch {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，網路連線發生問題，請稍後再試。',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  }, [inputValue, storeState.isStreaming, bridgeState]);

  const handleStopStreaming = useCallback(() => {
    aiqChatStore.stopStreaming();
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
      return;
    }

    if (key === 'actionTrail') {
      const events = actionTrail.getTrail(100)
        .filter((event) => !event.type.startsWith('intent_'))
        .sort((a, b) => b.timestamp - a.timestamp);
      setActionHistory(events);
      setCurrentView('actionTrail');
      // Pre-warm backend history (ChatHistoryPanel will display it)
      fetchActionHistory({ page: 1, pageSize: 50, sort: 'desc' }).catch(() => {});
    }
  }, []);

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

  const handleIntentSelect = (guess: IntentGuess) => {
    setInputValue(guess.text);
    setIntentPanelOpen(false);
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const toggleExpanded = useCallback(async () => {
    try {
      const nextExpanded = await invoke<boolean>('set_ai_assistant_expanded', { expanded: !isExpanded });
      setIsExpanded(nextExpanded);
    } catch {
      setIsExpanded(prev => !prev);
    }
  }, [isExpanded]);

  const hideAssistant = useCallback(async () => {
    try {
      await invoke('hide_ai_assistant');
    } catch {
      console.warn('Tauri hide_ai_assistant not available');
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setMessages([{
      id: `welcome-${Date.now()}`,
      role: 'assistant',
      content: '您好！我是艾企 AI 助手。請問有什麼可以幫您的？',
      timestamp: new Date()
    }]);
    setInputValue('');
    setCurrentView('chat');
    aiqChatStore.setActiveSessionKey(null);
    aiqChatStore.resetCurrentSession();
    aiqChatStore.clearDataSources();
  }, []);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    event.target.value = '';
  };

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    event.target.value = '';
  };

  const handleDragPointerDown = useCallback(async () => {
    try {
      await getCurrentWindow().startDragging();
    } catch {
      // no-op when native dragging is unavailable
    }
  }, []);

  const effectivePageContext = bridgeState?.pageContext ?? resolvePageContext(window.location.pathname);
  const quickSuggestions = effectivePageContext.suggestions;
  const requiredWidthForSidecar = WINDOW_LEFT + WINDOW_RIGHT + SIDECAR_WIDTH + SIDECAR_LEFT + SIDECAR_VISIBILITY_GAP;
  const canShowIntentSidecar = windowWidth >= requiredWidthForSidecar;
  const shouldRenderIntentSidecar = intentGuesses.length > 0 && intentPanelOpen && canShowIntentSidecar;

  return (
    <div className={`ai-assistant-root ${shouldRenderIntentSidecar ? 'has-intent-sidecar' : ''}`}>
      {shouldRenderIntentSidecar && (
        <div className="ai-intent-sidecar">
          <div className="intent-guess-popover">
            <div className="intent-sidecar-header">
              <span>🔮 猜你想问...</span>
              <Button
                type="text"
                size="small"
                icon={<CloseOutlined />}
                className="intent-sidecar-close"
                onClick={() => setIntentPanelOpen(false)}
              />
            </div>
            <div className="intent-sidecar-list">
              {intentGuesses.map((guess, i) => (
                <div
                  key={i}
                  className="intent-sidecar-item"
                  onClick={() => handleIntentSelect(guess)}
                >
                  <span className="intent-sidecar-text">{guess.text}</span>
                  <Tag
                    color={guess.confidence >= 0.8 ? 'green' : guess.confidence >= 0.5 ? 'orange' : 'default'}
                    className="intent-sidecar-tag"
                  >
                    {guess.confidence >= 0.8 ? '★★★' : guess.confidence >= 0.5 ? '★★' : '★'}
                    {guess.source === 'template' ? ' 模板' : guess.source === 'rule' ? ' 規則' : ' AI'}
                  </Tag>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className={`ai-window ${isExpanded ? 'expanded' : ''}`}>
        <div className="ai-window-header">
          <div className="ai-window-title" onPointerDown={() => void handleDragPointerDown()}>
            <Avatar
              size="small"
              src={avatarSrc}
              icon={!avatarSrc ? <RobotOutlined /> : undefined}
            />
            <span>艾企 AI 助手</span>
          </div>
          <div className="ai-window-drag-area" onPointerDown={() => void handleDragPointerDown()} />
          <div className="ai-window-actions">
            <Tooltip title="開始新對話">
              <Button type="text" icon={<PlusOutlined />} onClick={handleNewChat} />
            </Tooltip>
            <AdminDropdown menuItems={adminMenuItems} onMenuClick={handleAdminMenuClick} />
            <Tooltip title={isExpanded ? '還原' : '展開'}>
              <Button
                type="text"
                icon={isExpanded ? <ShrinkOutlined /> : <ExpandOutlined />}
                onClick={toggleExpanded}
              />
            </Tooltip>
            <Tooltip title="關閉">
              <Button type="text" icon={<CloseOutlined />} onClick={hideAssistant} />
            </Tooltip>
          </div>
        </div>

        {bridgeState?.fullPageContext && (
          <div className="ai-window-context">
            <span>頁面：{bridgeState.fullPageContext.pageName}</span>
            {bridgeState.fullPageContext.componentName && <span>組件：{bridgeState.fullPageContext.componentName}</span>}
            {bridgeState.fullPageContext.entity && <span>實體：{bridgeState.fullPageContext.entity}</span>}
          </div>
        )}

        {currentView !== 'chat' ? (
          <div className="ai-window-history">
            <ChatHistoryPanel
              currentView={currentView}
              intentHistory={intentHistory}
              actionHistory={actionHistory}
              onBackToChat={() => setCurrentView('chat')}
            />
          </div>
        ) : (
          <>
            <div className="ai-window-messages">
            {renderedMessages.map(msg => (
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

          {quickSuggestions.length > 0 && (
            <div className="ai-window-quick-suggestions">
              {quickSuggestions.map((text) => (
                <button key={text} className="intent-item quick-suggestion" onClick={() => setInputValue(text)}>
                  <span className="intent-text">{text}</span>
                </button>
              ))}
            </div>
          )}
          </>
        )}

      <div className="ai-window-footer">
        <Tooltip title={intentGuesses.length > 0 ? '顯示意圖預測' : '操作更多後可使用意圖猜測'}>
          <Button
            type="text"
            icon={storeState.isStreaming ? <Spin size="small" /> : <BulbOutlined />}
            className={`ai-footer-icon ${intentPanelOpen && intentGuesses.length > 0 ? 'active' : ''}`}
            onClick={() => intentGuesses.length > 0 && setIntentPanelOpen(prev => !prev)}
            disabled={intentGuesses.length === 0}
          />
        </Tooltip>
        <Tooltip title="附加檔案">
          <Button
            type="text"
            icon={<PaperClipOutlined />}
            className="ai-footer-icon"
            onClick={() => fileInputRef.current?.click()}
          />
        </Tooltip>
        <Input
          ref={inputRef}
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onPressEnter={handleSend}
          placeholder="輸入消息...（支援 Markdown）"
          disabled={storeState.isStreaming}
        />
        <Button
          type="text"
          className={`ai-footer-icon ai-footer-send ${storeState.isStreaming ? 'is-stop' : ''}`}
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
    </div>
  );
}

function AIAssistantApp() {
  return (
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm }}>
      <AntApp>
        <AIAssistantWindow />
      </AntApp>
    </ConfigProvider>
  );
}

export default AIAssistantApp;
