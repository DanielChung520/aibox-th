/**
 * @file        PlatformLINE.tsx
 * @description LINE Channel 設定頁面，Grid 顯示所有 Channel 卡片，點擊展開右側詳情面板
 * @lastUpdate  2026-04-19 06:30:00
 * @author      Daniel Chung
 * @version     2.1.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Button,
  Typography,
  Modal,
  Form,
  Input,
  Empty,
  App,
  Spin,
  Row,
  Col,
  Divider,
} from 'antd';
import { PlusOutlined, MessageOutlined } from '@ant-design/icons';
import ChannelCard from '../components/LineMarketplace/ChannelCard';
import ChannelDetailPanel from '../components/LineMarketplace/ChannelDetailPanel';
import AvatarPicker from '../components/AvatarPicker';
import {
  linePlatformApi,
  type LINEOfficialAccount,
  type LINEChannel,
} from '../services/api';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const { Title } = Typography;

export default function PlatformLINE() {
  const { message: antMessage } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [accounts, setAccounts] = useState<LINEOfficialAccount[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<LINEChannel | null>(null);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [channelForm] = Form.useForm();

  useEntityPerception({ defaultEntityType: 'line_platform', defaultAction: 'list' });

  const fetchAccounts = useCallback(async () => {
    try {
      const response = await linePlatformApi.listOfficialAccounts();
      if (response.data.code === 200) {
        setAccounts(response.data.data || []);
      }
    } catch (error: any) {
      antMessage.error(error.response?.data?.message || '取得資料失敗');
    } finally {
      setLoading(false);
    }
  }, [antMessage]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  useEffect(() => {
    pageContextManager.report({ component: 'PlatformLINE', entityType: 'line_platform', action: 'list' });
  }, []);

  const handleCardClick = (channel: LINEChannel) => {
    setSelectedChannel(channel);
    setDetailPanelOpen(true);
  };

  const handleAddChannel = async () => {
    channelForm.resetFields();
    if (accounts.length === 0) {
      try {
        await linePlatformApi.createOfficialAccount({
          provider_name: 'Default',
          name: '預設官方帳號',
        });
        await fetchAccounts();
      } catch (error: any) {
        antMessage.error(error.response?.data?.message || '建立官方帳號失敗');
        return;
      }
    }
    setCreateModalOpen(true);
  };

  const handleCreateChannel = async () => {
    const targetAccount = accounts[0];
    if (!targetAccount) return;
    try {
      const values = await channelForm.validateFields();
      await linePlatformApi.createChannel(targetAccount._key, {
        channel_name: values.channel_name,
        channel_id: values.channel_id,
        channel_secret: values.channel_secret,
        channel_access_token: values.channel_access_token,
        channel_icon: values.channel_icon || '',
        channel_description: values.channel_description || '',
      });
      setCreateModalOpen(false);
      channelForm.resetFields();
      await fetchAccounts();
      antMessage.success('Channel 已建立');
    } catch (error: any) {
      if (error.errorFields) return;
      antMessage.error(error.response?.data?.message || '建立失敗');
    }
  };

  const allChannels: LINEChannel[] = accounts.flatMap((a) => a.channels);
  const totalChannels = allChannels.length;
  const connectedCount = allChannels.filter((c) => c.publication_status === 'published').length;

  return (
    <div style={{ padding: 24 }}>
      <Spin spinning={loading}>
        <div
          style={{
            marginBottom: 24,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Title level={4} style={{ margin: 0 }}>
            <MessageOutlined style={{ marginRight: 8, color: '#00b900' }} />
            LINE Channel 設定
          </Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddChannel}>
            新增 Channel
          </Button>
        </div>

        {totalChannels === 0 ? (
          <Empty
            description={
              <span>
                尚無 LINE Channel 設定
                <br />
                <span style={{ fontSize: 12, color: '#999' }}>
                  點擊上方「新增 Channel」開始設定
                </span>
              </span>
            }
            style={{ marginTop: 80 }}
          />
        ) : (
          <>
            <div style={{ marginBottom: 16, color: '#666', fontSize: 13 }}>
              共 {totalChannels} 個 Channel，{connectedCount} 個已發布
            </div>
            <Row gutter={[16, 16]}>
              {allChannels.map((channel) => (
                <Col key={channel._key} xs={24} sm={12} md={8} lg={6} xl={6}>
                  <ChannelCard
                    channel={channel}
                    onClick={handleCardClick}
                    isSelected={selectedChannel?._key === channel._key}
                  />
                </Col>
              ))}
            </Row>
          </>
        )}

        <ChannelDetailPanel
          channel={selectedChannel}
          open={detailPanelOpen}
          onClose={() => {
            setDetailPanelOpen(false);
            setSelectedChannel(null);
          }}
          onDeleted={() => {
            setSelectedChannel(null);
            fetchAccounts();
          }}
          onUpdated={() => fetchAccounts()}
        />

        <Modal
          title="新增 LINE Channel"
          open={createModalOpen}
          onCancel={() => {
            setCreateModalOpen(false);
            channelForm.resetFields();
          }}
          onOk={handleCreateChannel}
          okText="建立"
          cancelText="取消"
        >
          <Form form={channelForm} layout="vertical" style={{ marginTop: 16 }}>
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
              rules={[{ required: true, message: '請輸入 Channel Secret' }]}
              extra="LINE Developers Console → Basic settings → Channel secret"
            >
              <Input.Password placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" />
            </Form.Item>
            <Form.Item
              label="Channel Access Token (Long-lived)"
              name="channel_access_token"
              rules={[{ required: true, message: '請輸入 Channel Access Token' }]}
              extra="LINE Developers Console → Messaging API → Channel Access Token"
            >
              <Input.Password placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" />
            </Form.Item>

            <Divider style={{ margin: '8px 0' }} />

            <div style={{ marginBottom: 8 }}>
              <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 12, marginBottom: 4 }}>Your User ID (Bot ID)</div>
              <div style={{ color: '#999', fontSize: 13 }}>待連線（建立完成後，點擊 Channel 卡片上的「測試連線」取得）</div>
            </div>

            <Form.Item
              label="Channel 圖示"
              name="channel_icon"
            >
              <AvatarPicker
                value={undefined}
                onChange={(val) => channelForm.setFieldValue('channel_icon', val)}
              />
            </Form.Item>

            <Form.Item
              label="Channel 描述"
              name="channel_description"
              extra="描述這個 Channel 的用途"
            >
              <Input.TextArea placeholder="簡短描述 Channel" rows={2} />
            </Form.Item>
          </Form>
        </Modal>
      </Spin>
    </div>
  );
}
