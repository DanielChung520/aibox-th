import { Card, Collapse, Button, Space, Badge, Typography, Row, Col, Popconfirm } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CopyOutlined,
  GlobalOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import type { LINEOfficialAccount, LINEChannel } from '../../services/lineTypes';

const { Text } = Typography;

interface ProviderListProps {
  accounts: LINEOfficialAccount[];
  activeKeys: string[];
  onToggleExpand: (key: string) => void;
  onEditChannel: (account: LINEOfficialAccount, channel: LINEChannel) => void;
  onAddChannel: (account: LINEOfficialAccount) => void;
  onPublishChannel: (channel: LINEChannel) => void;
  onDeleteChannel: (accountKey: string, channelKey: string) => void;
  onDeleteAccount: (accountKey: string) => void;
  onCopyWebhook: (url: string) => void;
}

export default function ProviderList({
  accounts,
  activeKeys,
  onToggleExpand,
  onEditChannel,
  onAddChannel,
  onPublishChannel,
  onDeleteChannel,
  onDeleteAccount,
  onCopyWebhook,
}: ProviderListProps) {
  const collapseItems = accounts.map((account) => ({
    key: account._key,
    label: (
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          width: '100%',
          paddingRight: 8,
        }}
      >
        <Space>
          <MessageOutlined />
          <div>
            <Text strong>{account.name}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Provider: {account.provider_name} | Channels: {account.channels.length} 個
            </Text>
          </div>
        </Space>
        <Space>
          <Badge status={account.status === 'active' ? 'success' : 'error'} />
          <Popconfirm
            title="確定要刪除這個官方帳號嗎？"
            onConfirm={() => onDeleteAccount(account._key)}
            okText="刪除"
            cancelText="取消"
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      </div>
    ),
    children: (
      <div style={{ marginBottom: 16 }}>
        {account.channels.map((channel) => (
          <Card
            key={channel._key}
            size="small"
            style={{ marginBottom: 8, borderLeft: '3px solid #00b900' }}
          >
            <Row gutter={16} align="middle">
              <Col span={16}>
                <Space direction="vertical" size={2}>
                  <Space>
                    <GlobalOutlined />
                    <Text strong>{channel.channel_name}</Text>
                    <Badge
                      status={
                        channel.publication_status === 'published'
                          ? 'success'
                          : channel.publication_status === 'error'
                          ? 'error'
                          : 'warning'
                      }
                      text={
                        channel.publication_status === 'published'
                          ? `已發布 → ${channel.published_bot_name}`
                          : channel.publication_status === 'error'
                          ? '錯誤'
                          : '未發布'
                      }
                    />
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Channel ID: {channel.channel_id}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Webhook: {channel.webhook_url}{' '}
                    <Button
                      type="link"
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => onCopyWebhook(channel.webhook_url)}
                    />
                  </Text>
                </Space>
              </Col>
              <Col span={8} style={{ textAlign: 'right' }}>
                <Space>
                  <Button
                    type="link"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => onEditChannel(account, channel)}
                  >
                    編輯
                  </Button>
                  <Button
                    type="link"
                    size="small"
                    onClick={() => onPublishChannel(channel)}
                  >
                    發布
                  </Button>
                  <Popconfirm
                    title="確定要刪除這個 Channel 嗎？"
                    onConfirm={() => onDeleteChannel(account._key, channel._key)}
                    okText="刪除"
                    cancelText="取消"
                  >
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              </Col>
            </Row>
          </Card>
        ))}
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={() => onAddChannel(account)}
          style={{ width: '100%' }}
        >
          新增 Channel
        </Button>
      </div>
    ),
  }));

  if (accounts.length === 0) {
    return null;
  }

  return (
    <Collapse
      activeKey={activeKeys}
      onChange={(keys) => {
        if (Array.isArray(keys)) {
          keys.forEach((k) => onToggleExpand(k));
        } else if (typeof keys === 'string') {
          onToggleExpand(keys);
        }
      }}
      items={collapseItems}
      accordion
    />
  );
}
