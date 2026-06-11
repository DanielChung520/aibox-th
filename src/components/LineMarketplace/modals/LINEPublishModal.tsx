/**
 * @file        LINEPublishModal.tsx
 * @description LINE Channel 發布到 Bot Modal
 * @lastUpdate  2026-04-19 02:10:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState } from 'react';
import {
  Modal,
  Form,
  Select,
  Input,
  Card,
  Typography,
  Space,
  App,
} from 'antd';

const { Text } = Typography;

interface BotAgent {
  _key: string;
  name: string;
  description?: string;
  intents?: string[];
}

interface LINEPublishModalProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (botKey: string, customSettings?: PublishSettings) => Promise<void>;
  channelName: string;
  channelId: string;
  availableBots: BotAgent[];
  currentPublishedBotKey?: string;
}

export interface PublishSettings {
  greeting?: string;
  delay?: number;
}

export default function LINEPublishModal({
  open,
  onCancel,
  onSubmit,
  channelName,
  channelId,
  availableBots,
  currentPublishedBotKey,
}: LINEPublishModalProps) {
  const [form] = Form.useForm();
  const { message: antMessage } = App.useApp();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      await onSubmit(values.bot_key, {
        greeting: values.greeting,
        delay: values.delay || 0,
      });
      antMessage.success('發布成功');
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
      title="發布 LINE Channel"
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      okText="發布"
      cancelText="取消"
      width={500}
      centered
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Card
          type="inner"
          title="Channel 資訊"
          style={{ marginBottom: 16 }}
          styles={{ body: { paddingBottom: 8 } }}
        >
          <Space direction="vertical" size={4}>
            <Text strong>{channelName}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Channel ID: {channelId}
            </Text>
          </Space>
        </Card>

        <Form.Item
          label="選擇 Bot Agent"
          name="bot_key"
          rules={[{ required: true, message: '請選擇 Bot Agent' }]}
        >
          <Select placeholder="請選擇 Bot Agent">
            {availableBots.map((bot) => (
              <Select.Option key={bot._key} value={bot._key} disabled={bot._key === currentPublishedBotKey}>
                <div>
                  <div>{bot.name}</div>
                  {bot.intents && bot.intents.length > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      意圖：{bot.intents.join('、')}
                    </Text>
                  )}
                </div>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="客製化設定" style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            以下為選填設定
          </Text>
        </Form.Item>

        <Form.Item
          label="歡迎訊息"
          name="greeting"
        >
          <Input.TextArea
            placeholder="您好！歡迎使用客服服務，請問有什麼可以幫您？"
            rows={2}
          />
        </Form.Item>

        <Form.Item
          label="自動回覆延遲（秒）"
          name="delay"
          extra="0表示立即回覆"
        >
          <Input type="number" placeholder="0" min={0} max={30} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
