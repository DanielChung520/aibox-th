/**
 * @file        LineAssistantPage.tsx
 * @description LINE 助手管理頁面 — 業務員專用的 LINE Bot 後台
 * @lastUpdate  2026-06-14
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import { Tabs, Table, Button, Tag, Modal, Form, Input, Select, Switch,
         Typography, Avatar, Drawer, App, Radio, Divider } from 'antd';
import {
  MessageOutlined, ClockCircleOutlined, UserOutlined,
  SendOutlined, PlusOutlined, ReloadOutlined,
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
  const [search, setSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [limit, setLimit] = useState(20);

  const loadContacts = useCallback(() => {
    setLoading(true);
    apiClient.get('/api/v1/bot-contacts')
      .then((res: any) => setContacts(res.data?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadContacts(); }, [loadContacts]);

  const loadMessages = (userId: string) => {
    setSelected(userId);
    setMsgLoading(true);
    apiClient.get(`/api/v1/bot-messages/${userId}`)
      .then((res: any) => setMessages(res.data?.data || []))
      .catch(() => setMessages([]))
      .finally(() => setMsgLoading(false));
  };

  const filtered = contacts.filter((c: any) => {
    const uid = c.user_id || '';
    const lastMsg = c.last_message || '';
    return !search || uid.includes(search) || lastMsg.includes(search);
  }).slice(0, limit);

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
        <Input.Search
          placeholder="搜尋 LINE ID 或對話內容..."
          style={{ maxWidth: 320 }} size="small" allowClear
          value={search} onChange={e => setSearch(e.target.value)}
        />
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={loadContacts} />
        <Text type="secondary" style={{ fontSize: 11, alignSelf: 'center' }}>
          {loading ? '載入中...' : `${filtered.length} 位聯絡人`}
        </Text>
      </div>

      {filtered.length === 0 ? (
        <Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 40 }}>
          {loading ? '載入中...' : '尚無對話記錄'}
        </Text>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {filtered.map((c: any) => (
            <div key={c.user_id}
              onClick={() => loadMessages(c.user_id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
                borderRadius: 8, cursor: 'pointer',
                background: selected === c.user_id ? '#e6f4ff' : 'transparent',
              }}>
              <Avatar size={36} icon={<UserOutlined />} style={{ background: '#1677ff' }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Text strong style={{ fontSize: 13 }}>{c.display_name || c.user_id?.slice(-8) || '未知'}</Text>
                <div style={{ fontSize: 12, color: '#888', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.last_message || '(無訊息)'}
                </div>
              </div>
              <Text type="secondary" style={{ fontSize: 11 }}>{c.message_count || 0} 則</Text>
            </div>
          ))}
        </div>
      )}

      {limit < contacts.length && (
        <Button type="link" size="small" onClick={() => setLimit(limit + 20)} style={{ marginTop: 8 }}>
          載入更多...
        </Button>
      )}

      <Drawer title={`💬 對話記錄`}
        open={!!selected} onClose={() => setSelected(null)} width={560}
        styles={{ body: { padding: 0 } }}>
        {msgLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#888' }}>載入中...</div>
        ) : messages.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#888', fontSize: 13 }}>尚無對話記錄</div>
        ) : (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {messages.map((msg: any, i: number) => {
              const isBot = msg.role !== 'user';
              return (
              <div key={i} style={{
                display: 'flex', flexDirection: 'column',
                alignItems: isBot ? 'flex-start' : 'flex-end',
                marginBottom: 8,
              }}>
                <div style={{
                  fontSize: 11, color: '#999', marginBottom: 2,
                  paddingLeft: isBot ? 4 : 0, paddingRight: isBot ? 0 : 4,
                }}>
                  {isBot ? '🤖 i舒雅' : `👤 ${selected?.slice(-8) || '用戶'}`}
                </div>
                <div style={{
                  maxWidth: '75%', padding: '8px 14px', borderRadius: 12,
                  background: isBot ? '#e8e8e8' : '#1677ff',
                  color: isBot ? '#222' : '#fff',
                  fontSize: 13, lineHeight: 1.6,
                  border: isBot ? '1px solid #d9d9d9' : 'none',
                }}>
                  <div>{msg.message}</div>
                  <div style={{ fontSize: 10, opacity: 0.6, marginTop: 4, textAlign: 'right' }}>
                    {msg.created_at?.slice(0, 16) || ''}
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </Drawer>
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
function TimelineView() {
  const [search, setSearch] = useState('');
  const activities = [
    { name: '陳董', type: '訊息', summary: '追問貨物出貨進度', time: '10:30' },
    { name: '林經理', type: '問候', summary: '傳送早安問候', time: '昨天 08:00' },
    { name: '林經理', type: '訊息', summary: '回覆「早安，請問下週方便拜訪嗎？」', time: '昨天 08:01' },
    { name: '張老闆', type: '名片', summary: '傳送名片圖片（待確認建檔）', time: '06/12' },
    { name: '王老師', type: '訊息', summary: '詢問產品規格與價格', time: '06/11' },
    { name: '趙主任', type: '訊息', summary: '反應品質問題，情緒不滿', time: '06/08' },
    { name: '黃小姐', type: '訊息', summary: '預約維修時間', time: '06/07' },
    { name: '吳先生', type: '名片', summary: '傳送名片圖片', time: '06/05' },
    { name: '周副理', type: '群發', summary: '接收促銷活動訊息（已讀）', time: '06/03' },
    { name: '許課長', type: '訊息', summary: '更換聯絡電話', time: '06/01' },
  ];
  const filtered = activities.filter(a =>
    a.name.includes(search) || a.summary.includes(search),
  );

  const typeColors: Record<string, string> = {
    '訊息': 'cyan', '問候': 'green', '名片': 'orange', '群發': 'purple',
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Input.Search
          placeholder="搜尋聯絡人名稱或活動摘要..."
          style={{ maxWidth: 360 }} size="small" allowClear
          value={search} onChange={e => setSearch(e.target.value)}
        />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {filtered.map((a, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 12px', borderRadius: 8,
            background: i % 2 === 0 ? '#fafafa' : 'transparent',
          }}>
            <Avatar size={36} icon={<UserOutlined />} style={{ background: '#1677ff', flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Text strong style={{ fontSize: 13 }}>{a.name}</Text>
                <Tag color={typeColors[a.type] || 'default'} style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>{a.type}</Tag>
              </div>
              <div style={{ fontSize: 12, color: '#555', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a.summary}
              </div>
            </div>
            <Text type="secondary" style={{ fontSize: 11, flexShrink: 0 }}>{a.time}</Text>
          </div>
        ))}
      </div>
      <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginTop: 12, fontSize: 11 }}>
        僅顯示 LINE 相關活動（訊息、問候、名片、群發）
      </Text>
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
  { key: 'conversations', label: '對話查詢', icon: <MessageOutlined />, component: <ConversationView /> },
  { key: 'greeting', label: '信息發送排程', icon: <SendOutlined />, component: <GreetingScheduler /> },
  { key: 'timeline', label: '客戶 Timeline', icon: <ClockCircleOutlined />, component: <TimelineView /> },
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
