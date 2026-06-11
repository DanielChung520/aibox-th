/**
 * @file        ChannelEditModal.tsx
 * @description LINE Channel 分層式編輯 Modal
 * @lastUpdate  2026-04-19 02:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useEffect } from 'react';
import { useState } from 'react';
import {
  Modal,
  Form,
  Input,
  Card,
  Row,
  Col,
  Button,
  Space,
  Badge,
  Typography,
  Alert,
  App,
} from 'antd';
import {
  CopyOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { LINEOfficialAccount, LINEChannel } from '../../../services/lineTypes';

const { Text } = Typography;

interface ChannelEditModalProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: ChannelFormValues) => Promise<void>;
  onTestConnection?: (channelKey: string) => Promise<{ success: boolean; bot_user_id?: string; error?: string }>;
  editingAccount?: LINEOfficialAccount | null;
  editingChannel?: LINEChannel | null;
  mode: 'create' | 'edit';
  officialAccountKey?: string;
}

export interface ChannelFormValues {
  provider_name: string;
  official_account_name: string;
  channel_name: string;
  channel_id: string;
  channel_secret: string;
  channel_access_token: string;
}

const rules = {
  provider_name: [{ required: true, message: '請輸入 Provider 名稱' }],
  official_account_name: [{ required: true, message: '請輸入官方帳號名稱' }],
  channel_name: [{ required: true, message: '請輸入 Channel 名稱' }],
  channel_id: [
    { required: true, message: '請輸入 Channel ID' },
    { pattern: /^\d+$/, message: 'Channel ID 必須為數字' },
  ],
  channel_secret: [
    { required: true, message: '請輸入 Channel Secret' },
  ],
  channel_access_token: [
    { required: true, message: '請輸入 Channel Access Token' },
  ],
};

export default function ChannelEditModal({
  open,
  onCancel,
  onSubmit,
  onTestConnection,
  editingAccount,
  editingChannel,
  mode,
  officialAccountKey,
}: ChannelEditModalProps) {
  const [form] = Form.useForm<ChannelFormValues>();
  const { message: antMessage } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);

  useEffect(() => {
    if (open) {
      if (mode === 'edit' && editingChannel) {
        form.setFieldsValue({
          provider_name: editingAccount?.provider_name || '',
          official_account_name: editingAccount?.name || '',
          channel_name: editingChannel.channel_name || '',
          channel_id: editingChannel.channel_id || '',
          channel_secret: editingChannel.channel_secret || '',
          channel_access_token: editingChannel.channel_access_token || '',
        });
      } else {
        form.resetFields();
        if (editingAccount) {
          form.setFieldsValue({
            provider_name: editingAccount.provider_name,
            official_account_name: editingAccount.name,
          });
        }
      }
    }
  }, [open, mode, editingChannel, editingAccount, form]);

  const handleCopyWebhook = () => {
    const webhookUrl = editingChannel?.webhook_url || `https://eeaapi.ent4i.com/api/v1/webhook/line/${officialAccountKey || 'new'}`;
    navigator.clipboard.writeText(webhookUrl).then(() => {
      antMessage.success('Webhook URL 已複製');
    });
  };

  const handleTestConnection = async () => {
    if (!editingChannel?._key) {
      antMessage.warning('請先儲存後再測試連線');
      return;
    }

    setTestingConnection(true);
    try {
      if (onTestConnection) {
        const result = await onTestConnection(editingChannel._key);
        if (result.success) {
          antMessage.success('連線測試成功');
        } else {
          antMessage.error(result.error || '連線失敗');
        }
      }
    } catch (err) {
      antMessage.error('連線測試失敗');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      await onSubmit(values);
      antMessage.success(mode === 'create' ? 'Channel 已建立' : 'Channel 已更新');
      form.resetFields();
    } catch (err) {
      if (err instanceof Error) {
        antMessage.error(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={mode === 'create' ? '新增 LINE Channel' : '編輯 LINE Channel'}
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      okText={mode === 'create' ? '建立' : '儲存變更'}
      cancelText="取消"
      width={700}
      centered
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        {/* 區塊 1：官方帳號設定 */}
        <Card
          type="inner"
          title="官方帳號設定"
          style={{ marginBottom: 16 }}
          styles={{ body: { paddingBottom: 8 } }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Provider 名稱"
                name="provider_name"
                rules={rules.provider_name}
              >
                <Input placeholder="客戶A公司" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="官方帳號名稱"
                name="official_account_name"
                rules={rules.official_account_name}
              >
                <Input placeholder="客戶A LINE客服" />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        {/* 區塊 2：Channel 設定 */}
        <Card
          type="inner"
          title="Channel 設定"
          style={{ marginBottom: 16 }}
          styles={{ body: { paddingBottom: 8 } }}
        >
          <Form.Item
            label="Channel 名稱"
            name="channel_name"
            rules={rules.channel_name}
          >
            <Input placeholder="例如: ChristCoffee (客服)" />
          </Form.Item>

          <Form.Item
            label="Channel ID"
            name="channel_id"
            rules={rules.channel_id}
            extra="格式：200xxxxxxx，可從 LINE Developers Console 取得"
          >
            <Input placeholder="例如: 2001234567" />
          </Form.Item>

          <Form.Item
            label="Channel Secret"
            name="channel_secret"
            rules={rules.channel_secret}
            extra="可從 LINE Developers Console > Basic settings 取得"
          >
            <Input.Password placeholder="輸入 Secret" />
          </Form.Item>

          <Form.Item
            label="Channel Access Token (Long-lived)"
            name="channel_access_token"
            rules={rules.channel_access_token}
            extra="請至 LINE Developers Console > Messaging API > Channel Access Token (long-lived) 取得"
          >
            <Input.Password placeholder="輸入 Access Token" />
          </Form.Item>
        </Card>

        {/* 區塊 3：Webhook 設定 */}
        <Card
          type="inner"
          title="Webhook 設定"
          style={{ marginBottom: 16 }}
          styles={{ body: { paddingBottom: 8 } }}
        >
          <Form.Item label="Webhook URL (自動產生)">
            <Input
              readOnly
              value={editingChannel?.webhook_url || `https://eeaapi.ent4i.com/api/v1/webhook/line/${officialAccountKey || 'new'}`}
              addonAfter={
                <CopyOutlined onClick={handleCopyWebhook} style={{ cursor: 'pointer' }} />
              }
            />
          </Form.Item>
          <Alert
            message="請至 LINE Developers Console > Messaging API > Webhook settings 貼上此 URL 並啟用 Webhook"
            type="info"
            showIcon
          />
        </Card>

        {/* 區塊 4：連線狀態 */}
        {mode === 'edit' && editingChannel && (
          <Card
            type="inner"
            title="連線狀態"
            styles={{ body: { paddingBottom: 8 } }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Space direction="vertical" size={4}>
                  <div>
                    <Badge
                      status={editingChannel.status === 'connected' ? 'success' : editingChannel.status === 'error' ? 'error' : 'default'}
                      text={
                        editingChannel.status === 'connected'
                          ? '已驗證'
                          : editingChannel.status === 'error'
                          ? '驗證失敗'
                          : '未驗證'
                      }
                    />
                  </div>
                  {editingChannel.bot_user_id && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      Bot User ID: {editingChannel.bot_user_id}
                    </Text>
                  )}
                  {editingChannel.last_connected_at && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      最後連線: {editingChannel.last_connected_at}
                    </Text>
                  )}
                </Space>
              </div>
              <Space>
                <Button icon={<SyncOutlined />} onClick={handleTestConnection} loading={testingConnection}>
                  測試連線
                </Button>
              </Space>
            </div>
          </Card>
        )}
      </Form>
    </Modal>
  );
}
