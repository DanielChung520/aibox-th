/**
 * @file        LineAssistantPage.tsx
 * @description LINE 助手管理頁面 — 業務員專用的 LINE Bot 後台
 * @lastUpdate  2026-06-14
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Tabs, Table, Button, Tag, Modal, Form, Input, Select, Switch,
         Typography, Avatar, App, Radio, Divider, Space } from 'antd';
import {
  MessageOutlined, ClockCircleOutlined, UserOutlined,
  SendOutlined, PlusOutlined, PictureOutlined, ReloadOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { pageContextManager } from '../../services/PageContextManager';
import apiClient, { crmApi, MessageSchedule, CreateSchedulePayload, UpdateSchedulePayload } from '../../services/api';

const { Text } = Typography;

/* ─── Mock Data ─────────────────────────────────── */

const MOCK_PENDING = [
  { key: '1', lineId: 'U1234', name: '陳董', phone: '0912-345-678', company: '某某企業', status: 'pending', channel: 'ch_a' },
  { key: '2', lineId: 'U5678', name: '林總', phone: '0933-111-222', company: '某木集團', status: 'confirmed', channel: 'ch_b' },
];

const MOCK_VISITS = [
  { key: '1', customer: '陳董', date: '2026-06-17', time: '10:00', location: '台北市大安區', status: 'planned' },
  { key: '2', customer: '林經理', date: '2026-06-17', time: '14:00', location: '新北市板橋區', status: 'planned' },
  { key: '3', customer: '張老闆', date: '2026-06-15', time: '已拜訪', location: '桃園市中壢區', status: 'done' },
];

/* ─── Tab Components ────────────────────────────── */

function ConversationView() {
  const { message: msgApi } = App.useApp();
  const [search, setSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedContact, setSelectedContact] = useState<any>(null);
  const [selectedChannel, setSelectedChannel] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [imageUploading, setImageUploading] = useState(false);
  const msgsEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadContacts = useCallback(() => {
    setLoading(true);
    apiClient.get('/api/v1/bot-contacts')
      .then((res: any) => setContacts(res.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadContacts(); }, [loadContacts]);

  const loadMessages = useCallback(async (userId: string) => {
    setMsgLoading(true);
    try {
      const res = await apiClient.get(`/api/v1/bot-messages/${userId}`);
      setMessages(res.data?.data || []);
    } catch { setMessages([]); }
    setMsgLoading(false);
  }, []);

  useEffect(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const selectContact = (c: any) => {
    setSelectedId(c.user_id);
    setSelectedContact(c);
    setSelectedChannel(c.channels?.[0] || null);
    loadMessages(c.user_id);
  };

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !selectedContact || !selectedChannel) return;
    setSending(true);
    setInputText('');
    const optimistic = { role: 'assistant', message: text, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, optimistic]);
    try {
      const res = await apiClient.post('/api/v1/bot-push', {
        user_id: selectedContact.user_id,
        message: text,
        channel_key: selectedChannel.key,
      });
      const data = res.data || {};
      if (data.code) msgApi.success('訊息已送出');
      else msgApi.warning(`LINE API 回應異常: ${data.line_status}`);
    } catch { msgApi.error('發送失敗（連線異常）'); }
    setSending(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleDeleteChat = (e: React.MouseEvent, userId: string) => {
    e.stopPropagation();
    Modal.confirm({
      title: '刪除聊天記錄',
      content: '確定刪除此聯絡人的所有聊天記錄？',
      onOk: async () => {
        try {
          await apiClient.delete(`/api/v1/bot-messages/${userId}`);
          msgApi.success('已刪除');
          if (selectedId === userId) { setSelectedId(null); setSelectedContact(null); }
          loadContacts();
        } catch { msgApi.error('刪除失敗'); }
      },
    });
  };

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedContact || !selectedChannel) return;
    setImageUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const uploadRes = await apiClient.post('/api/v1/upload/line-image', form);
      const imgUrl = uploadRes.data?.data?.url;
      if (!imgUrl) { msgApi.error('圖片上傳失敗'); return; }
      const optimistic = { role: 'assistant', type: 'image', image_url: imgUrl, message: '', created_at: new Date().toISOString() };
      setMessages(prev => [...prev, optimistic]);
      const pushRes = await apiClient.post('/api/v1/bot-push', {
        user_id: selectedContact.user_id, message: '',
        channel_key: selectedChannel.key, type: 'image', image_url: imgUrl,
      });
      if (pushRes.data?.code) msgApi.success('圖片已送出');
      else msgApi.warning(`LINE API 回應: ${pushRes.data?.line_status}`);
    } catch { msgApi.error('圖片發送失敗'); }
    setImageUploading(false);
    if (e.target) e.target.value = '';
  };

  const filtered = contacts.filter((c: any) => {
    const uid = c.user_id || '';
    const lastMsg = c.last_message || '';
    return !search || uid.includes(search) || lastMsg.includes(search);
  });

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 180px)', gap: 0, border: '1px solid #e8e8e8', borderRadius: 8, overflow: 'hidden' }}>
      {/* Left: contact list */}
      <div style={{ width: 280, borderRight: '1px solid #e8e8e8', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '8px 10px', borderBottom: '1px solid #e8e8e8' }}>
          <Input.Search size="small" placeholder="搜尋..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#888' }}>載入中...</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#888' }}>尚無對話</div>
          ) : (
            filtered.map(c => (
              <div key={c.user_id} onClick={() => selectContact(c)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', cursor: 'pointer',
                  background: selectedId === c.user_id ? '#e6f4ff' : 'transparent',
                  borderBottom: '1px solid #f5f5f5',
                }}>
                <Avatar size={32} icon={<UserOutlined />} style={{ background: '#1677ff', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Text style={{ fontSize: 13, fontWeight: selectedId === c.user_id ? 600 : 400 }}>
                    {c.display_name || c.user_id?.slice(-8) || '未知'}
                  </Text>
                  <div style={{ fontSize: 11, color: '#999', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.last_message || ''}
                  </div>
                </div>
                <Button type="text" size="small" icon={<DeleteOutlined />} onClick={e => handleDeleteChat(e, c.user_id)}
                  style={{ color: '#ccc', flexShrink: 0 }} />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right: chat room */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {!selectedId ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ccc', fontSize: 14 }}>
            請選擇聯絡人開始聊天
          </div>
        ) : (
          <>
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #e8e8e8', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{selectedContact?.display_name || selectedId?.slice(-8)}</span>
              {selectedContact?.channels?.length > 1 && (
                <Select size="small" value={selectedChannel?.key}
                  onChange={val => setSelectedChannel(selectedContact.channels.find((ch: any) => ch.key === val))}
                  options={selectedContact.channels.map((ch: any) => ({ label: ch.name || ch.key, value: ch.key }))}
                  style={{ width: 120 }} />
              )}
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', background: '#f5f5f5' }}>
              {msgLoading ? (
                <div style={{ padding: 20, textAlign: 'center', color: '#888' }}>載入中...</div>
              ) : messages.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: '#999', fontSize: 12 }}>尚無對話記錄</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {messages.map((msg: any, i: number) => {
                    const fromLineUser = msg.role === 'user';
                    return (
                      <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: fromLineUser ? 'flex-start' : 'flex-end' }}>
                        <div style={{
                          maxWidth: '75%', padding: msg.type === 'image' ? '4px' : '6px 10px', borderRadius: 10,
                          background: fromLineUser ? '#fff' : msg.type === 'image' ? 'transparent' : '#1677ff',
                          color: fromLineUser ? '#222' : '#fff',
                          fontSize: 13,
                          boxShadow: msg.type === 'image' ? 'none' : '0 1px 2px rgba(0,0,0,0.06)',
                        }}>
                          {msg.type === 'image' && msg.image_url ? (
                            <img src={msg.image_url} alt="圖片" style={{ maxWidth: 240, maxHeight: 240, borderRadius: 8, display: 'block' }} />
                          ) : null}
                          {msg.message ? <div>{msg.message}</div> : null}
                          <div style={{ fontSize: 10, opacity: 0.5, marginTop: 2, textAlign: 'right' }}>
                            {msg.created_at?.slice(11, 16) || ''}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={msgsEndRef} />
                </div>
              )}
            </div>
            <div style={{ padding: '8px 12px', borderTop: '1px solid #e8e8e8', display: 'flex', gap: 6, alignItems: 'center', background: '#fff' }}>
              <input type="file" accept="image/*" ref={fileInputRef}
                onChange={handleImageSelect} style={{ display: 'none' }} />
              <Button icon={<PictureOutlined />} loading={imageUploading}
                onClick={() => fileInputRef.current?.click()} size="small" />
              <Input.TextArea rows={1} size="small" placeholder="輸入訊息..." value={inputText}
                onChange={e => setInputText(e.target.value)} onKeyDown={handleKeyDown}
                style={{ flex: 1, borderRadius: 6, resize: 'none' }} />
              <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend} size="small" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function GreetingScheduler() {
  const { message: msg } = App.useApp();
  const [schedules, setSchedules] = useState<MessageSchedule[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [targetModalOpen, setTargetModalOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [targetType, setTargetType] = useState<'all' | 'select' | 'vip' | 'region'>('all');
  const [sendMessageType, setSendMessageType] = useState<'greeting' | 'promotion' | 'announcement'>('greeting');
  const [contentMode, setContentMode] = useState<'template' | 'ai'>('template');
  const [greetingTemplate, setGreetingTemplate] = useState('{{customer_name}}您好！祝您有美好的一天。');
  const [aiPrompt, setAiPrompt] = useState('');
  const [scheduleContentMode, setScheduleContentMode] = useState<'template' | 'ai'>('template');
  const [form] = Form.useForm();

  const loadSchedules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await crmApi.listSchedules();
      setSchedules((res as any).data || []);
    } catch { setSchedules([]); }
    setLoading(false);
  }, []);

  useEffect(() => { loadSchedules(); }, [loadSchedules]);

  const MESSAGE_TYPE_LABELS: Record<string, string> = {
    greeting: '問候', promotion: '促銷', announcement: '公告',
  };
  const MESSAGE_TYPE_COLORS: Record<string, string> = {
    greeting: 'green', promotion: 'volcano', announcement: 'purple',
  };

  const handleSendGreeting = () => {
    setTargetType('all');
    setSendMessageType('greeting');
    setContentMode('template');
    setGreetingTemplate('{{customer_name}}您好！祝您有美好的一天。');
    setAiPrompt('');
    setTargetModalOpen(true);
  };

  const handleConfirmTarget = async () => {
    setTargetModalOpen(false);
    try {
      const payload: CreateSchedulePayload = {
        business_user_key: '',
        name: `立即發送 - ${MESSAGE_TYPE_LABELS[sendMessageType]}`,
        message_type: sendMessageType,
        template_text: contentMode === 'template' ? greetingTemplate : undefined,
        ai_prompt: contentMode === 'ai' ? aiPrompt : undefined,
        content_mode: contentMode,
        schedule_type: 'one_time',
        target_type: targetType,
        is_active: true,
      };
      await crmApi.createSchedule(payload);
      msg.success('訊息已排入發送佇列');
      loadSchedules();
    } catch { msg.error('發送失敗'); }
  };

  const handleCreateOrUpdate = async () => {
    const values = form.getFieldsValue();
    try {
      const payload: CreateSchedulePayload = {
        business_user_key: values.business_user_key || '',
        name: values.name,
        message_type: values.message_type || 'greeting',
        template_text: scheduleContentMode === 'template' ? values.template : undefined,
        ai_prompt: scheduleContentMode === 'ai' ? values.aiPrompt : undefined,
        content_mode: scheduleContentMode,
        schedule_time: values.schedule_time,
        schedule_type: values.schedule_type || 'recurring',
        target_type: values.target_type || 'all',
        is_active: true,
      };
      if (editingKey) {
        await crmApi.updateSchedule(editingKey, payload as UpdateSchedulePayload);
        msg.success('排程已更新');
      } else {
        await crmApi.createSchedule(payload);
        msg.success('排程已建立');
      }
      setModalOpen(false);
      setEditingKey(null);
      form.resetFields();
      loadSchedules();
    } catch { msg.error('操作失敗'); }
  };

  const handleToggleActive = async (record: MessageSchedule) => {
    try {
      await crmApi.updateSchedule(record._key, { is_active: !record.is_active });
      loadSchedules();
    } catch { msg.error('更新失敗'); }
  };

  const handleDelete = async (key: string) => {
    try {
      await crmApi.deleteSchedule(key);
      msg.success('已刪除');
      loadSchedules();
    } catch { msg.error('刪除失敗'); }
  };

  const openEditModal = (record: MessageSchedule) => {
    setEditingKey(record._key);
    setScheduleContentMode(record.content_mode || 'template');
    form.setFieldsValue({
      name: record.name,
      message_type: record.message_type,
      schedule_type: record.schedule_type,
      schedule_time: record.schedule_time,
      target_type: record.target_type,
      template: record.template_text,
      aiPrompt: record.ai_prompt,
    });
    setModalOpen(true);
  };

  const columns = [
    { title: '', dataIndex: 'is_active', key: 'active', width: 40,
      render: (v: boolean, r: MessageSchedule) => <Switch size="small" checked={v} onChange={() => handleToggleActive(r)} /> },
    { title: '類型', dataIndex: 'message_type', key: 'message_type', width: 60,
      render: (v: string) => <Tag color={MESSAGE_TYPE_COLORS[v]} style={{ fontSize: 11 }}>{MESSAGE_TYPE_LABELS[v] || v}</Tag> },
    { title: '任務名稱', dataIndex: 'name', key: 'name', width: 130,
      render: (v: string) => <Text style={{ fontSize: 12 }}>{v || '(未命名)'}</Text> },
    { title: '排程', dataIndex: 'schedule_time', key: 'schedule_time', width: 120 },
    { title: '對象', dataIndex: 'target_type', key: 'target_type', width: 80,
      render: (v: string) => {
        const m: Record<string, string> = { all: '全部', vip: 'VIP', region: '區域', select: '指定' };
        return <Text style={{ fontSize: 12 }}>{m[v] || v}</Text>;
      }},
    { title: '類型', dataIndex: 'schedule_type', key: 'schedule_type', width: 56,
      render: (v: string) => <Tag>{v === 'recurring' ? '定期' : '單次'}</Tag> },
    { title: '已發', dataIndex: 'sent_count', key: 'sent_count', width: 48,
      render: (v: number) => <Text style={{ fontSize: 12 }}>{v ?? 0}</Text> },
    { title: '操作', key: 'action', width: 80,
      render: (_: any, r: MessageSchedule) => (
        <span>
          <Button size="small" type="link" onClick={() => openEditModal(r)}>編輯</Button>
          <Button size="small" type="link" danger onClick={() => handleDelete(r._key)}>刪除</Button>
        </span>
      )},
  ];

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
        <Button size="small" icon={<PlusOutlined />} onClick={() => {
          setEditingKey(null); form.resetFields(); setModalOpen(true);
        }}>新增排程</Button>
        <Button size="small" type="primary" icon={<SendOutlined />} onClick={handleSendGreeting}>立即發送訊息</Button>
      </div>

      <Table dataSource={schedules} columns={columns} rowKey="_key" pagination={false} size="middle" loading={loading} />

      {/* 立即發送 Modal */}
      <Modal title="選擇發送對象與內容" open={targetModalOpen}
        onCancel={() => setTargetModalOpen(false)}
        onOk={handleConfirmTarget} okText="確認發送" width={520}>
        <div style={{ marginBottom: 12 }}>
          <Text strong style={{ fontSize: 13 }}>📋 訊息類型</Text>
          <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
            <Tag color={sendMessageType === 'greeting' ? 'green' : 'default'} style={{ cursor: 'pointer' }}
              onClick={() => setSendMessageType('greeting')}>💬 問候</Tag>
            <Tag color={sendMessageType === 'promotion' ? 'volcano' : 'default'} style={{ cursor: 'pointer' }}
              onClick={() => setSendMessageType('promotion')}>🏷️ 促銷</Tag>
            <Tag color={sendMessageType === 'announcement' ? 'purple' : 'default'} style={{ cursor: 'pointer' }}
              onClick={() => setSendMessageType('announcement')}>📢 公告</Tag>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {([
            { key: 'all', label: '👥 全部聯絡人', desc: '對所有已加好友的客戶發送' },
            { key: 'vip', label: '⭐ VIP 客戶', desc: '僅發送給 VIP 等級客戶' },
            { key: 'region', label: '📍 指定區域', desc: '按客戶所在地區篩選' },
            { key: 'select', label: '📋 手動選擇', desc: '從聯絡人清單中勾選' },
          ] as const).map(item => (
            <div key={item.key} onClick={() => setTargetType(item.key)} style={{
              padding: '10px 14px', borderRadius: 8, border: '1px solid', cursor: 'pointer',
              borderColor: targetType === item.key ? '#1677ff' : '#d9d9d9',
              background: targetType === item.key ? '#e6f4ff' : '#fff',
            }}>
              <Text strong>{item.label}</Text>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{item.desc}</div>
            </div>
          ))}
        </div>

        <Divider style={{ margin: '12px 0' }} />
        <Text strong style={{ fontSize: 13 }}>💬 訊息內容</Text>
        <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
          <Tag color={contentMode === 'template' ? 'blue' : 'default'} style={{ cursor: 'pointer' }}
            onClick={() => setContentMode('template')}>📝 固定模板</Tag>
          <Tag color={contentMode === 'ai' ? 'blue' : 'default'} style={{ cursor: 'pointer' }}
            onClick={() => setContentMode('ai')}>🤖 AI 生成</Tag>
        </div>
        <div style={{ marginTop: 8 }}>
          {contentMode === 'template' ? (
            <Input.TextArea rows={2} value={greetingTemplate}
              onChange={e => setGreetingTemplate(e.target.value)}
              placeholder="{{customer_name}}您好！祝您有美好的一天。" />
          ) : (
            <Input.TextArea rows={2} value={aiPrompt}
              onChange={e => setAiPrompt(e.target.value)}
              placeholder="例如：用輕鬆活潑的語氣，提醒客戶定期保養" />
          )}
        </div>
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
          {contentMode === 'template'
            ? '支援 {{customer_name}}、{{company}} 等變數'
            : 'AI 會根據每個客戶資料個別生成'}
        </Text>
      </Modal>

      {/* 新增/編輯排程 Modal */}
      <Modal title={editingKey ? '編輯排程' : '新增排程'} open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingKey(null); }}
        onOk={handleCreateOrUpdate} width={520}>
        <Form form={form} layout="vertical" size="small"
          initialValues={{ message_type: 'greeting', schedule_type: 'recurring', target_type: 'all' }}>
          <Form.Item label="訊息類型" name="message_type">
            <Select options={[
              { label: '💬 問候', value: 'greeting' },
              { label: '🏷️ 促銷', value: 'promotion' },
              { label: '📢 公告', value: 'announcement' },
            ]} />
          </Form.Item>
          <Form.Item label="任務名稱" name="name" rules={[{ required: true }]}>
            <Input placeholder="早安問候 / 端午促銷 / 系統維護公告" />
          </Form.Item>
          <Form.Item label="排程類型" name="schedule_type">
            <Select options={[
              { label: '定期（如每天）', value: 'recurring' },
              { label: '單次（如節日）', value: 'one_time' },
            ]} />
          </Form.Item>
          <Form.Item label="排程時間" name="schedule_time" rules={[{ required: true }]}>
            <Input placeholder="每天 08:00" />
          </Form.Item>

          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>🎯 發送對象</div>
          <Form.Item name="target_type" noStyle>
            <Radio.Group style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
              <Radio value="all">👥 全部聯絡人</Radio>
              <Radio value="vip">⭐ VIP 客戶</Radio>
              <Radio value="region">📍 指定區域</Radio>
              <Radio value="select">📋 手動選擇</Radio>
            </Radio.Group>
          </Form.Item>

          <Divider style={{ margin: '4px 0' }} />
          <Text strong style={{ fontSize: 13 }}>💬 訊息內容</Text>
          <div style={{ marginTop: 6, marginBottom: 8, display: 'flex', gap: 8 }}>
            <Tag color={scheduleContentMode === 'template' ? 'blue' : 'default'} style={{ cursor: 'pointer' }}
              onClick={() => setScheduleContentMode('template')}>📝 固定模板</Tag>
            <Tag color={scheduleContentMode === 'ai' ? 'blue' : 'default'} style={{ cursor: 'pointer' }}
              onClick={() => setScheduleContentMode('ai')}>🤖 AI 生成</Tag>
          </div>
          {scheduleContentMode === 'template' ? (
            <Form.Item name="template">
              <Input.TextArea rows={3} placeholder="{{customer_name}}您好！祝您有美好的一天。" />
            </Form.Item>
          ) : (
            <Form.Item name="aiPrompt">
              <Input.TextArea rows={3} placeholder="例如：用溫暖關懷的語氣，提醒客戶定期保養，並附上最近的優惠活動" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}
function ContactListView() {
  const { message: msg } = App.useApp();
  const [search, setSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [syncing, setSyncing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const pageSize = 50;

  const loadContacts = useCallback(async () => {
    try {
      const res = await crmApi.listContacts({ page, page_size: pageSize, q: search || undefined }) as any;
      const list = res?.data?.data;
      setContacts(Array.isArray(list) ? list : []);
    } catch {
      setContacts([]);
    }
  }, [page, search]);

  useEffect(() => { loadContacts(); }, [loadContacts]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await apiClient.post('/api/v1/crm/contacts/sync-from-line') as any;
      const n = res?.data?.data?.created || 0;
      if (n > 0) {
        msg.success(`已新增 ${n} 位聯絡人`);
        loadContacts();
      } else {
        msg.info('沒有遺漏的聯絡人');
      }
    } catch { msg.error('同步失敗'); }
    setSyncing(false);
  };

  const startEdit = () => {
    setEditForm({
      name_cn: selected.name_cn || '',
      name_en: selected.name_en || '',
      title: selected.title || '',
      gender: selected.gender || '',
      birthday: selected.birthday || '',
      notes: selected.notes || '',
      is_self: selected.is_self || false,
    });
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditForm({});
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      // 若設為本人，檢查是否有重複（僅警告，不阻止）
      if (editForm.is_self) {
        const dup = contacts.filter(c => c._key !== selected._key && c.is_self && c.owner_key === selected.owner_key);
        if (dup.length > 0) {
          msg.warning(`⚠️ ${dup.map(c => c.name_cn || c.name_en).join('、')} 也已標記為「本人」`);
        }
      }
      await crmApi.updateContact(selected._key, editForm);
      msg.success('已儲存');
      setEditing(false);
      setEditForm({});
      // 更新 selected 與 contacts
      const updated = { ...selected, ...editForm };
      setSelected(updated);
      setContacts(prev => prev.map(c => c._key === updated._key ? updated : c));
    } catch { msg.error('儲存失敗'); }
    setSaving(false);
  };

  const handleDeleteContact = (c: any) => {
    Modal.confirm({
      title: '刪除聯絡人',
      content: `確定刪除 ${c.name_cn || c.name_en || '此聯絡人'}？此操作不可復原。`,
      onOk: async () => {
        try {
          await crmApi.deleteContact(c._key);
          msg.success('已刪除');
          if (selected?._key === c._key) setSelected(null);
          setContacts(prev => prev.filter(x => x._key !== c._key));
        } catch { msg.error('刪除失敗'); }
      },
    });
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 180px)', gap: 0, border: '1px solid #e8e8e8', borderRadius: 8, overflow: 'hidden' }}>
      {/* Left: contact list */}
      <div style={{ width: 300, borderRight: '1px solid #e8e8e8', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '8px 10px', borderBottom: '1px solid #e8e8e8', display: 'flex', gap: 6 }}>
          <Input.Search size="small" placeholder="搜尋姓名或公司..." value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }} />
          <Button size="small" icon={<ReloadOutlined />} loading={syncing} onClick={handleSync} />
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {contacts.map((c: any) => (
            <div key={c._key} onClick={() => setSelected(c)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', cursor: 'pointer',
                background: selected?._key === c._key ? '#e6f4ff' : 'transparent',
                borderBottom: '1px solid #f5f5f5',
              }}>
              <Avatar size={36} icon={<UserOutlined />} style={{ background: '#1677ff', flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Text style={{ fontSize: 13, fontWeight: selected?._key === c._key ? 600 : 400 }}>
                  {c.name_cn || c.name_en || '未知'}
                </Text>
                <div style={{ fontSize: 11, color: '#999', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.titles?.[0]?.title || c.organizations?.[0]?.name || c.source || ''}
                </div>
              </div>
              <Button type="text" size="small" icon={<DeleteOutlined />}
                onClick={e => { e.stopPropagation(); handleDeleteContact(c); }}
                style={{ color: '#ccc', flexShrink: 0 }} />
            </div>
          ))}
        </div>
      </div>

      {/* Right: contact detail */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {!selected ? (
          <div style={{ textAlign: 'center', color: '#ccc', paddingTop: 80 }}>請選擇聯絡人</div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <Avatar size={48} icon={<UserOutlined />} style={{ background: '#1677ff', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                {editing
                  ? <Input size="small" value={editForm.name_cn} onChange={e => setEditForm({...editForm, name_cn: e.target.value})}
                      style={{ maxWidth: 200, marginBottom: 4 }} />
                  : <Text strong style={{ fontSize: 16 }}>
                      {selected.name_cn || selected.name_en || '未知'}
                      {selected.is_self && <Tag color="blue" style={{ marginLeft: 6, fontSize: 10 }}>本人</Tag>}
                    </Text>
                }
                {editing
                  ? <Input size="small" value={editForm.title} onChange={e => setEditForm({...editForm, title: e.target.value})}
                      placeholder="稱謂" style={{ maxWidth: 150 }} />
                  : <div style={{ fontSize: 12, color: selected.title ? '#888' : '#ccc' }}>{selected.title || '(無稱謂)'}</div>
                }
              </div>
              {editing ? (
                <Space>
                  <Button size="small" onClick={cancelEdit}>取消</Button>
                  <Button size="small" type="primary" loading={saving} onClick={handleSave}>保存</Button>
                </Space>
              ) : (
                <Button size="small" icon={<EditOutlined />} onClick={startEdit}>編輯</Button>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', fontSize: 13, marginBottom: 16 }}>
              <EditField label="姓名(英)" value={editForm.name_en} editing={editing}
                onChange={v => setEditForm({...editForm, name_en: v})} />
              <EditField label="性別" value={editing ? editForm.gender : selected.gender} editing={editing}
                onChange={v => setEditForm({...editForm, gender: v})}
                options={[{value:'male',label:'男'},{value:'female',label:'女'}]} />
              <EditField label="生日" value={editing ? editForm.birthday : selected.birthday} editing={editing}
                onChange={v => setEditForm({...editForm, birthday: v})} />
              {editing && (
                <div style={{ display: 'flex', gap: 4, padding: '2px 0', alignItems: 'center' }}>
                  <span style={{ color: '#888', minWidth: 60, fontSize: 13 }}>本人</span>
                  <Switch size="small" checked={editForm.is_self} onChange={v => setEditForm({...editForm, is_self: v})} />
                  <span style={{ fontSize: 12, color: '#999' }}>{editForm.is_self ? '這是我的聯絡人' : ''}</span>
                </div>
              )}
              <Field label="來源" value={selected.source} />
              <Field label="LINE ID" value={selected.line_user_id} />
              <Field label="LINE 狀態" value={selected.line_status} />
              <Field label="建立者" value={selected.created_by} />
              <Field label="建立時間" value={selected.created_at?.slice(0, 10)} />
            </div>

            {/* 多筆電話 */}
            <SectionTitle title="電話" />
            {selected.phones && Array.isArray(selected.phones) && selected.phones.length > 0
              ? selected.phones.map((p: any, i: number) => (
                  <FieldValue key={i} icon="📞" value={`${p.number || p}${p.type ? ` (${p.type})` : ''}`} />
                ))
              : <EmptyValue text="（尚無電話）" />}

            {/* Email */}
            <SectionTitle title="Email" />
            {selected.emails && Array.isArray(selected.emails) && selected.emails.length > 0
              ? selected.emails.map((e: string, i: number) => <FieldValue key={i} icon="✉️" value={e} />)
              : <EmptyValue text="（尚無 Email）" />}

            {/* 社群平台 */}
            <SectionTitle title="社群平台" />
            {selected.social_accounts && Array.isArray(selected.social_accounts) && selected.social_accounts.length > 0
              ? selected.social_accounts.map((s: any, i: number) => (
                  <FieldValue key={i} icon="🔗" value={`${s.platform}: ${s.account_id}`} />
                ))
              : <EmptyValue text="（尚無社群帳號）" />}

            {/* 公司/組織 */}
            <SectionTitle title="公司/組織" />
            {selected.organizations && Array.isArray(selected.organizations) && selected.organizations.length > 0
              ? selected.organizations.map((o: any, i: number) => (
                  <FieldValue key={i} icon="🏢" value={`${o.name}${o.title ? ` - ${o.title}` : ''}`} />
                ))
              : <EmptyValue text="（尚無公司資料）" />}

            {/* 家人 */}
            <SectionTitle title="家人" />
            {selected.family_members && Array.isArray(selected.family_members) && selected.family_members.length > 0
              ? selected.family_members.map((fm: any, i: number) => (
                  <FieldValue key={i} icon="👨‍👩‍👧" value={`${fm.name}${fm.relation ? ` (${fm.relation})` : ''}${fm.birthday ? ` 🎂${fm.birthday}` : ''}`} />
                ))
              : <EmptyValue text="（尚無家人資料）" />}

            {/* 備註 */}
            <SectionTitle title="備註" />
            {editing ? (
              <Input.TextArea rows={2} size="small" value={editForm.notes}
                onChange={e => setEditForm({...editForm, notes: e.target.value})}
                style={{ fontSize: 13, marginBottom: 12 }} placeholder="（無備註）" />
            ) : (
              <div style={{ fontSize: 13, color: selected.notes ? '#333' : '#bbb', marginBottom: 12 }}>
                {selected.notes || '（無備註）'}
              </div>
            )}

            {/* 名片 */}
            <SectionTitle title={`名片 (${(selected.card_images || []).length} 張)`} />
            {selected.card_images && Array.isArray(selected.card_images) && selected.card_images.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6, marginBottom: 12 }}>
                {selected.card_images.map((url: string, i: number) => (
                  <img key={i} src={url} alt={`名片${i+1}`}
                    style={{ width: 180, height: 120, objectFit: 'contain', border: '1px solid #e8e8e8', borderRadius: 6, cursor: 'pointer' }}
                    onClick={() => window.open(url, '_blank')} />
                ))}
              </div>
            ) : (
              <EmptyValue text="（尚无名片）" />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div style={{ display: 'flex', gap: 4, padding: '2px 0' }}>
      <span style={{ color: '#888', minWidth: 60 }}>{label}</span>
      <span style={{ color: value ? '#333' : '#ccc' }}>{value || '—'}</span>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <div style={{ fontWeight: 600, fontSize: 12, color: '#666', marginTop: 8, marginBottom: 4, borderBottom: '1px solid #eee', paddingBottom: 2 }}>{title}</div>;
}

function FieldValue({ icon, value }: { icon: string; value: string }) {
  return <div style={{ fontSize: 13, marginBottom: 2 }}>{icon} {value}</div>;
}

function EmptyValue({ text }: { text: string }) {
  return <div style={{ fontSize: 12, color: '#ccc', marginBottom: 4, fontStyle: 'italic' }}>{text}</div>;
}

function EditField({ label, value, editing, onChange, options }: {
  label: string; value?: string; editing: boolean;
  onChange: (v: string) => void;
  options?: { value: string; label: string }[];
}) {
  return (
    <div style={{ display: 'flex', gap: 4, padding: '2px 0', alignItems: 'center' }}>
      <span style={{ color: '#888', minWidth: 60, fontSize: 13 }}>{label}</span>
      {editing ? (
        options ? (
          <Select size="small" value={value || ''} onChange={onChange}
            style={{ minWidth: 100 }}
            options={[{ value: '', label: '—' }, ...options]} />
        ) : (
          <Input size="small" value={value || ''} onChange={e => onChange(e.target.value)}
            style={{ maxWidth: 160 }} placeholder="—" />
        )
      ) : (
        <span style={{ color: value ? '#333' : '#ccc', fontSize: 13 }}>{value || '—'}</span>
      )}
    </div>
  );
}

function PendingContacts() {
  const columns = [
    { title: 'LINE ID', dataIndex: 'lineId', key: 'lineId', width: 100, render: (v: string) => <Text code style={{ fontSize: 11 }}>{v}</Text> },
    { title: '姓名', dataIndex: 'name', key: 'name', width: 80 },
    { title: '電話', dataIndex: 'phone', key: 'phone', width: 120 },
    { title: '公司', dataIndex: 'company', key: 'company', width: 120 },
    { title: '狀態', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'confirmed' ? 'green' : 'orange'}>{v === 'confirmed' ? '已建檔' : '待確認'}</Tag> },
    { title: '操作', key: 'action', width: 100,
      render: (_: any, r: any) => r.status === 'pending'
        ? <><Button size="small" type="link">確認</Button><Button size="small" type="link" danger>忽略</Button></>
        : <Text type="secondary" style={{ fontSize: 11 }}>已建檔</Text> },
  ];
  return <Table dataSource={MOCK_PENDING} columns={columns} rowKey="key" pagination={false} size="middle" />;
}

function VisitBoard() {
  const columns = [
    { title: '客戶', dataIndex: 'customer', key: 'customer', width: 100 },
    { title: '日期', dataIndex: 'date', key: 'date', width: 100 },
    { title: '時間', dataIndex: 'time', key: 'time', width: 80 },
    { title: '地點', dataIndex: 'location', key: 'location', width: 180 },
    { title: '狀態', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => {
        const m: Record<string, {color: string; label: string}> = {
          planned: { color: 'processing', label: '待拜訪' },
          done: { color: 'success', label: '已拜訪' },
          cancelled: { color: 'default', label: '已取消' },
        };
        return <Tag color={m[v]?.color}>{m[v]?.label || v}</Tag>;
      }},
  ];
  return (
    <div>
      <div style={{ marginBottom: 12 }}><Button size="small" icon={<PlusOutlined />}>新增行程</Button></div>
      <Table dataSource={MOCK_VISITS} columns={columns} rowKey="key" pagination={false} size="middle" />
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────── */

const TABS = [
  { key: 'conversations', label: '聊天室', icon: <MessageOutlined />, component: <ConversationView /> },
  { key: 'greeting', label: '信息發送排程', icon: <SendOutlined />, component: <GreetingScheduler /> },
  { key: 'timeline', label: '我的聯絡人', icon: <UserOutlined />, component: <ContactListView /> },
  { key: 'contacts', label: '名片待確認', icon: <UserOutlined />, component: <PendingContacts /> },
  { key: 'visits', label: '行程看板', icon: <ClockCircleOutlined />, component: <VisitBoard /> },
];

export default function LineAssistantPage() {
  const contentTokens = useContentTokens();
  const [activeTab, setActiveTab] = useState(TABS[0].key);

  useEffect(() => {
    pageContextManager.report({ page: 'eea-crm/line-assistant', pageName: '我的 LINE 助手' });
  }, []);

  const filteredTabs = TABS;  // channels moved to standalone ChannelAdminPage

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
        <Text strong style={{ fontSize: 16 }}>📱 我的 LINE 助手</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>管理業務頻道、對話與客戶互動</Text>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab}
        items={filteredTabs.map(t => ({
          key: t.key,
          label: <span>{t.icon} {t.label}</span>,
          children: t.component,
        }))}
      />
    </div>
  );
}
