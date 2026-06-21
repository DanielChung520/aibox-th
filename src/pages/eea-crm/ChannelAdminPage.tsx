/**
 * @file        ChannelAdminPage.tsx
 * @description 通訊頻道管理 — 卡片式佈局，與 LINE Channel 設定一致
 * @lastUpdate  2026-06-20
 * @author      Sisyphus
 * @version     3.0.0
 */

import { useState, useEffect } from 'react';
import { Button, Tag, Modal, Form, Input, Select, Switch, Drawer, Table,
         Typography, Badge, App, Space, Divider, Card, Row, Col, Empty, Spin, Popconfirm } from 'antd';
import { PlusOutlined, ReloadOutlined, DeleteOutlined, CloseOutlined, CopyOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { channelsApi, userApi } from '../../services/api';
import { theme } from 'antd';
import type { Channel, User } from '../../services/api';
import AvatarPicker from '../../components/AvatarPicker';

const avatarModules = import.meta.glob<{ default: string }>('../../assets/avatar/*.png', { eager: true });
const avatarMap: Record<string, string> = {};
for (const [path, mod] of Object.entries(avatarModules)) {
  const name = path.split('/').pop()?.replace(/\.png$/i, '') || '';
  avatarMap[name] = (mod as { default: string }).default;
}

const { Text } = Typography;

const PLATFORM_META: Record<string, { label: string; color: string; icon: string }> = {
  line: { label: 'LINE', color: 'green', icon: '💬' },
  whatsapp: { label: 'WhatsApp', color: 'cyan', icon: '📱' },
  dingtalk: { label: 'DingTalk', color: 'blue', icon: '🔷' },
  wecom: { label: 'WeCom', color: 'orange', icon: '🔶' },
};

const PLATFORM_OPTIONS = [
  { label: '💬 LINE', value: 'line' },
  { label: '📱 WhatsApp', value: 'whatsapp' },
  { label: '🔷 DingTalk', value: 'dingtalk' },
  { label: '🔶 WeCom', value: 'wecom' },
];

const PLATFORM_CONFIG_FIELDS: Record<string, { key: string; label: string; type: string }[]> = {
  line: [
    { key: 'channel_id', label: 'Channel ID', type: 'string' },
    { key: 'channel_secret', label: 'Channel Secret', type: 'password' },
    { key: 'access_token', label: 'Access Token', type: 'password' },
  ],
  whatsapp: [
    { key: 'phone_number_id', label: 'Phone Number ID', type: 'string' },
    { key: 'access_token', label: 'Access Token', type: 'password' },
  ],
  dingtalk: [
    { key: 'app_key', label: 'App Key', type: 'string' },
    { key: 'app_secret', label: 'App Secret', type: 'password' },
  ],
  wecom: [
    { key: 'corp_id', label: 'Corp ID', type: 'string' },
    { key: 'agent_id', label: 'Agent ID', type: 'string' },
    { key: 'secret', label: 'Secret', type: 'password' },
    { key: 'token', label: 'Token', type: 'password' },
  ],
};

function ChannelCardComponent({ channel, onClick, onToggle }: { channel: Channel; onClick: (c: Channel) => void; onToggle: (key: string, checked: boolean) => void }) {
  const meta = PLATFORM_META[channel.platform] || { label: channel.platform, color: 'default', icon: '📡' };
  const displayName = channel.business_user_name || channel._key;
  const avatarSrc = channel.avatar ? avatarMap[channel.avatar] : null;
  const cid = channel.config?.channel_id || '';
  const contentTokens = useContentTokens();
  const { token } = theme.useToken();
  const [isHovered, setIsHovered] = useState(false);
  const hoverShadow = contentTokens.cardShadowHover || token.boxShadowSecondary;
  const normalShadow = contentTokens.cardShadow || token.boxShadow;
  const isDark = token.colorBgContainer.startsWith('#1') || token.colorBgContainer === '#141414';
  const headerBg = isDark ? 'rgb(36 103 24)' : 'rgb(181 236 183 / 20%)';
  const avatarBg = isDark ? 'rgba(255,255,255,0.06)' : (meta.color === 'green' ? '#00b90015' : '#f0f0f0');
  return (
    <Card
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onClick(channel)}
      style={{
        borderRadius: 10, aspectRatio: '16 / 9', overflow: 'hidden', cursor: 'pointer',
        transition: 'all 0.3s ease',
        transform: isHovered ? 'translateY(-4px)' : 'none',
        boxShadow: isHovered ? hoverShadow : normalShadow,
        border: isHovered ? `1px solid ${contentTokens.colorPrimary}80` : undefined,
      }}
      styles={{ body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' } }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px', flexShrink: 0,
        background: headerBg,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <img src={`/${channel.platform}-logo.png`} alt={meta.label}
            style={{ height: 18, width: 'auto' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          <Text strong style={{ fontSize: 16 }} ellipsis>{displayName}</Text>
        </div>
        <Switch size="small" checked={channel.status === 'active'}
          onChange={(c) => { onToggle(channel._key, c); }}
          onClick={(_, e) => e.stopPropagation()} />
      </div>
      <div style={{ display: 'flex', flex: 1, gap: 10, padding: '10px 14px', minHeight: 0 }}>
        <div style={{ flex: '0 0 40%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
          <div style={{
            width: 100, height: 100, borderRadius: 14,
            background: avatarSrc ? 'transparent' : avatarBg,
            display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
          }}>
            {avatarSrc ? (
              <img src={avatarSrc} alt={channel.avatar} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              <img src={`/${channel.platform}-logo.png`} alt={meta.label}
                style={{ height: 36, width: 'auto', opacity: 0.5 }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            )}
          </div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 4, minWidth: 0 }}>
          <div style={{ fontSize: 15, lineHeight: '24px' }}>{channel.role || '業務員'}</div>
          <div style={{ fontSize: 15, lineHeight: '24px' }}>
            {channel.business_user_name
              ? `${channel.business_user_name}（${channel.business_user_key}）`
              : channel.business_user_key || '—'}
          </div>
          {cid && <div style={{ fontSize: 15, lineHeight: '24px' }}><Text code style={{ fontSize: 14 }}>{cid}</Text></div>}
          <div style={{ fontSize: 15, lineHeight: '24px' }}>聯絡人 <Text strong>—</Text></div>
        </div>
      </div>
    </Card>
  );
}

function ChannelDetailDrawer({ channel, open, onClose, onSaved }: {
  channel: Channel | null; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { message: msg } = App.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    userApi.list().then(res => setUsers(res?.data?.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!open || !channel) return;
    form.setFieldsValue({
      platform: channel.platform,
      business_user_key: channel.business_user_key,
      business_user_name: channel.business_user_name,
      role: channel.role,
      linked_agent_key: channel.linked_agent_key,
      status: channel.status,
      avatar: channel.avatar,
      channel_id: channel.config?.channel_id || '',
      channel_secret: channel.config?.channel_secret || '',
      access_token: channel.config?.access_token || '',
    });
  }, [channel, open, form]);

  const userOptions = users.filter(u => u.status === 'enabled').map(u => ({
    label: `${u.name}（${u.username}）`, value: u._key,
  }));

  const handleSave = async () => {
    if (!channel) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        platform: values.platform,
        business_user_key: values.business_user_key,
        business_user_name: values.business_user_name || users.find(u => u._key === values.business_user_key)?.name || '',
        role: values.role,
        org_tags: values.org_tags || [],
        region_tags: values.region_tags || [],
        linked_agent_key: values.linked_agent_key,
        status: values.status,
        avatar: values.avatar || '',
        config: {
          channel_id: values.channel_id || '',
          channel_secret: values.channel_secret || '',
          access_token: values.access_token || '',
        },
      };
      await channelsApi.update(channel._key, payload);
      msg.success('頻道已更新');
      onSaved();
    } catch { msg.error('儲存失敗'); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!channel) return;
    try {
      await channelsApi.delete(channel._key);
      msg.success('頻道已刪除');
      onSaved();
      onClose();
    } catch { msg.error('刪除失敗'); }
  };

  const fields = PLATFORM_CONFIG_FIELDS[channel?.platform || 'line'] || [];

  return (
    <Drawer title={<span>{PLATFORM_META[channel?.platform || 'line']?.icon} 頻道設定</span>}
      placement="right" width={480} open={open} onClose={onClose} maskClosable
      extra={<Button type="text" icon={<CloseOutlined />} onClick={onClose} />}
      footer={
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Popconfirm title="確定刪除此頻道？" onConfirm={handleDelete} okText="刪除" cancelText="取消" okButtonProps={{ danger: true }}>
            <Button danger icon={<DeleteOutlined />}>刪除</Button>
          </Popconfirm>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" loading={saving} onClick={handleSave}>儲存</Button>
          </Space>
        </div>
      }>
      {channel && (
        <Form form={form} layout="vertical" size="small">
          <Form.Item label="Channel Key">
            <Input.Group compact style={{ display: 'flex' }}>
              <Input value={channel._key} readOnly style={{ flex: 1, fontSize: 12 }} />
              <Button icon={<CopyOutlined />} onClick={() => { navigator.clipboard.writeText(channel._key); msg.success('已複製'); }} />
            </Input.Group>
          </Form.Item>

          <Form.Item label="Webhook Path">
            <Input value={channel.webhook_path || `webhook/${channel._key}`} readOnly style={{ fontSize: 12 }} />
          </Form.Item>

          <Divider style={{ margin: '8px 0' }} />

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item label="平台" name="platform" style={{ flex: 1 }}>
              <Input readOnly />
            </Form.Item>
            <Form.Item label="角色" name="role" style={{ flex: 1 }}>
              <Select options={[{ label: '業務員', value: '業務員' }, { label: '業務主管', value: '業務主管' }]} />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item label="業務組織" name="org_tags" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後按 Enter" open={false}
                tokenSeparators={[',', '，', '|', '/']} />
            </Form.Item>
            <Form.Item label="負責區域" name="region_tags" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後按 Enter" open={false}
                tokenSeparators={[',', '，', '|', '/']} />
            </Form.Item>
          </div>
          <Form.Item label="綁定使用者" name="business_user_key">
            <Select options={userOptions} placeholder="選擇使用者" allowClear />
          </Form.Item>
          <Form.Item label="頻道別名" name="business_user_name">
            <Input placeholder="留空則使用帳號名稱" />
          </Form.Item>
          <Form.Item label="連結 Agent" name="linked_agent_key">
            <Input placeholder="welfare_secretary" />
          </Form.Item>
          <Form.Item label="頭像" name="avatar">
            <AvatarPicker value={form.getFieldValue('avatar')} onChange={(val) => form.setFieldValue('avatar', val)} />
          </Form.Item>
          <Form.Item label="狀態" name="status">
            <Select options={[{ label: '啟用', value: 'active' }, { label: '停用', value: 'inactive' }]} />
          </Form.Item>

          <Divider style={{ margin: '8px 0' }} />
          <Text strong style={{ fontSize: 13 }}>{PLATFORM_META[channel.platform]?.icon} {PLATFORM_META[channel.platform]?.label} 設定</Text>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px', marginTop: 8 }}>
            {fields.map(f => (
              <Form.Item key={f.key} name={f.key} label={f.label}>
                {f.type === 'password' ? <Input.Password /> : <Input />}
              </Form.Item>
            ))}
          </div>
        </Form>
      )}
    </Drawer>
  );
}


export default function ChannelAdminPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<Channel | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    userApi.list().then(res => setUsers(res?.data?.data || [])).catch(() => {});
  }, []);

  const userOptions = users.filter(u => u.status === 'enabled').map(u => ({
    label: `${u.name}（${u.username}）`, value: u._key,
  }));

  const fetchChannels = async () => {
    setLoading(true);
    try {
      const res = await channelsApi.list();
      setChannels(res?.data?.data || []);
    } catch { message.error('載入頻道失敗'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchChannels(); }, []);

  const handleCardClick = (ch: Channel) => {
    setSelectedChannel(ch);
    setDrawerOpen(true);
  };

  const handleToggle = async (key: string, checked: boolean) => {
    try {
      await channelsApi.update(key, { status: checked ? 'active' : 'inactive' });
      message.success(checked ? '已啟用' : '已停用');
      fetchChannels();
    } catch { message.error('更新失敗'); }
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      if (values.platform !== 'line') {
        message.warning(`${values.platform} 平台尚未開放，目前僅支援 LINE`);
        return;
      }
      setSaving(true);
      await channelsApi.create({
        platform: values.platform,
        business_user_key: values.business_user_key,
        business_user_name: values.business_user_name || users.find(u => u._key === values.business_user_key)?.name || '',
        role: values.role || '業務員',
        org_tags: values.org_tags || [],
        region_tags: values.region_tags || [],
        linked_agent_key: values.linked_agent_key || 'welfare_secretary',
        avatar: values.avatar || '',
        config: {
          channel_id: values.channel_id || '',
          channel_secret: values.channel_secret || '',
          access_token: values.access_token || '',
        },
      });
      setCreateModalOpen(false);
      form.resetFields();
      fetchChannels();
      message.success('頻道已建立');
    } catch { message.error('建立失敗'); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ padding: 24, background: contentTokens.contentBg, minHeight: '100%' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: '#666', fontSize: 13 }}>
          {channels.length > 0 ? `共 ${channels.length} 個頻道` : ''}
        </span>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setCreateModalOpen(true); }}>
          新增業務員/頻道
        </Button>
      </div>

      <Spin spinning={loading}>
        {channels.length === 0 ? (
          <Empty description={<span>尚無頻道設定<br /><span style={{ fontSize: 12, color: '#999' }}>點擊上方「新增業務員/頻道」開始設定</span></span>}
            style={{ marginTop: 60 }} />
        ) : (
          <>
            <Row gutter={[16, 16]}>
              {channels.map(ch => (
                <Col key={ch._key} xs={24} sm={12} md={8} lg={6}>
                  <ChannelCardComponent channel={ch} onClick={handleCardClick} onToggle={handleToggle} />
                </Col>
              ))}
            </Row>
          </>
        )}
      </Spin>

      <ChannelDetailDrawer
        channel={selectedChannel}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setSelectedChannel(null); }}
        onSaved={fetchChannels}
      />

      <Modal title="新增業務員/通訊頻道" open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)} onOk={handleCreate} width={520}
        okText="建立" confirmLoading={saving} destroyOnClose>
        <Form form={form} layout="vertical" size="small" initialValues={{ platform: 'line', role: '業務員', linked_agent_key: 'welfare_secretary' }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item label="平台" name="platform" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={PLATFORM_OPTIONS} />
            </Form.Item>
            <Form.Item label="角色" name="role" style={{ flex: 1 }}>
              <Select options={[{ label: '業務員', value: '業務員' }, { label: '業務主管', value: '業務主管' }]} />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item label="業務組織" name="org_tags" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後按 Enter" open={false}
                tokenSeparators={[',', '，', '|', '/']} />
            </Form.Item>
            <Form.Item label="負責區域" name="region_tags" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後按 Enter" open={false}
                tokenSeparators={[',', '，', '|', '/']} />
            </Form.Item>
          </div>
          <Form.Item label="綁定使用者" name="business_user_key">
            <Select options={userOptions} placeholder="選擇使用者" allowClear />
          </Form.Item>
          <Form.Item label="頻道別名" name="business_user_name" style={{ marginTop: -12 }}>
            <Input placeholder="留空則使用帳號名稱" />
          </Form.Item>
          <Form.Item label="連結 Agent" name="linked_agent_key">
            <Input placeholder="welfare_secretary" />
          </Form.Item>
          <Form.Item label="頭像" name="avatar">
            <AvatarPicker value={undefined} onChange={(val) => form.setFieldValue('avatar', val)} />
          </Form.Item>

          <Divider style={{ margin: '8px 0' }} />
          <Text strong style={{ fontSize: 13 }}>平台設定</Text>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px', marginTop: 8 }}>
            {PLATFORM_CONFIG_FIELDS.line.map(f => (
              <Form.Item key={f.key} name={f.key} label={f.label}>
                {f.type === 'password' ? <Input.Password /> : <Input />}
              </Form.Item>
            ))}
          </div>
        </Form>
      </Modal>
    </div>
  );
}
