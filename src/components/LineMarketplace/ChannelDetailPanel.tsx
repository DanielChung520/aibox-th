/**
 * @file        ChannelDetailPanel.tsx
 * @description LINE Channel 詳情編輯面板，右侧展示式編輯所有 Channel 欄位
 * @lastUpdate  2026-04-19 06:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Drawer,
  Form,
  Input,
  Button,
  Space,
  Typography,
  Divider,
  Tag,
  App,
  Popconfirm,
  Select,
  Spin,
} from 'antd';
import {
  CloseOutlined,
  CopyOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import type { LINEChannel, Agent } from '../../services/api';
import { linePlatformApi, agentApi } from '../../services/api';
import AvatarPicker from '../AvatarPicker';
import { resolveChannelIconSrc } from '../../utils/avatarUtils';

const { Text } = Typography;

interface ChannelDetailPanelProps {
  channel: LINEChannel | null;
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
  onUpdated: () => void;
}

interface ChannelFormValues {
  channel_name: string;
  channel_id: string;
  channel_secret: string;
  channel_access_token: string;
  channel_icon?: string;
  channel_description?: string;
  linked_agent_key?: string;
}

export default function ChannelDetailPanel({
  channel,
  open,
  onClose,
  onDeleted,
  onUpdated,
}: ChannelDetailPanelProps) {
  const { message: antMessage } = App.useApp();
  const [form] = Form.useForm<ChannelFormValues>();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [revealToken, setRevealToken] = useState(false);
  const [revealSecret, setRevealSecret] = useState(false);
  const [lineAgents, setLineAgents] = useState<{ value: string; label: string }[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setAgentsLoading(true);
    // 先載入所有工具，找出 line_bot 的 tool key
    Promise.all([
      agentApi.list('bpa'),
      import('../../services/api').then(m => m.toolApi.list()),
    ]).then(([agentRes, toolRes]) => {
      const toolsList = toolRes.data.data || [];
      const lineBotKey = toolsList.find((t: any) => t.code === 'line_bot')?._key;
      if (!lineBotKey) { setAgentsLoading(false); return; }

      const items = agentRes.data.data || [];
      const opts: { value: string; label: string }[] = [];
      items.forEach((a: Agent) => {
        const atools = a.tools || [];
        if (atools.includes(lineBotKey)) {
          opts.push({ value: a._key || '', label: a.name });
        }
      });
      setLineAgents(opts);
    }).catch(() => {}).finally(() => setAgentsLoading(false));
  }, [open]);

  if (channel) {
    form.setFieldsValue({
      channel_name: channel.channel_name,
      channel_id: channel.channel_id,
      channel_secret: channel.channel_secret || '',
      channel_access_token: channel.channel_access_token || '',
      channel_icon: channel.channel_icon || '',
      channel_description: channel.channel_description || '',
      linked_agent_key: channel.linked_agent_key || undefined,
    });
  } else {
    form.resetFields();
  }

  const handleSave = async () => {
    if (!channel) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      await linePlatformApi.updateChannel(channel._key, {
        channel_name: values.channel_name,
        channel_id: values.channel_id,
        channel_secret: values.channel_secret,
        channel_access_token: values.channel_access_token,
        channel_icon: values.channel_icon || '',
        channel_description: values.channel_description || '',
        linked_agent_key: values.linked_agent_key || '',
      });
      antMessage.success('Channel 已儲存');
      onUpdated();
    } catch (error: any) {
      if (error.errorFields) return;
      antMessage.error(error.response?.data?.message || '儲存失敗');
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!channel) return;
    try {
      setTesting(true);
      const res = await linePlatformApi.testConnection(channel._key);
      if (res.data.data?.success) {
        antMessage.success(`連線成功！Bot User ID: ${res.data.data.bot_user_id}`);
      } else {
        antMessage.error(res.data.data?.error || '連線失敗');
      }
      onUpdated();
    } catch (error: any) {
      antMessage.error(error.response?.data?.message || '連線失敗');
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async () => {
    if (!channel) return;
    try {
      await linePlatformApi.deleteChannel(channel._key);
      antMessage.success('Channel 已刪除');
      onDeleted();
      onClose();
    } catch (error: any) {
      antMessage.error(error.response?.data?.message || '刪除失敗');
    }
  };

  const handleCopyWebhook = () => {
    if (!channel) return;
    navigator.clipboard.writeText(channel.webhook_url);
    antMessage.success('Webhook URL 已複製');
  };

  const handleOpenLineConsole = () => {
    window.open(`https://developers.line.biz/console/`, '_blank');
  };

  const isPublished = channel?.publication_status === 'published';

  return (
    <Drawer
      title={
        <Space>
          <img src="/line-logo.png" alt="LINE" style={{ height: 20, objectFit: 'contain' }} />
          <span>Channel 設定</span>
          {channel && (
            <Tag color={isPublished ? 'success' : 'default'}>
              {isPublished ? '已發布' : '未發布'}
            </Tag>
          )}
        </Space>
      }
      placement="right"
      width={480}
      open={open}
      onClose={onClose}
      maskClosable={true}
      extra={
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} />
      }
      footer={
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Popconfirm
            title="確定要刪除這個 Channel 嗎？"
            onConfirm={handleDelete}
            okText="刪除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button danger icon={<DeleteOutlined />}>刪除</Button>
          </Popconfirm>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" loading={saving} onClick={handleSave}>
              儲存
            </Button>
          </Space>
        </div>
      }
    >
      {channel && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Form form={form} layout="vertical" size="small">
            <Form.Item label="Channel Key">
              <Input.Group compact style={{ display: 'flex' }}>
                <Input value={channel._key} readOnly style={{ flex: 1, fontSize: 12 }} />
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => {
                    navigator.clipboard.writeText(channel._key);
                    antMessage.success('Channel Key 已複製');
                  }}
                />
              </Input.Group>
            </Form.Item>

            <Form.Item label="Webhook URL" name="webhook_url">
              <Input.Group compact style={{ display: 'flex' }}>
                <Input value={channel.webhook_url} style={{ flex: 1, fontSize: 12 }} />
                <Button icon={<CopyOutlined />} onClick={handleCopyWebhook} />
                <Button icon={<LinkOutlined />} onClick={handleOpenLineConsole} />
              </Input.Group>
            </Form.Item>

            <Divider style={{ margin: '8px 0' }} />

            <Form.Item
              label="Channel 名稱"
              name="channel_name"
              rules={[{ required: true, message: '請輸入 Channel 名稱' }]}
            >
              <Input placeholder="我的 LINE Bot" />
            </Form.Item>

            <Form.Item
              label="Channel ID"
              name="channel_id"
              rules={[{ required: true, message: '請輸入 Channel ID' }]}
              extra="LINE Developers Console → Basic settings → Channel ID"
            >
              <Input placeholder="200xxxxxxxxx" />
            </Form.Item>

            <Form.Item
              label="Channel Secret"
              name="channel_secret"
              extra="LINE Developers Console → Basic settings → Channel secret"
            >
              <Input.Password
                placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                visibilityToggle={{ visible: revealSecret, onVisibleChange: setRevealSecret }}
              />
            </Form.Item>

            <Divider style={{ margin: '8px 0' }} />

            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>Your User ID (Bot ID)</Text>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <Text strong style={{ fontSize: 13 }}>
                  {channel.bot_user_id || '尚未測試連線'}
                </Text>
                {channel.bot_user_id && (
                  <CheckCircleOutlined style={{ color: '#00b900' }} />
                )}
              </div>
            </div>

            <Form.Item
              label="Channel Access Token (Long-lived)"
              name="channel_access_token"
              extra="LINE Developers Console → Messaging API → Channel Access Token"
            >
              <Input.Password
                placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                visibilityToggle={{ visible: revealToken, onVisibleChange: setRevealToken }}
              />
            </Form.Item>

            <Form.Item
              label="Channel 圖示"
              name="channel_icon"
              extra="點擊選擇圖示"
            >
              <Form.Item noStyle shouldUpdate={(prev, curr) => prev.channel_icon !== curr.channel_icon}>
                {({ getFieldValue }) => {
                  const name = getFieldValue('channel_icon');
                  const src = resolveChannelIconSrc(name);
                  return (
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                      <AvatarPicker
                        value={name}
                        onChange={(val) => form.setFieldValue('channel_icon', val)}
                      />
                      {src && (
                        <img
                          src={src}
                          alt="preview"
                          style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 8, border: '1px solid #d9d9d9' }}
                        />
                      )}
                    </div>
                  );
                }}
              </Form.Item>
            </Form.Item>

            <Form.Item
              label="Channel 描述"
              name="channel_description"
              extra="描述這個 Channel 的用途"
            >
              <Input.TextArea placeholder="簡短描述 Channel" rows={2} />
            </Form.Item>

            <Divider style={{ margin: '8px 0' }} />

            <Form.Item
              label="關聯 Agent"
              name="linked_agent_key"
              extra="選擇有 LINE Bot 工具權限的 Agent，Webhook 訊息將自動路由到該 Agent"
            >
              <Select
                allowClear
                placeholder={agentsLoading ? '載入中...' : '請選擇 Agent'}
                loading={agentsLoading}
                options={lineAgents}
                notFoundContent={agentsLoading ? <Spin size="small" /> : '無符合條件的 Agent（需在工具權限設定 LINE Bot）'}
              />
            </Form.Item>

          </Form>

          <Divider style={{ margin: '8px 0' }} />

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>操作</Text>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button
                icon={<ApiOutlined />}
                onClick={handleTestConnection}
                loading={testing}
                style={{ width: '100%' }}
              >
                測試連線
              </Button>
              {channel.last_connected_at && (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  最後連線：{new Date(channel.last_connected_at).toLocaleString('zh-TW')}
                </Text>
              )}
            </Space>
          </div>
        </div>
      )}
    </Drawer>
  );
}
