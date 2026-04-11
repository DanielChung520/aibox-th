/**
 * @file        任務會話聊天頁
 * @description 純聊天模式，整合 ChatStore、Provider 選擇與 SSE 串流
 * @lastUpdate  2026-03-27 22:39:59
 * @author      Daniel Chung
 * @version     1.3.0
 */

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { Input, Dropdown, Tag, message } from 'antd';
import type { MenuProps } from 'antd';
import { PlusOutlined, PaperClipOutlined, SmileOutlined, AudioOutlined, SendOutlined, StopOutlined, RobotOutlined, EditOutlined, DeleteOutlined, VerticalAlignBottomOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { chatStore } from '../stores/chatStore';
import { chatOrchestrator } from '../stores/chatOrchestrator';
import { subscribeSessionFileStatus, type SSEConnection } from '../services/sseManager';
import MessageBubble from '../components/MessageBubble';
import ToolCallDisplay from '../components/ToolCallDisplay';

export default function TaskSessionChat() {
  const { sessionKey: urlSessionKey } = useParams<{ sessionKey?: string }>();
  const navigate = useNavigate();
  const contentTokens = useContentTokens();
  const [storeState, setStoreState] = useState(chatStore.getState());
  const [orchState, setOrchState] = useState(chatOrchestrator.getState());
  const [inputValue, setInputValue] = useState('');
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [queue, setQueue] = useState<string[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set());
  const chatEndRef = useRef<HTMLDivElement>(null);
  const connectionRef = useRef<SSEConnection | null>(null);
  const fileSSEConnectionRef = useRef<SSEConnection | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const prevStreamingRef = useRef(storeState.isStreaming);

  useEffect(() => {
    const unsubChat = chatStore.subscribe(() => setStoreState(chatStore.getState()));
    const unsubOrch = chatOrchestrator.subscribe(() => setOrchState(chatOrchestrator.getState()));
    return () => { unsubChat(); unsubOrch(); };
  }, []);

  useEffect(() => {
    void chatStore.loadProviders();
    void chatStore.loadChatDefaults();
    void chatStore.loadSessions();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [storeState.messages, storeState.streamingContent, storeState.isStreaming, queue]);

  // 根據 URL sessionKey 載入對話與訂閱檔案狀態
  const loadedSessionKeyRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const sessionKey = urlSessionKey;
    // 避免重複載入同一個 session
    if (sessionKey === loadedSessionKeyRef.current) return;
    loadedSessionKeyRef.current = sessionKey;

    fileSSEConnectionRef.current?.abort();
    fileSSEConnectionRef.current = null;

    if (!sessionKey) {
      // 沒有指定 sessionKey 時，嘗試導航到最近的 session
      chatStore.setActiveSessionKey(null);
      chatStore.resetCurrentSession();
      void chatStore.loadSessions().then(() => {
        const sessions = chatStore.getState().sessions;
        if (sessions.length === 0) return;
        const sorted = [...sessions].sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
        );
        navigate(`/app/task-session/chat/${sorted[0]._key}`, { replace: true });
      });
      return;
    }

    void chatStore.loadSessionMessages(sessionKey);
    const conn = subscribeSessionFileStatus(sessionKey, {
      onFileStatus: (payload) => {
        chatStore.applyFileStatusUpdate(payload);
      },
      onError: () => {},
    });
    fileSSEConnectionRef.current = conn;

    return () => {
      conn.abort();
    };
  }, [urlSessionKey]);

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const sessionKey = storeState.activeSessionKey;
    if (!sessionKey) {
      message.error('請先選擇或建立聊天會話');
      return;
    }
    for (const file of Array.from(files)) {
      setUploadingFiles((prev) => new Set(prev).add(file.name));
      try {
        await chatStore.uploadFile(sessionKey, file);
      } catch (err: any) {
        message.error(err.response?.data?.message || '上傳失敗');
      } finally {
        setUploadingFiles((prev) => {
          const next = new Set(prev);
          next.delete(file.name);
          return next;
        });
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDeleteFile = async (fileKey: string) => {
    const sessionKey = storeState.activeSessionKey;
    if (!sessionKey) return;
    try {
      await chatStore.deleteFile(sessionKey, fileKey);
    } catch (err: any) {
      message.error(err.response?.data?.message || '刪除失敗');
    }
  };

  const handleNewSession = () => {
    chatStore.resetCurrentSession();
    chatStore.setActiveSessionKey(null);
    fileSSEConnectionRef.current?.abort();
    fileSSEConnectionRef.current = null;
  };

  const inputBarIcons = [
    { icon: <AudioOutlined />, key: 'voice' },
    { icon: <SmileOutlined />, key: 'emoji' },
  ];

  const providerItems: MenuProps['items'] = useMemo(
    () => {
      const auto = [{ key: '__auto__', label: '自動' }];
      const list = storeState.providers.map((provider) => {
        const isLocal = provider.base_url.includes('localhost') || provider.base_url.includes('127.0.0.1');
        const hasApiKey = Boolean(provider.api_key?.trim());
        return { key: provider.code, label: provider.name, disabled: provider.status !== 'enabled' || (!isLocal && !hasApiKey) };
      });
      return [...auto, ...list];
    },
    [storeState.providers],
  );

  const providerDisplayName = useMemo(() => {
    if (!storeState.selectedProvider) return '自動';
    const provider = storeState.providers.find((item) => item.code === storeState.selectedProvider);
    return provider?.name ?? '自動';
  }, [storeState.selectedProvider, storeState.providers]);

  const handleProviderSelect: MenuProps['onClick'] = ({ key }) => {
    if (key === '__auto__') {
      chatStore.setSelectedProvider(null);
    } else {
      chatStore.setSelectedProvider(key);
    }
  };

  const greetingVisible = storeState.messages.length === 0 && !storeState.isStreaming && Boolean(storeState.greeting);

  const displayMessages = storeState.messages;

  const sendNow = async (text: string) => {
    chatOrchestrator.handleSendStart();
    const connection = await chatStore.sendMessage(text);
    connectionRef.current = connection;
  };

  const handleSend = async (queuedText?: string) => {
    const text = (queuedText ?? inputValue).trim();
    if (!text) return;
    if (storeState.isStreaming) {
      setQueue((prev) => [...prev, text]);
      if (!queuedText) setInputValue('');
      return;
    }

    if (editingKey) {
      setEditingKey(null);
      setInputValue('');
      const conn = await chatStore.editAndResend(editingKey, text);
      connectionRef.current = conn;
      return;
    }

    if (!queuedText) setInputValue('');
    await sendNow(text);
  };

  const handleCancelEdit = () => {
    setEditingKey(null);
    setInputValue('');
  };

  const handleScrollToLastUserMsg = () => {
    const lastUserMsg = [...displayMessages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg) {
      document.getElementById(`msg-${lastUserMsg._key}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  useEffect(() => {
    const wasStreaming = prevStreamingRef.current;
    const isStreaming = storeState.isStreaming;
    prevStreamingRef.current = isStreaming;
    if (!wasStreaming && isStreaming) {
      chatOrchestrator.handleStreamStart();
    }
    if (wasStreaming && !isStreaming) {
      chatOrchestrator.handleDone();
      connectionRef.current = null;
      if (queue.length > 0) {
        const [next, ...rest] = queue;
        setQueue(rest);
        void sendNow(next);
      }
    }
  }, [storeState.isStreaming, queue]);

  useEffect(() => () => connectionRef.current?.abort(), []);

  const handleStop = () => {
    connectionRef.current?.abort();
    connectionRef.current = null;
    chatStore.stopStreaming();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: contentTokens.colorBgBase, color: contentTokens.colorTextBase, fontFamily: 'Inter, "PingFang SC", -apple-system, sans-serif', overflow: 'hidden' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 16px', scrollbarWidth: 'thin', scrollbarColor: `${contentTokens.textSecondary} transparent` }}>
        {greetingVisible && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 24 }}>
            <div style={{ maxWidth: '70%', background: contentTokens.chatAssistantBubble, borderRadius: 8, borderLeft: `3px solid ${contentTokens.colorPrimary}`, padding: '10px 12px', fontSize: 14, lineHeight: 1.6, color: contentTokens.colorTextBase }}>
              {storeState.greeting}
            </div>
          </div>
        )}

        {displayMessages.map((msg) => (
          <div key={msg._key} id={`msg-${msg._key}`}>
            <MessageBubble
              message={msg}
              onCopyToInput={msg.role === 'user' ? (text: string) => setInputValue(text) : undefined}
            />
          </div>
        ))}

        {storeState.isStreaming && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
            {storeState.streamingContent ? (
              <MessageBubble
                message={{ _key: 'streaming', session_key: '', role: 'assistant', content: storeState.streamingContent, tokens: null, created_at: '' }}
                streamingContent={storeState.streamingContent}
                streamingThinking={storeState.streamingThinking}
              />
            ) : (
              <div style={{ display: 'flex', gap: 4, padding: '10px 12px' }}>
                {[0, 1, 2].map((i) => (
                  <span key={i} style={{ width: 8, height: 8, borderRadius: '50%', background: contentTokens.textSecondary, animation: 'dotBounce 1.4s ease-in-out infinite', animationDelay: `${i * 0.16}s` }} />
                ))}
              </div>
            )}
          </div>
        )}

        {orchState.currentToolCalls.length > 0 && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8, paddingLeft: 8 }}>
            <ToolCallDisplay toolCalls={orchState.currentToolCalls} />
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {(storeState.uploadedFiles.length > 0 || uploadingFiles.size > 0) && (
        <div style={{
          padding: '0 16px 8px',
          flexShrink: 0,
          maxHeight: 80,
          overflowY: 'auto',
          borderTop: `1px solid ${contentTokens.chatInputBg}`,
          background: contentTokens.colorBgBase,
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, paddingTop: 6 }}>
          {storeState.uploadedFiles.map((file) => (
            <div key={file.file_key} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '2px 8px',
              borderRadius: 4,
              background: `${contentTokens.chatInputBg}cc`,
              border: `1px solid ${contentTokens.chatInputBg}`,
              fontSize: 12,
            }}>
              <span style={{ color: contentTokens.colorTextBase, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {file.filename}
              </span>
              <Tag style={{ margin: 0, fontSize: 10, padding: '0 2px', lineHeight: '16px' }}
                color={file.vector_status === 'completed' ? 'green' : file.vector_status === 'failed' ? 'red' : 'blue'}
              >
                V:{file.vector_status}
              </Tag>
              <Tag style={{ margin: 0, fontSize: 10, padding: '0 2px', lineHeight: '16px' }}
                color={file.graph_status === 'completed' ? 'green' : file.graph_status === 'failed' ? 'red' : 'blue'}
              >
                G:{file.graph_status}
              </Tag>
              <DeleteOutlined
                onClick={() => void handleDeleteFile(file.file_key)}
                style={{ color: contentTokens.textSecondary, cursor: 'pointer', fontSize: 10 }}
              />
            </div>
          ))}
          {Array.from(uploadingFiles).map((name) => (
            <div key={name} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '2px 8px',
              borderRadius: 4,
              background: `${contentTokens.chatInputBg}cc`,
              border: `1px solid ${contentTokens.colorPrimary}40`,
              fontSize: 12,
            }}>
              <span style={{ color: contentTokens.colorTextBase, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {name}
              </span>
              <Tag style={{ margin: 0, fontSize: 10, padding: '0 2px', lineHeight: '16px' }} color="orange">
                上傳中...
              </Tag>
            </div>
          ))}
          </div>
        </div>
      )}

      <div style={{ padding: '12px 16px', borderTop: `1px solid ${contentTokens.chatInputBg}`, flexShrink: 0 }}>
        {editingKey && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, padding: '4px 10px', background: `${contentTokens.colorPrimary}18`, borderRadius: 6, fontSize: 12, color: contentTokens.colorPrimary }}>
            <EditOutlined />
            <span>編輯模式</span>
            <button onClick={handleCancelEdit} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: contentTokens.colorPrimary, fontSize: 12 }}>
              取消
            </button>
          </div>
        )}
        <div style={{ position: 'relative' }}>
          <Input.TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={editingKey ? '修改訊息內容，按 Ctrl+Enter 送出...' : '輸入您的問題，按 Ctrl+Enter 送出...'}
            autoSize={{ minRows: 3, maxRows: 3 }}
            style={{ width: '100%', background: contentTokens.chatInputBg, border: `1px solid ${editingKey ? contentTokens.colorPrimary : contentTokens.chatInputBg}`, borderRadius: 8, color: contentTokens.colorTextBase, fontSize: 14, padding: '8px 120px 8px 12px', resize: 'none' }}
          />
          <div style={{ position: 'absolute', top: 6, right: 8, display: 'flex', gap: 4, alignItems: 'center' }}>
            <span
              onClick={handleNewSession}
              style={{ fontSize: 14, color: contentTokens.iconDefault, cursor: 'pointer', transition: 'color 0.2s', padding: '2px 4px' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = contentTokens.iconHover; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = contentTokens.iconDefault; }}
            >
              <PlusOutlined />
            </span>
            <Dropdown menu={{ items: providerItems, onClick: handleProviderSelect }} trigger={['click']}>
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '2px 8px',
                  borderRadius: 4,
                  background: `${contentTokens.colorPrimary}18`,
                  color: contentTokens.colorPrimary,
                  fontSize: 11,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  maxWidth: 120,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  border: `1px solid ${contentTokens.colorPrimary}40`,
                }}
              >
                <RobotOutlined style={{ fontSize: 10, flexShrink: 0 }} />
                {providerDisplayName}
              </span>
            </Dropdown>
            {inputBarIcons.map((item) => (
              <span
                key={item.key}
                style={{ fontSize: 14, color: contentTokens.iconDefault, cursor: 'pointer', transition: 'color 0.2s', padding: '2px 4px' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = contentTokens.iconHover; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = contentTokens.iconDefault; }}
              >
                {item.icon}
              </span>
            ))}
            <span
              onClick={handleAttachClick}
              style={{ fontSize: 14, color: contentTokens.iconDefault, cursor: 'pointer', transition: 'color 0.2s', padding: '2px 4px' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = contentTokens.iconHover; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = contentTokens.iconDefault; }}
            >
              <PaperClipOutlined />
            </span>
            <span
              onClick={handleScrollToLastUserMsg}
              title="定位到最後發問"
              style={{ fontSize: 14, color: contentTokens.iconDefault, cursor: 'pointer', transition: 'color 0.2s', padding: '2px 4px' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = contentTokens.iconHover; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = contentTokens.iconDefault; }}
            >
              <VerticalAlignBottomOutlined />
            </span>
            <span
              onClick={storeState.isStreaming ? handleStop : () => void handleSend()}
              style={{ fontSize: 16, color: storeState.isStreaming ? contentTokens.btnClear : (inputValue.trim() ? contentTokens.btnSend : contentTokens.iconDefault), cursor: storeState.isStreaming || inputValue.trim() ? 'pointer' : 'not-allowed', transition: 'color 0.2s', padding: '2px 4px' }}
              onMouseEnter={(e) => {
                if (storeState.isStreaming) e.currentTarget.style.color = contentTokens.btnClearHover;
                else if (inputValue.trim()) e.currentTarget.style.color = contentTokens.btnSendHover;
              }}
              onMouseLeave={(e) => {
                if (storeState.isStreaming) e.currentTarget.style.color = contentTokens.btnClear;
                else if (inputValue.trim()) e.currentTarget.style.color = contentTokens.btnSend;
              }}
            >
              {storeState.isStreaming ? <StopOutlined /> : <SendOutlined />}
            </span>
          </div>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      <style>{`
        @keyframes dotBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-6px); opacity: 1; }
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${contentTokens.textSecondary}; border-radius: 2px; }
      `}</style>
    </div>
  );
}
