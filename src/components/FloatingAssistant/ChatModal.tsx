/**
 * @file        ChatModal.tsx
 * @description 悬浮聊天窗口，可拖拽、可调整大小、磨砂玻璃头部、頁面感知、意圖歷史、新對話
 * @lastUpdate  2026-04-18 22:45:00
 * @author      Daniel Chung
 * @version     2.4.0
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { CloseOutlined, RobotOutlined, SendOutlined, BulbOutlined, LoadingOutlined, PlusOutlined, FullscreenOutlined, FullscreenExitOutlined, PaperClipOutlined } from '@ant-design/icons';
import { Button, Input, Avatar, Tooltip, Spin, Dropdown, message } from 'antd';
import type { InputRef } from 'antd';
import type { MenuProps } from 'antd';
import { MarkdownContent } from './ChatMarkdown';
import { formatAgentResult, ROUTABLE_STRATEGIES } from './formatAgentResult';
import { useDragResize } from './useDragResize';
import { ChatHistoryPanel } from './ChatHistoryPanel';
import { AdminDropdown } from './AdminDropdown';
import { FloatingAssistantConfig, PageContext, IntentGuess } from './types';
import { intentEngine } from '../../services/intentEngine';
import { actionTrail } from '../../services/actionTrail';
import type { ActionEvent } from '../../services/actionTrail';
import { authStore } from '../../stores/auth';
import { aiqChatStore } from '../../stores/chatStore';
import type { ChatMessage as ApiChatMessage } from '../../services/api';
import { buildAssistantContext } from '../../services/assistantContext';


interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  position: { x: number; y: number };
  onPositionChange: (pos: { x: number; y: number }) => void;
  buttonPosition: { x: number; y: number };
  initialConfig: FloatingAssistantConfig;
  avatarSrc?: string;
  pageContext: PageContext;
  fullPageContext: {
    page: string;
    pageName: string;
    component?: string;
    componentName?: string;
    entity?: string;
    entityType?: string;
    action?: string;
    data?: Record<string, unknown>;
  } | null;
  modalContext: {
    modal: string;
    mode: string;
    agent_key?: string;
    agent_name?: string;
    demand?: {
      key: string;
      goal: string;
      expected_effect: string;
      problem_description: string;
      status: string;
    } | null;
    action: string;
  } | null;
  intentGuesses: IntentGuess[];
  intentLoading: boolean;
  intentPanelOpen: boolean;
  onIntentPanelToggle: () => void;
  intentSelectRef: React.RefObject<((text: string, guess: IntentGuess) => void) | null>;
}

export default function ChatModal({
  isOpen, onClose, position, onPositionChange, buttonPosition, initialConfig, avatarSrc, pageContext, fullPageContext, modalContext,
  intentGuesses, intentLoading, intentPanelOpen, onIntentPanelToggle, intentSelectRef
}: ChatModalProps) {
  const { size, handleHeaderMouseDown, handleResizeMouseDown } = useDragResize(
    initialConfig,
    position,
    onPositionChange
  );

  const buildWelcomeMessages = useCallback((): ChatMessage[] => {
    const ts = Date.now();
    return [
      {
        id: `sys-init-${ts}`,
        role: 'system',
        content: '今天 ' + new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' }),
        timestamp: new Date(),
      },
      {
        id: `welcome-${ts}`,
        role: 'assistant',
        content: '你好！我是**艾企**——您的 AI 企業好助手，請問有什麼能幫到您！',
        timestamp: new Date(),
      },
    ];
  }, []);

  const [localWelcomeMessages, setLocalWelcomeMessages] = useState<ChatMessage[]>(() => buildWelcomeMessages());
  const [storeState, setStoreState] = useState(aiqChatStore.getState());
  const [inputValue, setInputValue] = useState('');
  const lastPageNameRef = useRef(pageContext.name);
  const lastModalContextRef = useRef(modalContext);

  useEffect(() => {
    const unsubscribe = aiqChatStore.subscribe(() => setStoreState(aiqChatStore.getState()));
    void aiqChatStore.loadProviders();
    return unsubscribe;
  }, []);

  const [selectedGuess, setSelectedGuess] = useState<IntentGuess | null>(null);
  const [currentView, setCurrentView] = useState<'chat' | 'intentHistory' | 'actionTrail'>('chat');
  const [intentHistory, setIntentHistory] = useState<ActionEvent[]>([]);
  const [actionHistory, setActionHistory] = useState<ActionEvent[]>([]);
  const [fullscreen, setFullscreen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<InputRef>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      message.info(`已選擇文件：${file.name}`);
      e.target.value = '';
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      message.info(`已選擇圖片：${file.name}`);
      e.target.value = '';
    }
  };

  const attachmentMenuItems: MenuProps['items'] = [
    {
      key: 'file',
      label: '上傳文件',
      onClick: () => {
        fileInputRef.current?.click();
      },
    },
    {
      key: 'image',
      label: '上傳圖片',
      onClick: () => {
        imageInputRef.current?.click();
      },
    },
  ];

  const user = authStore.getState().user;
  const isAdmin = (user as Record<string, unknown>)?.role_keys
    ? ((user as Record<string, unknown>).role_keys as string[]).includes('admin')
    : user?.role_key === 'admin';

  const adminMenuItems: MenuProps['items'] = [
    { key: 'actionTrail', label: '📋 顯示操作記錄' },
    { key: 'intentHistory', label: '🔍 顯示意圖記錄' },
  ];

  const handleAdminMenuClick = (key: string) => {
    if (key === 'intentHistory') {
      const events = [
        ...actionTrail.getTrailByType('intent_accepted', 50),
        ...actionTrail.getTrailByType('intent_rejected', 50),
        ...actionTrail.getTrailByType('intent_confirmed', 50),
      ].sort((a, b) => b.timestamp - a.timestamp);
      setIntentHistory(events);
      setCurrentView('intentHistory');
    } else if (key === 'actionTrail') {
      const events = actionTrail.getTrail(100)
        .filter(ev => !ev.type.startsWith('intent_'))
        .sort((a, b) => b.timestamp - a.timestamp);
      setActionHistory(events);
      setCurrentView('actionTrail');
    }
  };

  useEffect(() => {
    intentSelectRef.current = (text: string, guess: IntentGuess) => {
      setInputValue(text);
      setSelectedGuess(guess);
    };
    return () => {
      intentSelectRef.current = null;
    };
  }, [intentSelectRef]);

  useEffect(() => {
    if (selectedGuess) {
      const timer = setTimeout(() => {
        const modal = document.querySelector('.floating-modal');
        const inputEl = modal?.querySelector<HTMLInputElement>('input.ant-input');
        if (inputEl) {
          inputEl.focus();
          const len = inputEl.value.length;
          requestAnimationFrame(() => {
            inputEl.setSelectionRange(len, len);
          });
        }
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [selectedGuess]);

  useEffect(() => {
    if (!isOpen) return;
    const timer = window.setTimeout(() => {
      inputRef.current?.focus({ cursor: 'end' });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [isOpen]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    if (val === '' && selectedGuess) {
      intentEngine.rejectGuess(selectedGuess.text, '');
      setSelectedGuess(null);
    }
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const apiToLocal = useCallback((msg: ApiChatMessage): ChatMessage => ({
    id: msg._key,
    role: msg.role as 'user' | 'assistant' | 'system',
    content: msg.content,
    timestamp: new Date(msg.created_at),
  }), []);

  const displayMessages = useMemo(() => {
    const apiMessages = storeState.messages.map(apiToLocal);
    return [...localWelcomeMessages, ...apiMessages];
  }, [apiToLocal, localWelcomeMessages, storeState.messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayMessages, storeState.streamingContent]);

  // 頁面切換時僅更新 ref，不再自動發送通知訊息
  useEffect(() => {
    if (pageContext.name === lastPageNameRef.current) return;
    lastPageNameRef.current = pageContext.name;
  }, [pageContext]);

  useEffect(() => {
    if (!modalContext || modalContext.action !== 'open') return;
    if (modalContext.modal === 'AgentFormModal' && modalContext.agent_name) {
      let content = `📝 您正在「${pageContext.name}」頁面，${modalContext.mode === 'edit' ? '編輯' : '建立'} Agent「${modalContext.agent_name}」`;
      if (modalContext.demand?.goal) {
        content += `\n\n需求目標：${modalContext.demand.goal}`;
      }
      if (modalContext.demand?.expected_effect) {
        content += `\n預期效果：${modalContext.demand.expected_effect}`;
      }
      aiqChatStore.addLocalMessage('assistant', content);
    }
    lastModalContextRef.current = modalContext;
  }, [modalContext, pageContext.name]);

  useEffect(() => {
    if (!fullPageContext || !fullPageContext.component) return;
    if (fullPageContext.component === 'AgentFormModal') return;

    let content = `📝 您正在「${fullPageContext.pageName}」`;
    if (fullPageContext.componentName) {
      content += `，${fullPageContext.action === 'editing' ? '編輯' : '建立'}「${fullPageContext.componentName}」`;
    }
    if (fullPageContext.entity && fullPageContext.entityType) {
      content += `\n實體：${fullPageContext.entity}（${fullPageContext.entityType}）`;
    }
    aiqChatStore.addLocalMessage('assistant', content);
  }, [fullPageContext]);

  const handleSuggestionClick = (text: string) => {
    setInputValue(text);
    setTimeout(() => {
      const modal = document.querySelector('.floating-modal');
      const inputEl = modal?.querySelector<HTMLInputElement>('input.ant-input');
      if (inputEl) {
        inputEl.focus();
        const len = inputEl.value.length;
        requestAnimationFrame(() => {
          inputEl.setSelectionRange(len, len);
        });
      }
    }, 50);
  };

  const handleSend = async () => {
    if (!inputValue.trim() || storeState.isStreaming) return;
    
    const confirmedGuess = selectedGuess;
    const isConfirmedMatch = confirmedGuess && inputValue === confirmedGuess.text;
    if (confirmedGuess) {
      if (isConfirmedMatch) {
        intentEngine.confirmGuess(confirmedGuess);
      } else {
        intentEngine.rejectGuess(confirmedGuess.text, inputValue);
      }
      setSelectedGuess(null);
    }

    const userText = inputValue.trim();
    setInputValue('');

    if (isConfirmedMatch && confirmedGuess.strategy && ROUTABLE_STRATEGIES.has(confirmedGuess.strategy)) {
      const userMsgKey = aiqChatStore.addLocalMessage('user', userText);
      const placeholderKey = aiqChatStore.addLocalMessage('assistant', '正在查詢，請稍候...');
      const commitResult = await intentEngine.commitToAgent(confirmedGuess, userText);
      aiqChatStore.removeMessageByKey(placeholderKey);
      if (commitResult.status === 'success' && commitResult.result) {
        const content = formatAgentResult(commitResult.action, commitResult.result);
        aiqChatStore.addLocalMessage('assistant', content);
      } else if (commitResult.error) {
        aiqChatStore.addLocalMessage('assistant', `路由失敗：${commitResult.error}`);
      } else {
        aiqChatStore.removeMessageByKey(userMsgKey);
        await aiqChatStore.sendMessage(userText, buildAssistantContext({
          pathname: window.location.pathname,
          pageContext,
          fullPageContext,
          modalContext,
          intentGuesses,
          recentActions: actionTrail.getTrail(8),
        }));
      }
      return;
    }

    await aiqChatStore.sendMessage(userText, buildAssistantContext({
      pathname: window.location.pathname,
      pageContext,
      fullPageContext,
      modalContext,
      intentGuesses,
      recentActions: actionTrail.getTrail(8),
    }));
  };

  const transformOriginX = buttonPosition.x - position.x + 28;
  const transformOriginY = buttonPosition.y - position.y + 28;

  const modalStyle: React.CSSProperties = fullscreen
    ? {
        left: '10vw',
        top: '10vh',
        width: '80vw',
        height: '80vh',
        transform: 'none',
      }
    : {
        left: `${position.x}px`,
        top: `${position.y}px`,
        width: `${size.width}px`,
        height: `${size.height}px`,
        transformOrigin: `${transformOriginX}px ${transformOriginY}px`,
};

  const renderMessage = (msg: ChatMessage) => {
    const timeStr = msg.timestamp.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
    
    if (msg.role === 'system') {
      return (
        <div key={msg.id} className="floating-bubble-system">
          {msg.content}
        </div>
      );
    }

    const bubbleClass = msg.role === 'user' ? 'floating-bubble-user' : 'floating-bubble-ai';
    
    return (
      <div key={msg.id} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
        <div className={bubbleClass}>
          <MarkdownContent content={msg.content} />
        </div>
        <div className="floating-bubble-time">{timeStr}</div>
      </div>
    );
  };

  const hasGuesses = intentGuesses.length > 0;

  const modalNode = (
    <div
      className={`floating-modal ${isOpen ? 'open' : ''}`}
      style={{ ...modalStyle, zIndex: 11000, position: 'fixed' }}
    >
      <div 
        className="floating-modal-header"
        onMouseDown={handleHeaderMouseDown}
        onTouchStart={handleHeaderMouseDown}
      >
        <div className="floating-modal-title">
          <Avatar 
            size="small" 
            src={avatarSrc}
            icon={!avatarSrc ? <RobotOutlined /> : undefined}
          />
          <span>艾企</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {isAdmin && (
            <AdminDropdown menuItems={adminMenuItems} onMenuClick={handleAdminMenuClick} />
          )}
          <Button
            type="text"
            icon={<PlusOutlined />}
            size="small"
            title="開始新對話"
             style={{ color: 'rgba(255,255,255,0.65)', fontSize: 14 }}
            onClick={() => {
              setLocalWelcomeMessages(buildWelcomeMessages());
               setInputValue('');
               setSelectedGuess(null);
               setCurrentView('chat');
               aiqChatStore.setActiveSessionKey(null);
               aiqChatStore.resetCurrentSession();
             }}
             onMouseDown={(e) => e.stopPropagation()}
             onTouchStart={(e) => e.stopPropagation()}
          />
          <Tooltip title={fullscreen ? '還原' : '放大'}><Button type="text" icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />} size="small" onClick={() => setFullscreen(f => !f)} onMouseDown={(e) => e.stopPropagation()} onTouchStart={(e) => e.stopPropagation()} style={{ color: 'rgba(255,255,255,0.65)', fontSize: 14 }} /></Tooltip>
          <Button 
            type="text" 
            icon={<CloseOutlined />} 
            size="small" 
            onClick={onClose}
            onMouseDown={(e) => e.stopPropagation()} 
            onTouchStart={(e) => e.stopPropagation()} 
          />
        </div>
      </div>
      
      <div className="floating-modal-body">
        {currentView !== 'chat' ? (
          <ChatHistoryPanel
            currentView={currentView}
            intentHistory={intentHistory}
            actionHistory={actionHistory}
            onBackToChat={() => setCurrentView('chat')}
          />
        ) : (
          <>
            {displayMessages.map(renderMessage)}
            {storeState.isStreaming && storeState.streamingContent && (
              <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <div className="floating-bubble-ai">
                  <MarkdownContent content={storeState.streamingContent} />
                </div>
              </div>
            )}
            {storeState.isStreaming && !storeState.streamingContent && (
              <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <div className="floating-bubble-ai">
                  <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} /> 思考中...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {pageContext.suggestions.length > 0 && (
        <div className="floating-modal-suggestions">
          {pageContext.suggestions.map((text) => (
            <button
              key={text}
              className="floating-suggestion-btn"
              onClick={() => handleSuggestionClick(text)}
            >
              {text}
            </button>
          ))}
        </div>
      )}
      
      <div className="floating-modal-footer">
        {hasGuesses ? (
          <Button 
            type="text" 
            icon={<BulbOutlined style={{ fontSize: 16 }} />} 
            className={`intent-guess-btn ${intentPanelOpen ? 'active' : ''}`}
            onClick={onIntentPanelToggle}
          />
        ) : (
          <Tooltip title="操作更多后可使用意图猜测">
            <Button 
              type="text" 
              icon={intentLoading ? <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} /> : <BulbOutlined style={{ fontSize: 16 }} />} 
              className="intent-guess-btn disabled"
              disabled
            />
          </Tooltip>
        )}
        <Dropdown
          menu={{
            items: attachmentMenuItems,
            className: 'attachment-dropdown-menu',
          }}
          placement="topLeft"
          trigger={['click']}
          styles={{ root: { zIndex: 9999 } }}
        >
          <Button
            type="text"
            icon={<PaperClipOutlined style={{ fontSize: 16, color: 'rgba(255,255,255,0.65)' }} />}
          />
        </Dropdown>
        <Input
          ref={inputRef}
          placeholder="输入消息...（支持 Markdown）"
          value={inputValue}
          onChange={handleInputChange}
          onPressEnter={() => {
            if (storeState.isStreaming) return;
            void handleSend();
          }}
        />
        <Button 
          type="primary" 
          icon={<SendOutlined />} 
          onClick={() => void handleSend()}
          disabled={storeState.isStreaming}
        />
        <input 
          type="file" 
          ref={fileInputRef} 
          style={{ display: 'none' }} 
          accept=".pdf,.doc,.docx,.txt,.xlsx,.csv" 
          onChange={handleFileSelect} 
        />
        <input 
          type="file" 
          ref={imageInputRef} 
          style={{ display: 'none' }} 
          accept="image/*" 
          onChange={handleImageSelect} 
        />
      </div>

      <div 
        className="floating-modal-resize"
        onMouseDown={handleResizeMouseDown}
      />
    </div>
  );

  const visibleAntModal = Array.from(document.querySelectorAll<HTMLElement>('.ant-modal'))
    .find((el) => window.getComputedStyle(el).display !== 'none');

  const portalTarget = visibleAntModal ?? document.body;

  return createPortal(modalNode, portalTarget);
}
