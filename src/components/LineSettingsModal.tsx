import { useState, useCallback } from 'react';
import {
  Modal,
  Button,
  Typography,
  Empty,
  Spin,
  Space,
  Card,
  Row,
  Col,
  Popconfirm,
  App,
} from 'antd';
import { DeleteOutlined, MessageOutlined, GlobalOutlined } from '@ant-design/icons';
import type { LINEOfficialAccount, LINEChannel } from '../services/api';
import { linePlatformApi } from '../services/api';

const { Text } = Typography;

interface LineSettingsModalProps {
  open: boolean;
  onCancel: () => void;
}

export default function LineSettingsModal({ open, onCancel }: LineSettingsModalProps) {
  const { message: antMessage } = App.useApp();
  const [fetching, setFetching] = useState(false);
  const [accounts, setAccounts] = useState<LINEOfficialAccount[]>([]);
  const [accountsLoaded, setAccountsLoaded] = useState(false);

  const fetchAccounts = useCallback(async () => {
    setFetching(true);
    setAccountsLoaded(true);
    try {
      const response = await linePlatformApi.listOfficialAccounts();
      if (response.data.code === 200) {
        setAccounts(response.data.data || []);
      }
    } catch {
      antMessage.error('取得官方帳號失敗');
    } finally {
      setFetching(false);
    }
  }, [antMessage]);

  const handleDeleteAccount = async (key: string) => {
    try {
      await linePlatformApi.deleteOfficialAccount(key);
      antMessage.success('官方帳號已刪除');
      await fetchAccounts();
    } catch {
      antMessage.error('刪除失敗');
    }
  };

  const handleDeleteChannel = async (channelKey: string) => {
    try {
      await linePlatformApi.deleteChannel(channelKey);
      antMessage.success('Channel 已刪除');
      await fetchAccounts();
    } catch {
      antMessage.error('刪除失敗');
    }
  };

  return (
    <Modal
      title={
        <Space>
          <MessageOutlined style={{ color: '#00b900' }} />
          <span>LINE Bot 設定</span>
        </Space>
      }
      open={open}
      onCancel={onCancel}
      width="80%"
      style={{ top: 40 }}
      footer={[
        <Button key="close" onClick={onCancel}>關閉</Button>,
        <Button key="refresh" onClick={fetchAccounts} loading={fetching}>重新整理</Button>,
      ]}
    >
      <Spin spinning={fetching}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          {!accountsLoaded ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Button onClick={fetchAccounts} loading={fetching}>載入 LINE 帳號</Button>
            </div>
          ) : accounts.length === 0 ? (
            <Empty description="尚無 LINE 官方帳號設定" style={{ marginTop: 48 }} />
          ) : (
            <div style={{ marginTop: 16 }}>
              {accounts.map((account) => (
                <Card
                  key={account._key}
                  size="small"
                  style={{ marginBottom: 16, borderLeft: '3px solid #00b900' }}
                  title={
                    <Space>
                      <MessageOutlined style={{ color: '#00b900' }} />
                      <Text strong>{account.name}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Provider: {account.provider_name}
                      </Text>
                    </Space>
                  }
                  extra={
                    <Space>
                      <Text type="secondary">{account.channels.length} 個 Channel</Text>
                      <Popconfirm
                        title="確定要刪除這個官方帳號嗎？"
                        onConfirm={() => handleDeleteAccount(account._key)}
                        okText="刪除"
                        cancelText="取消"
                      >
                        <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  }
                >
                  {account.channels.length === 0 ? (
                    <Text type="secondary">尚無 Channel 設定</Text>
                  ) : (
                    <div>
                      {account.channels.map((channel: LINEChannel) => (
                        <Card
                          key={channel._key}
                          size="small"
                          style={{ marginBottom: 8, background: '#f5f5f5' }}
                          bodyStyle={{ padding: 12 }}
                        >
                          <Row gutter={16} align="middle">
                            <Col span={12}>
                              <Space direction="vertical" size={2}>
                                <Space>
                                  <GlobalOutlined />
                                  <Text strong>{channel.channel_name}</Text>
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    ID: {channel.channel_id}
                                  </Text>
                                </Space>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  Webhook: {channel.webhook_url}
                                </Text>
                              </Space>
                            </Col>
                            <Col span={12} style={{ textAlign: 'right' }}>
                              <Space>
                                <Text
                                  type={channel.publication_status === 'published' ? 'success' : 'secondary'}
                                  style={{ fontSize: 12 }}
                                >
                                  {channel.publication_status === 'published'
                                    ? `已發布 → ${channel.published_bot_name || 'Bot'}`
                                    : channel.publication_status === 'error'
                                    ? '錯誤'
                                    : '未發布'}
                                </Text>
                                <Popconfirm
                                  title="確定要刪除這個 Channel 嗎？"
                                  onConfirm={() => handleDeleteChannel(channel._key)}
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
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      </Spin>
    </Modal>
  );
}
