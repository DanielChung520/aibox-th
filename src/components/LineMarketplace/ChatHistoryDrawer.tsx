import { useState, useEffect, useMemo, useRef } from 'react';
import { Drawer, Input, Spin, Empty, Typography, Tabs, DatePicker, Image, Modal, List, Button, theme, Space } from 'antd';
import { SearchOutlined, MessageOutlined, PictureOutlined, FileOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import type { LINEChannel } from '../../services/api';
import { ragicApi, RagicHistoryMessage } from '../../services/api';
import { resolveChannelIconSrc } from '../../utils/avatarUtils';
import dayjs from 'dayjs';

const { Text } = Typography;

interface ChatSession {
  session_id: string;
  platform: string;
  message_count: number;
  first_message_at: string;
  last_message_at: string;
  group_name?: string;
  user_name?: string;
}

function sessionLabel(s: ChatSession): string {
  const sid = s.session_id;
  if (sid.includes(':group:')) {
    if (s.group_name) return `👥 ${s.group_name}`;
    return `👥 群組 ${sid.split(':')[3]?.slice(0, 8) || '?'}`;
  }
  if (s.user_name) return `💬 ${s.user_name}`;
  return `💬 ${sid.split(':')[2]?.slice(0, 10) || '?'}`;
}

interface ChatHistoryDrawerProps {
  visible: boolean;
  onClose: () => void;
  channel: LINEChannel;
}

export default function ChatHistoryDrawer({ visible, onClose, channel }: ChatHistoryDrawerProps) {
  const { token } = theme.useToken();
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<RagicHistoryMessage[]>([]);
  const [searchText, setSearchText] = useState('');
  const [activeTab, setActiveTab] = useState('chat');
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Sessions
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string>('');

  useEffect(() => {
    if (visible && channel._key) {
      loadSessions();
    } else {
      setMessages([]);
      setSessions([]);
      setActiveSessionId('');
      setSearchText('');
      setActiveTab('chat');
    }
  }, [visible, channel._key]);

  const loadSessions = async () => {
    setSessionsLoading(true);
    try {
      const res = await ragicApi.listSessions('line', channel._key);
      const items = (res.data.sessions || []) as ChatSession[];
      setSessions(items);
      if (items.length > 0 && !activeSessionId) {
        setActiveSessionId(items[0].session_id);
      }
    } catch {
      setSessions([]);
    } finally {
      setSessionsLoading(false);
    }
  };

  useEffect(() => {
    if (!activeSessionId) return;
    fetchHistory(activeSessionId);
  }, [activeSessionId]);

  const fetchHistory = async (sessionId: string) => {
    setLoading(true);
    try {
      const response = await ragicApi.getChatHistory(sessionId, 100);
      setMessages(response.data.history || []);
    } catch {
      setMessages([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredMessages = useMemo(() => {
    if (!searchText.trim()) return messages;
    const lowerSearch = searchText.toLowerCase();
    return messages.filter((msg) =>
      msg.content?.toLowerCase().includes(lowerSearch)
    );
  }, [messages, searchText]);

  const groupedMessages = useMemo(() => {
    const todayStr = dayjs().format('YYYY-MM-DD');
    const yesterdayStr = dayjs().subtract(1, 'day').format('YYYY-MM-DD');
    const groupMap = new Map<string, RagicHistoryMessage[]>();

    filteredMessages.forEach((msg) => {
      const ts = msg.timestamp || msg.created_at;
      const dateKey = ts ? dayjs(ts).format('YYYY-MM-DD') : '未知時間';
      let displayDate = dateKey;
      if (dateKey === todayStr) displayDate = '今天';
      else if (dateKey === yesterdayStr) displayDate = '昨天';
      if (!groupMap.has(displayDate)) groupMap.set(displayDate, []);
      groupMap.get(displayDate)!.push(msg);
    });
    return Array.from(groupMap.entries());
  }, [filteredMessages]);

  const imageMessages = useMemo(() => {
    return messages.filter((msg) => {
      const meta = msg.metadata;
      return meta?.media_type === 'image' && (meta.media_url || meta.seaweed_url);
    });
  }, [messages]);

  const fileMessages = useMemo(() => {
    return messages.filter((msg) => {
      const meta = msg.metadata;
      return meta?.file_name && meta?.file_url;
    });
  }, [messages]);

  const dateList = useMemo(() => {
    const dates = new Set<string>();
    messages.forEach((msg) => {
      const ts = msg.timestamp || msg.created_at;
      if (ts) dates.add(dayjs(ts).format('YYYY-MM-DD'));
    });
    return Array.from(dates).sort().reverse();
  }, [messages]);

  const scrollToDate = (dateStr: string) => {
    const el = document.getElementById(`date-${dateStr}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const iconSrc = resolveChannelIconSrc(channel.channel_icon);

  const DrawerTitle = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8, background: token.colorSuccessBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
          border: `1px solid ${token.colorSuccessBorder}`
        }}>
          {iconSrc ? (
            <img src={iconSrc} alt={channel.channel_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <MessageOutlined style={{ color: token.colorSuccess, fontSize: 18 }} />
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Text strong style={{ fontSize: 16, lineHeight: 1.2, color: token.colorTextHeading }}>{channel.channel_name}</Text>
          <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.2 }}>LINE 對話歷史記錄</Text>
        </div>
      </div>
      <Button
        type="text"
        icon={<ReloadOutlined spin={loading} />}
        onClick={loadSessions}
        loading={sessionsLoading || loading}
        title="刷新歷史記錄"
        style={{ color: token.colorTextSecondary }}
      />
    </div>
  );

  const chatTab = (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      <div style={{ 
        padding: '12px 16px', 
        borderBottom: `1px solid ${token.colorBorderSecondary}`, 
        display: 'flex', 
        gap: 12,
        background: token.colorBgElevated,
        zIndex: 1
      }}>
        <DatePicker
          placeholder="跳轉日期"
          format="MM/DD"
          onChange={(date) => { if (date) scrollToDate(date.format('YYYY-MM-DD')); }}
          disabledDate={(d) => d && !dateList.includes(d.format('YYYY-MM-DD'))}
          style={{ width: 120 }}
        />
        <Input
          prefix={<SearchOutlined style={{ color: token.colorTextDescription }} />}
          placeholder="搜尋對話..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ flex: 1 }}
        />
      </div>
        {/* Sessions tab bar */}
        {sessions.length > 1 && (
          <div style={{
            padding: '8px 16px',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            background: token.colorBgContainer,
            overflowX: 'auto',
            whiteSpace: 'nowrap',
          }}>
            {sessionsLoading ? <Spin size="small" /> : sessions.map((s) => (
              <Button
                key={s.session_id}
                type={activeSessionId === s.session_id ? 'primary' : 'default'}
                size="small"
                onClick={() => { setActiveSessionId(s.session_id); setSearchText(''); }}
                style={{ marginRight: 8, marginBottom: 4 }}
              >
                {sessionLabel(s)}
                <span style={{ fontSize: 10, marginLeft: 4, color: token.colorTextDescription }}>
                  ({s.message_count})
                </span>
              </Button>
            ))}
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 16px' }} ref={scrollRef}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spin size="large" /></div>
        ) : filteredMessages.length === 0 ? (
          <Empty description="尚無對話記錄" style={{ marginTop: 60 }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          groupedMessages.map(([date, msgs]) => {
            const dateId = date === '今天' ? dayjs().format('YYYY-MM-DD')
              : date === '昨天' ? dayjs().subtract(1, 'day').format('YYYY-MM-DD')
              : date;
            return (
              <div key={date} id={`date-${dateId}`} style={{ marginBottom: 32 }}>
                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                  <Text type="secondary" style={{ 
                    fontSize: 12, 
                    background: token.colorFillAlter, 
                    padding: '4px 12px', 
                    borderRadius: 16 
                  }}>
                    {date}
                  </Text>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  {msgs.map((msg, idx) => {
                    const isSystem = msg.role === 'system';
                    if (isSystem) {
                      return (
                        <div key={idx} style={{ textAlign: 'center', marginBottom: 24 }}>
                          <Text type="secondary" style={{
                            fontSize: 12,
                            background: token.colorFillAlter,
                            padding: '8px 16px',
                            borderRadius: 12,
                            display: 'inline-block',
                            maxWidth: '90%',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}>
                            {msg.content}
                          </Text>
                        </div>
                      );
                    }
                    const isUser = msg.role === 'user';
                    return (
                      <div key={idx} style={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: isUser ? 'flex-start' : 'flex-end', 
                        width: '100%' 
                      }}>
                        <div style={{ 
                          display: 'flex', 
                          alignItems: 'flex-end', 
                          gap: 8, 
                          maxWidth: '85%', 
                          flexDirection: isUser ? 'row' : 'row-reverse' 
                        }}>
                          <div style={{
                            padding: '12px 16px',
                            borderRadius: 16,
                            borderTopLeftRadius: isUser ? 4 : 16,
                            borderTopRightRadius: !isUser ? 4 : 16,
                            background: isUser ? token.colorBgContainer : token.colorSuccess,
                            color: isUser ? token.colorText : '#fff',
                            border: isUser ? `1px solid ${token.colorBorderSecondary}` : 'none',
                            boxShadow: token.boxShadowTertiary,
                            wordBreak: 'break-word',
                            whiteSpace: 'pre-wrap',
                            fontSize: 14,
                            lineHeight: 1.6
                          }}>
                            {msg.content}
                          </div>
                          <Text type="secondary" style={{ fontSize: 12, flexShrink: 0, color: token.colorTextDescription }}>
                            {msg.timestamp || msg.created_at ? dayjs(msg.timestamp || msg.created_at).format('HH:mm') : ''}
                          </Text>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
        <div ref={chatEndRef} />
      </div>
    </div>
  );

  const imageTab = (
    <div style={{ padding: 24, overflowY: 'auto', flex: 1 }}>
      {imageMessages.length === 0 ? (
        <Empty description="尚無圖片" style={{ marginTop: 60 }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {imageMessages.map((msg, idx) => {
            const url = msg.metadata?.media_url || msg.metadata?.seaweed_url || '';
            return (
              <div
                key={idx}
                style={{ 
                  aspectRatio: '1', 
                  overflow: 'hidden', 
                  borderRadius: 12, 
                  cursor: 'pointer', 
                  border: `1px solid ${token.colorBorderSecondary}`,
                  boxShadow: token.boxShadowTertiary
                }}
                onClick={() => setPreviewImage(url)}
              >
                <Image src={url} alt={`圖片 ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} preview={false} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const fileTab = (
    <div style={{ padding: '12px 24px', overflowY: 'auto', flex: 1 }}>
      {fileMessages.length === 0 ? (
        <Empty description="尚無文件" style={{ marginTop: 60 }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          dataSource={fileMessages}
          renderItem={(msg, idx) => {
            const meta = msg.metadata || {};
            const fileName = meta.file_name || `文件 ${idx + 1}`;
            const fileUrl = meta.file_url || '';
            const fileSize = meta.file_size ? formatFileSize(meta.file_size) : '';
            const ts = msg.timestamp || msg.created_at;
            return (
              <List.Item 
                style={{ padding: '16px 0', borderBottom: `1px solid ${token.colorBorderSecondary}` }}
                actions={[<Button key="download" type="text" icon={<DownloadOutlined />} onClick={() => window.open(fileUrl, '_blank')} />]}
              >
                <List.Item.Meta
                  avatar={<div style={{ 
                    width: 40, 
                    height: 40, 
                    borderRadius: 8, 
                    background: token.colorPrimaryBg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <FileOutlined style={{ fontSize: 20, color: token.colorPrimary }} />
                  </div>}
                  title={<Text strong style={{ fontSize: 14 }}>{fileName}</Text>}
                  description={<Text type="secondary" style={{ fontSize: 12 }}>{fileSize && `${fileSize} • `}{ts ? dayjs(ts).format('YYYY-MM-DD HH:mm') : ''}</Text>}
                />
              </List.Item>
            );
          }}
        />
      )}
    </div>
  );

  return (
    <>
      <Drawer
        title={DrawerTitle}
        placement="right"
        size="large"
        onClose={onClose}
        open={visible}
        styles={{
          header: { padding: '16px 24px', borderBottom: `1px solid ${token.colorBorderSecondary}` },
          body: { padding: 0, overflowY: 'auto', height: '100%' }
        }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            { key: 'chat', label: <Space><MessageOutlined /> 對話</Space>, children: chatTab },
            { key: 'image', label: <Space><PictureOutlined /> 圖片 {imageMessages.length > 0 && `(${imageMessages.length})`}</Space>, children: imageTab },
            { key: 'file', label: <Space><FileOutlined /> 文件 {fileMessages.length > 0 && `(${fileMessages.length})`}</Space>, children: fileTab },
          ]}
          style={{ height: '100%' }}
          tabBarStyle={{ padding: '0 24px', marginBottom: 0, background: token.colorBgContainer }}
        />
      </Drawer>
      <Modal open={!!previewImage} footer={null} onCancel={() => setPreviewImage(null)} centered width={600} styles={{ body: { padding: 0 } }}>
        <img src={previewImage || ''} alt="預覽" style={{ width: '100%', display: 'block', borderRadius: 8 }} />
      </Modal>
    </>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
